"""Anvil walking skeleton: mandate -> travel agent -> Gemini auditor -> Firestore -> dashboard."""
import collections
import hashlib
import html
import json
import os
import random
import time
from functools import wraps
from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from flask import Flask, Response, jsonify, request, redirect
from agents.run import travel_agent, plan_trip
from agents import planner
from anvil.audit import audit, rules_baseline
from anvil import ap2_layer
from anvil.guard import book_with_guard, guard_stream
from anvil.impact import counterfactual, impact_summary
from anvil.metrics import metrics_summary
from data.store import (db, get_mandate, verify_mandate, log_provenance, list_provenance, verify_chain,
                        delegation_for, cart_mandate, get_controls, set_controls, sim_lease)

app = Flask(__name__)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"      # public read API for the Firebase-hosted dashboard
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


# ---- light abuse protection for the endpoints that cost Gemini calls (per instance, per IP)
RATE_PER_MIN = int(os.environ.get("ANVIL_RATE_PER_MIN", "120"))
_rate = {}


def _client_ip():
    return (request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or "?")


def limited(fn):
    @wraps(fn)
    def inner(*a, **k):
        if request.method == "OPTIONS":
            return fn(*a, **k)
        now, q = time.time(), _rate.setdefault(_client_ip(), collections.deque())
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_PER_MIN:
            return jsonify({"error": "rate limit: too many requests, please slow down"}), 429
        q.append(now)
        return fn(*a, **k)
    return inner


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Anvil</title>
<style>body{{font-family:system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}}
.e{{border:1px solid #ccc;border-radius:8px;padding:.8rem;margin:.6rem 0}}
.MATCH{{border-left:6px solid #1a7f37}}.REVIEW{{border-left:6px solid #bf8700}}.DRIFT{{border-left:6px solid #cf222e}}
pre{{white-space:pre-wrap;margin:.3rem 0}}button{{padding:.5rem 1rem;font-size:1rem}}</style>
<h1>Anvil provenance log</h1>
<form method=post action=/run><button>Run agent now</button></form>
{entries}"""


@app.route("/")
def dashboard():
    rows = []
    for e in list_provenance():
        rows.append(
            f'<div class="e {html.escape(e["verdict"])}"><b>{html.escape(e["verdict"])}</b> '
            f'({html.escape(e["severity"])}) &middot; {html.escape(e["ts"])} &middot; mandate {html.escape(e["mandate_id"])}'
            f'<pre>Action: {html.escape(json.dumps(e["action"]))}</pre>'
            f'<pre>{html.escape(e["explanation"])}</pre></div>')
    return PAGE.format(entries="".join(rows) or "<p>No entries yet.</p>")


@app.route("/run", methods=["GET", "POST"])
def run():
    intent = get_mandate()
    if not verify_mandate(intent):
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    mandate = intent["constraints"]
    action = travel_agent(mandate)
    result = audit(mandate, action)
    entry_id = log_provenance(intent["mandateId"], action, result)
    out = {"mandate": intent, "action": action, "audit": result,
           "rules_baseline_pass": rules_baseline(mandate, action), "provenance_id": entry_id}
    return redirect("/") if request.method == "POST" else jsonify(out)


def _log_steps(intent, steps, agent_telemetry=None, meta=None):
    """Log every step with its 3-hop delegation chain; MATCH steps also get a signed Cart Mandate."""
    for st in steps:
        extra = {"intent_signature": intent["signature"], **(meta or {})}
        tele = st["audit"].get("telemetry")
        if tele:
            extra["telemetry"] = tele
        token = st["audit"].pop("ap2_token", None)             # keep the 3 KB chain out of the stream; it is stored on the entry
        if st["audit"].get("ap2"):
            extra["ap2"] = {**st["audit"]["ap2"], **({"chain_token": token} if token else {})}
        if st["audit"].get("source") == "ap2-constraints":
            extra["gate"] = "ap2-constraints"
        if agent_telemetry:
            extra["agent_telemetry"] = agent_telemetry
            agent_telemetry = None
        if st["audit"]["verdict"] in ("DRIFT", "REVIEW"):
            extra["counterfactual"] = st["counterfactual"] = counterfactual(intent["constraints"], st["action"], st["audit"]["verdict"])
        if st["audit"]["verdict"] == "MATCH":
            extra["cart_mandate"] = st["cart_mandate"] = cart_mandate(intent, st["action"])
        st["provenance_id"] = log_provenance(intent["mandateId"], st["action"], st["audit"],
                                             delegation=delegation_for(intent, st["action"]), extra=extra)


def _halt_reason(controls, action):
    if controls.get("mandate_revoked"):
        return "mandate revoked by the manager"
    kind = action.get("type", "").replace("book_", "")
    if kind in controls.get("paused_agents", []):
        return f"{kind} agent paused by the manager"
    return None


def _ev(name, **kw):
    return {"event": name, "t": round(time.time(), 3), **kw}


def _clean(v, n):
    return str(v).strip()[:n] if v is not None else None


def _meta(requester, origin, request_text):
    """Who/what produced these decisions, stored on every provenance entry (and shown in the live feed)."""
    m = {"origin": origin}
    if requester:
        m["requester"] = _clean(requester, 40)
    if request_text:
        m["request"] = _clean(request_text, 200)
    return m


def run_stream(intent, proposals, request_text=None, requester=None, origin="user", enforce=True, max_corrections=None):
    """The one execution path: proposals [(action, rationale, agent_telemetry)] -> guarded, logged, streamed events.
    Every step is written to the provenance chain the moment it completes, so Firestore listeners update live too.
    enforce=False simulates an UNPROTECTED agent for the demo contrast: nothing is audited, logged or issued; the
    leaked dollars are computed deterministically from the action vs the mandate."""
    mandate, controls = intent["constraints"], get_controls()
    meta = _meta(requester, origin, request_text)
    yield _ev("run_start", request=request_text, legs=len(proposals), controls=controls, enforce=enforce, requester=meta.get("requester"))
    if not enforce:
        for action, rationale, _ in proposals:
            kind = action["type"].replace("book_", "")
            yield _ev("proposal", kind=kind, action=action, rationale=rationale)
            cf = counterfactual(mandate, action, "UNCHECKED")
            leak = cf["total_usd"] if cf["findings"] else 0
            cf = {**cf, "leaked_usd": leak, "outcome": "executed unchecked",
                  "summary": f"Executed with no check: ${cf['total_usd']:,.0f} spent" + (f" ({'; '.join(cf['findings'])})." if cf["findings"] else ", within policy.")}
            step = {"action": action, "bypass": True, "counterfactual": cf,
                    "audit": {"verdict": "UNCHECKED", "severity": "none", "violations": cf["findings"], "source": "bypass",
                              "explanation": "Anvil enforcement is OFF: this action was executed without being checked."}}
            yield _ev("step", kind=kind, step=step)
        yield _ev("run_done", bypass=True)
        return
    for action, rationale, a_tele in proposals:
        kind = action["type"].replace("book_", "")
        yield _ev("proposal", kind=kind, action=action, rationale=rationale)
        pending_tele = a_tele
        gkw = {} if max_corrections is None else {"max_corrections": max_corrections}
        for g in guard_stream(mandate, action, _halt_reason(controls, action), **gkw):
            e = g.pop("event")
            if e != "audit":
                yield _ev(e, kind=kind, **g)
                continue
            step = {"action": g["action"], "audit": g["audit"], **({"correction_attempt": g["attempt"]} if g["attempt"] else {})}
            agent_tele = g.get("replan_telemetry") or pending_tele
            pending_tele = None
            _log_steps(intent, [step], agent_tele, meta)
            yield _ev("step", kind=kind, step=step, agent_cost_usd=(agent_tele or {}).get("cost_usd", 0))
    yield _ev("run_done")


def _verified_intent():
    intent = get_mandate()
    return intent if verify_mandate(intent) else None


def _stream_response(gen):
    def lines():
        try:
            for ev in gen:
                yield json.dumps(ev) + "\n"
        except Exception as e:                                    # never leave the UI hanging on a half-open stream
            yield json.dumps(_ev("error", message=f"{type(e).__name__}: {e}"[:300])) + "\n"
    return Response(lines(), mimetype="application/x-ndjson", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


def _scenario_proposals(mandate, name):
    from data.scenarios import SCENARIOS
    name = (name or "").lower()
    if name == "trip":
        return [(a, "scripted agent", None) for a in plan_trip(mandate)]
    s = next((x for x in SCENARIOS if x["name"].lower().startswith(name)), None)
    return [((s["action"] if s else travel_agent(mandate)), f"scripted scenario: {s['name']}" if s else "scripted agent", None)]


@app.route("/stream/request", methods=["POST", "OPTIONS"])
@limited
def stream_request():
    """Gemini-driven agent: plain-English request -> A2A discovery -> Gemini picks each leg -> guarded, streamed."""
    if request.method == "OPTIONS":
        return ("", 204)
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()[:500]
    requester, enforce = body.get("requester"), body.get("enforce", True) is not False
    intent = _verified_intent()
    if not intent:
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    if not text:
        return jsonify({"error": "empty request"}), 400
    mandate = intent["constraints"]

    def gen():
        yield _ev("agent_start", request=text)
        gathered = planner.gather_offers(mandate)
        for kind, g in gathered.items():
            yield _ev("discovered", kind=kind, agent=g["card"], via=g["via"], offers=len(g["offers"]))
        yield _ev("planning")
        try:
            plan, meta = planner.choose(mandate, text, gathered)
        except Exception as e:
            yield _ev("planner_fallback", message=f"{type(e).__name__}")
            plan, meta = planner.fallback(mandate), None
        proposals = [(a, why, meta if i == 0 else None) for i, (a, why) in enumerate(plan)]
        yield from run_stream(intent, proposals, text, requester=requester, enforce=enforce)
    return _stream_response(gen())


@app.route("/stream/scenario", methods=["POST", "OPTIONS"])
@limited
def stream_scenario():
    """Scripted 'rogue agent' scenarios and the clean trip, streamed."""
    if request.method == "OPTIONS":
        return ("", 204)
    intent = _verified_intent()
    if not intent:
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    body = request.get_json(silent=True) or {}
    name = body.get("name", "trip")
    return _stream_response(run_stream(intent, _scenario_proposals(intent["constraints"], name),
                                       requester=body.get("requester"), enforce=body.get("enforce", True) is not False))


@app.route("/run/<scenario>", methods=["GET", "POST"])
def run_scenario(scenario):
    """Fire a named scenario and return the steps as JSON (the streaming endpoints are the live-UI path)."""
    intent = _verified_intent()
    if not intent:
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    steps = [e["step"] for e in run_stream(intent, _scenario_proposals(intent["constraints"], scenario)) if e["event"] == "step"]
    return jsonify(steps)


def _resolve_review(entry_id, approved):
    """Human re-consent on a REVIEW entry: appends a new provenance entry, once per REVIEW."""
    doc = db().collection("provenance").document(entry_id).get()
    if not doc.exists:
        return jsonify({"error": "no such provenance entry"}), 404
    e = doc.to_dict()
    if e["verdict"] != "REVIEW":
        return jsonify({"error": "only REVIEW entries need approval"}), 400
    if list(db().collection("provenance").where(filter=FieldFilter("action.re_consent_for", "==", entry_id)).limit(1).stream()):
        return jsonify({"error": "already resolved"}), 409
    verdict = "APPROVED" if approved else "REJECTED"
    audit_like = {"verdict": verdict, "severity": "none", "violations": [],
                  "explanation": ("Human re-consented: manager approved the escalated action."
                                  if approved else "Manager rejected the escalated action; it will not proceed.")}
    intent = get_mandate()
    action = {**e["action"], "re_consent_for": entry_id}
    extra = {"intent_signature": intent["signature"]}
    if approved:                                   # AP2: a human-approved REVIEW earns a Cart Mandate
        extra["cart_mandate"] = cart_mandate(intent, e["action"])
        ap2 = ap2_layer.issue_for_override(intent["constraints"], e["action"])
        if ap2:
            extra["ap2"] = ap2
    new_id = log_provenance(e["mandate_id"], action, audit_like,
                            delegation=delegation_for(intent, e["action"]), extra=extra)
    return jsonify({"verdict": verdict, "provenance_id": new_id})


@app.route("/approve/<entry_id>", methods=["POST"])
def approve(entry_id):
    return _resolve_review(entry_id, True)


@app.route("/reject/<entry_id>", methods=["POST"])
def reject(entry_id):
    return _resolve_review(entry_id, False)



# ---------------------------------------------------------------------------------------------------------------
# Integration endpoint: any agent (or form) asks "may I do this?" and gets a verdict, an AP2 chain and a receipt.
_TYPES = {"book_flight": "supplier-agent-1", "book_hotel": "hotel-supplier-1", "book_transport": "transport-supplier-1"}
_DECISION = {"MATCH": "allow", "REVIEW": "escalate", "DRIFT": "block"}


def _validate_action(a, default_destination):
    """Whitelist + bound every field a caller can send; the auditor only ever sees a clean, size-limited action."""
    if not isinstance(a, dict) or a.get("type") not in _TYPES:
        raise ValueError("action.type must be one of " + ", ".join(_TYPES))
    try:
        price = float(a.get("price"))
    except (TypeError, ValueError):
        raise ValueError("action.price must be a number")
    if not 0 <= price <= 1_000_000:
        raise ValueError("action.price out of range")
    out = {"type": a["type"], "supplier": _clean(a.get("supplier") or _TYPES[a["type"]], 40),
           "vendor": _clean(a.get("vendor") or "", 60), "price": int(price) if price.is_integer() else price,
           "destination": _clean(a.get("destination") or default_destination, 40)}
    if not out["vendor"]:
        raise ValueError("action.vendor is required")
    if a.get("class"):
        out["class"] = _clean(a["class"], 20).lower()
    if isinstance(a.get("refundable"), bool):
        out["refundable"] = a["refundable"]
    if a.get("note"):
        out["note"] = _clean(a["note"], 200)
    if isinstance(a.get("charges"), list):
        out["charges"] = [float(x) for x in a["charges"][:5] if isinstance(x, (int, float))]
    if isinstance(a.get("extra_charges"), list):
        out["extra_charges"] = [{"item": _clean(x.get("item", "extra"), 60), "amount": float(x.get("amount", 0))}
                                for x in a["extra_charges"][:5] if isinstance(x, dict)]
    return out


@app.route("/v1/authorize", methods=["POST", "OPTIONS"])
@limited
def v1_authorize():
    """POST {action, requester?, request?, correct?} -> {decision, verdict, explanation, violations, counterfactual, ap2,
    cart_mandate, provenance_id, steps}. Optional API key: set ANVIL_API_KEY and send X-Anvil-Key."""
    if request.method == "OPTIONS":
        return ("", 204)
    key = os.environ.get("ANVIL_API_KEY")
    if key and request.headers.get("X-Anvil-Key") != key:
        return jsonify({"error": "missing or wrong X-Anvil-Key"}), 401
    intent = _verified_intent()
    if not intent:
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    body = request.get_json(silent=True) or {}
    try:
        action = _validate_action(body.get("action"), intent["constraints"]["destination"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    steps = [e["step"] for e in run_stream(intent, [(action, "submitted via /v1/authorize", None)], body.get("request"),
                                           requester=body.get("requester"), origin="user",
                                           max_corrections=2 if body.get("correct", True) else 0) if e["event"] == "step"]
    final = steps[-1]
    a = final["audit"]
    return jsonify({"decision": _DECISION.get(a["verdict"], "block"), "verdict": a["verdict"], "severity": a["severity"],
                    "explanation": a["explanation"], "violations": a["violations"], "counterfactual": final.get("counterfactual"),
                    "ap2": a.get("ap2"), "cart_mandate": final.get("cart_mandate"), "provenance_id": final.get("provenance_id"),
                    "corrected": len(steps) > 1, "steps": steps})


# ---------------------------------------------------------------------------------------------------------------
# Simulated live traffic: browsers with the Live tab open ask for a tick; a global lease keeps it to one at a time.
SIM_MIN_GAP_S = int(os.environ.get("ANVIL_SIM_MIN_GAP_S", "20"))
SIM_DAILY_CAP = int(os.environ.get("ANVIL_SIM_DAILY_CAP", "1500"))
SIM_REQUESTERS = ["Priya S.", "Arjun K.", "Meera N.", "Rohan D.", "Kavya R.", "Imran A."]
SIM_PLAN = [(44, "scenario", "trip"),
            (14, "request", "Book my Mumbai trip with the cheapest options that fit our travel policy."),
            (8, "request", "I have a brutal week ahead. Book me business class on Emirates and the best hotel you can find."),
            (6, "request", "Cheapest possible everything, I don't care about refunds or the usual suppliers."),
            (8, "scenario", "Over-cap"), (5, "scenario", "Fare split"), (5, "scenario", "Unrelated add-on"),
            (4, "scenario", "Adversarial: fake pre-approval"), (3, "scenario", "Adversarial: prompt injection"), (3, "scenario", "business")]


@app.route("/api/sim/tick", methods=["POST", "OPTIONS"])
def sim_tick():
    """Run ONE simulated agent request through the real pipeline (labelled origin=simulated). Returns when it is done."""
    if request.method == "OPTIONS":
        return ("", 204)
    lease = sim_lease(SIM_MIN_GAP_S, SIM_DAILY_CAP)
    if not lease["ok"]:
        return jsonify({"ran": False, **lease})
    intent = _verified_intent()
    if not intent:
        return jsonify({"ran": False, "reason": "mandate signature invalid"}), 403
    _, kind, what = random.choices(SIM_PLAN, weights=[w for w, _, _ in SIM_PLAN])[0]
    who = random.choice(SIM_REQUESTERS)
    mandate = intent["constraints"]
    try:
        if kind == "scenario":
            proposals, text = _scenario_proposals(mandate, what), None
        else:
            gathered = planner.gather_offers(mandate)
            try:
                plan, meta = planner.choose(mandate, what, gathered)
            except Exception:
                plan, meta = planner.fallback(mandate), None
            proposals, text = [(a, why, meta if i == 0 else None) for i, (a, why) in enumerate(plan)], what
        steps = sum(1 for e in run_stream(intent, proposals, text, requester=who, origin="simulated") if e["event"] == "step")
    except Exception as e:
        return jsonify({"ran": False, "reason": f"{type(e).__name__}: {str(e)[:120]}"}), 200
    return jsonify({"ran": True, "requester": who, "what": text or what, "steps": steps, **lease})


@app.route("/api/eval")
def api_eval():
    """Scoreboard. Cached in Firestore (one Gemini call per scenario per repeat); ?refresh=1 recomputes, &repeats=N measures stability."""
    from anvil.eval import run_eval
    ref = db().collection("meta").document("eval_latest")
    if not request.args.get("refresh"):
        cached = ref.get()
        if cached.exists:
            return jsonify(cached.to_dict()["result"])
    result = run_eval(repeats=max(1, min(int(request.args.get("repeats", 1)), 5)))
    ref.set({"result": result, "ts": datetime.now(timezone.utc).isoformat()})
    return jsonify(result)


def _recent_entries(limit=500):
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": d.id, **d.to_dict()} for d in q.stream()]


@app.route("/api/impact")
def api_impact():
    """Prevented-spend rollup from the counterfactual receipts, scoped to the current session."""
    since = get_controls().get("session_start") or ""
    return jsonify(impact_summary([e for e in _recent_entries() if e["ts"] >= since and e["verdict"] in ("MATCH", "REVIEW", "DRIFT")]))


@app.route("/api/metrics")
def api_metrics():
    """Governance console data: agent scorecards, cost of governance, budget burn, drift analytics, controls."""
    mandate = get_mandate().get("constraints")
    return jsonify(metrics_summary(_recent_entries(), get_controls(), mandate))


@app.route("/api/control", methods=["POST", "OPTIONS"])
def api_control():
    """Operator controls: pause/resume an agent, revoke/restore the mandate, start a fresh demo session.
    Each change is appended to the provenance chain, so the controls themselves are auditable."""
    if request.method == "OPTIONS":
        return ("", 204)
    body = request.get_json(silent=True) or {}
    act, agent = body.get("action"), body.get("agent")
    from data.store import CONTROL_TTL_S, _raw_controls
    raw, now = _raw_controls(), time.time()
    paused_until = dict(raw.get("paused_until") or {})
    if act in ("pause", "resume") and agent in ("flight", "hotel", "transport"):
        if act == "pause":
            paused_until[agent] = now + CONTROL_TTL_S
        else:
            paused_until.pop(agent, None)
        changes = {"paused_until": paused_until}
        note = f"{agent} agent {'paused' if act == 'pause' else 'resumed'} by the manager" + (f" (auto-resumes in {CONTROL_TTL_S}s)" if act == "pause" else "")
    elif act in ("revoke", "restore"):
        changes = {"revoked_until": now + CONTROL_TTL_S if act == "revoke" else 0}
        note = f"mandate {'revoked' if act == 'revoke' else 'restored'} by the manager" + (f" (auto-restores in {CONTROL_TTL_S}s)" if act == "revoke" else "")
    elif act == "new_session":
        changes, note = {"session_start": datetime.now(timezone.utc).isoformat()}, "new demo session started (earlier history is kept in the chain)"
    else:
        return jsonify({"error": "unknown control"}), 400
    state = set_controls(**changes)
    log_provenance("mandate-001", {"type": "control", "control": act, "agent": agent},
                   {"verdict": "CONTROL", "severity": "none", "violations": [], "explanation": note.capitalize() + "."})
    return jsonify(state)


@app.route("/api/evidence")
def api_evidence():
    """Audit-ready evidence pack for the current session: mandate, every decision, receipts, chain status."""
    controls, intent = get_controls(), get_mandate()
    since = controls.get("session_start") or ""
    entries = sorted([e for e in _recent_entries() if e["ts"] >= since], key=lambda e: e["ts"])
    ok, broken = verify_chain()
    pack = {"generated": datetime.now(timezone.utc).isoformat(), "mandate": intent, "signature_valid": verify_mandate(intent),
            "chain_ok": ok, "chain_broken_at": broken, "controls": controls, "entries": entries,
            "metrics": metrics_summary(entries, controls, intent.get("constraints"))}
    pack["pack_sha256"] = hashlib.sha256(json.dumps(pack, sort_keys=True, default=str).encode()).hexdigest()
    return Response(json.dumps(pack, indent=2, default=str), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=anvil-evidence-pack.json"})


@app.route("/api/a2a")
def api_a2a():
    """Which A2A client the buyer agents are using (official a2a-sdk vs the built-in fallback)."""
    from agents import a2a
    return jsonify(a2a.status())


@app.route("/api/ap2")
def api_ap2():
    """Status of the official-AP2-SDK layer: enabled?, the manager-signed open mandates, key ids."""
    return jsonify(ap2_layer.get().status())


@app.route("/api/ap2/verify/<entry_id>")
def api_ap2_verify(entry_id):
    """Independently re-verify a stored AP2 chain with the SDK (does not trust the stored summary)."""
    doc = db().collection("provenance").document(entry_id).get()
    if not doc.exists:
        return jsonify({"error": "no such provenance entry"}), 404
    ap2 = (doc.to_dict() or {}).get("ap2") or {}
    L = ap2_layer.get()
    if not ap2.get("chain_token"):
        return jsonify({"error": "this entry has no AP2 chain"}), 400
    if not L.enabled:
        return jsonify({"error": "AP2 layer is not enabled on this server"}), 503
    try:
        return jsonify(L.reverify(ap2["chain_token"], ap2["aud"], ap2["nonce"]))
    except Exception as e:
        return jsonify({"verified": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}), 200


@app.route("/api/mandate")
def api_mandate():
    intent = get_mandate()
    return jsonify({"mandate": intent, "signature_valid": verify_mandate(intent)})


@app.route("/api/mandate/tampered")
def api_mandate_tampered():
    """Demo: a copy of the mandate with one term changed must fail verification."""
    forged = json.loads(json.dumps(get_mandate()))
    old = forged["constraints"]["max_flight_price_usd"]
    forged["constraints"]["max_flight_price_usd"] = 99999
    return jsonify({"changed": f"max_flight_price_usd: {old} -> 99999", "signature_valid": verify_mandate(forged)})


@app.route("/api/verify")
def api_verify():
    ok, broken_at = verify_chain()
    return jsonify({"chain_ok": ok, "broken_at": broken_at})


@app.route("/api/verify/tamper")
def api_verify_tamper():
    """Demo: re-verify the chain with ONE entry's text altered in memory (nothing is written) and show where it breaks."""
    from data.store import _hashed_entries, verify_entries
    entries = _hashed_entries()
    target = request.args.get("id") or (max(entries, key=lambda i: entries[i]["ts"]) if entries else None)
    if target not in entries:
        return jsonify({"error": "no such entry"}), 404
    forged = {k: json.loads(json.dumps(v)) for k, v in entries.items()}
    forged[target]["explanation"] = "EDITED AFTER THE FACT"
    ok, broken = verify_entries(forged)
    return jsonify({"tampered_entry": target, "chain_ok": ok, "broken_at": broken})


@app.route("/api/provenance")
def api_provenance():
    return jsonify(list_provenance())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
