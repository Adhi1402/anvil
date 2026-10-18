"""The single door to Gemini (Vertex AI): one client, timeouts, retries, and per-call telemetry
(latency, tokens, estimated cost) so governance can report what governing costs."""
import json
import logging
import os
import threading
import time
import uuid
from google import genai
from google.genai import types

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# Estimated list prices in USD per 1M tokens; override via env if pricing changes. Output includes thinking tokens.
PRICE_IN = float(os.environ.get("GEMINI_PRICE_IN_PER_M", "0.30"))
PRICE_OUT = float(os.environ.get("GEMINI_PRICE_OUT_PER_M", "2.50"))

_client = None
_lock = threading.Lock()


def client():
    global _client
    if _client is None:
        with _lock:                                  # threads must not each build (and then discard/close) a client
            if _client is None:
                _client = genai.Client(
                    vertexai=True,
                    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "dazzling-lodge-511607-m0"),
                    location="us-central1",
                    http_options=types.HttpOptions(timeout=20_000),   # a stalled call must fail fast and be retried
                )
    return _client


def _meta(resp, started, attempts):
    u = getattr(resp, "usage_metadata", None)
    tin = getattr(u, "prompt_token_count", 0) or 0
    tout = (getattr(u, "candidates_token_count", 0) or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
    return {"model": MODEL, "latency_ms": int((time.time() - started) * 1000), "attempts": attempts,
            "prompt_tokens": tin, "output_tokens": tout,
            "cost_usd": round(tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT, 6)}


_ctx = threading.local()


def set_trace_context(**kw):
    """What the next model calls on this thread are for (requester, trip, leg...). Shown on the traces page."""
    _ctx.v = {k: v for k, v in kw.items() if v is not None}


def clear_trace_context():
    _ctx.v = {}


def _write_trace(doc):
    """Every model call is stored with its full input and output. Best-effort: tracing must never break a decision."""
    try:
        from datetime import datetime, timezone
        from data.store import db
        db().collection("llm_traces").document(doc["id"]).set({"ts": datetime.now(timezone.utc).isoformat(), **doc})
    except Exception as e:
        logging.warning("trace not stored: %s", e)


def call_json(contents, schema, retries=4, temperature=0, purpose="llm"):
    """Returns (parsed_json, telemetry). Retries quota/overload/stalls with backoff; raises after the last attempt.
    purpose: audit | plan | correct. The telemetry carries trace_id, the key of the stored input/output of this call."""
    config = types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema,
                                         temperature=temperature)
    started, tid = time.time(), uuid.uuid4().hex[:16]
    base = {"id": tid, "purpose": purpose, "model": MODEL, "prompt": str(contents)[:40000], "temperature": temperature,
            "ctx": dict(getattr(_ctx, "v", {}) or {})}
    for attempt in range(retries):
        try:
            resp = client().models.generate_content(model=MODEL, contents=contents, config=config)
            out, meta = json.loads(resp.text), _meta(resp, started, attempt + 1)
            meta["trace_id"] = tid
            _write_trace({**base, "status": "ok", "response": str(resp.text)[:20000], "parsed": out, **{k: meta[k] for k in ("latency_ms", "attempts", "prompt_tokens", "output_tokens", "cost_usd")}})
            return out, meta
        except Exception as e:                       # APIError, or a timeout/connection stall (no .code)
            code = getattr(e, "code", None)
            logging.warning("gemini attempt %d failed: %s %s", attempt + 1, type(e).__name__, str(e)[:200])
            if (code is not None and code not in (429, 500, 503)) or attempt == retries - 1:
                _write_trace({**base, "status": "error", "error": f"{type(e).__name__}: {str(e)[:400]}", "latency_ms": int((time.time() - started) * 1000),
                              "attempts": attempt + 1, "prompt_tokens": 0, "output_tokens": 0, "cost_usd": 0})
                raise
            time.sleep(2 ** attempt)
