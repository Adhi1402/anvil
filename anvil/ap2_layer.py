"""AP2 layer: Google's official AP2 SDK (V2, vendored in ap2/) as a deterministic second gate next to the Gemini audit.

How it fits
- The manager signs one OPEN payment mandate per leg (flight/hotel/transport) with an ES256 key that never lives on the
  server (scripts/ap2_issue.py): AmountRange (the leg's cap) + AllowedPayees (the approved suppliers), bound to the
  orchestrator's public key. The signed tokens are committed in data/ap2_open_mandates.json.
- When Gemini says MATCH, the orchestrator (holding the only private key on the server) presents a CLOSED payment mandate for
  the exact booking; the SDK verifies the whole SD-JWT chain and evaluates the constraints. Constraint violations turn the
  verdict into DRIFT (fail closed) and the normal self-correction loop runs.
- Infrastructure problems (layer not configured, SDK import failure, stale mandates, exceptions) never block an action: they are
  recorded as ap2.error so behaviour without AP2 is exactly the behaviour before AP2 existed.
- A human-approved REVIEW gets a chain too; any constraint violations are recorded as a manager override, not blocked."""
import base64
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path

from anvil.impact import CAP_FIELD, total_usd

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "ap2_open_mandates.json"
KINDS = ("flight", "hotel", "transport")
AUD = "anvil-executor"
SDK_COMMIT = "e1ea56db72a6385bce3e5c1112b3a56ce60acb43"
OPEN_MANDATE_DAYS = 90
log = logging.getLogger("anvil.ap2")


def _sdk():
    """Lazy import so an old Python or a broken dependency disables the layer instead of the app."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from jwcrypto.jwk import JWK
    import ap2.sdk.mandate as mandate_mod
    mandate_mod.LOG_FILE_PATH = "/tmp/ap2-mandate-operations.log"      # the SDK logs to a file; keep it out of the repo tree
    from ap2.sdk.mandate import MandateClient
    from ap2.sdk.payment_mandate_chain import PaymentMandateChain
    from ap2.sdk.generated.open_payment_mandate import AllowedPayees, AmountRange, OpenPaymentMandate
    from ap2.sdk.generated.payment_mandate import PaymentMandate
    from ap2.sdk.generated.types.amount import Amount
    from ap2.sdk.generated.types.merchant import Merchant
    from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
    return {k: v for k, v in locals().items() if k != "mandate_mod"}


def new_key(kid):
    s = _sdk()
    j = json.loads(s["JWK"].from_pyca(s["ec"].generate_private_key(s["ec"].SECP256R1())).export())
    j["kid"] = kid
    return s["JWK"].from_json(json.dumps(j))


def public_dict(jwk):
    return json.loads(jwk.export_public())


def key_to_b64(jwk):
    return base64.b64encode(jwk.export().encode()).decode()


def _merchant(s, supplier_id):
    return s["Merchant"](id=supplier_id, name=supplier_id)


def _cents(usd):
    return int(round(float(usd) * 100))


def issue_open_mandates(constraints, manager_key, orchestrator_public, days=OPEN_MANDATE_DAYS):
    """Manager-side: one signed OPEN payment mandate per leg. Returns the dict stored in data/ap2_open_mandates.json."""
    s = _sdk()
    now = int(time.time())
    payees = list(constraints["allowed_suppliers"])
    mandates, caps = {}, {}
    for kind in KINDS:
        caps[kind] = _cents(constraints[CAP_FIELD["book_" + kind]])
        open_m = s["OpenPaymentMandate"](
            constraints=[s["AmountRange"](currency="USD", max=caps[kind]),
                         s["AllowedPayees"](allowed=[_merchant(s, p) for p in payees])],
            cnf={"jwk": orchestrator_public}, iat=now, exp=now + days * 86400)
        mandates[kind] = s["MandateClient"]().create(payloads=[open_m], issuer_key=manager_key)
    return {"version": 1, "sdk": "google-agentic-commerce/AP2 V2", "sdk_commit": SDK_COMMIT, "issued_at": now, "exp": now + days * 86400,
            "manager_kid": manager_key.get("kid"), "manager_public_jwk": public_dict(manager_key),
            "orchestrator_kid": orchestrator_public.get("kid"), "caps_cents": caps, "payees": payees, "mandates": mandates}


class Layer:
    def __init__(self, enabled=False, reason="", orch_key=None, meta=None):
        self.enabled, self.reason, self.orch_key, self.meta = enabled, reason, orch_key, meta or {}
        self.manager_pub = None
        if enabled:
            self.manager_pub = _sdk()["JWK"].from_json(json.dumps(self.meta["manager_public_jwk"]))

    # ---- issuing / verifying ----
    def _check_fresh(self, kind, constraints):
        cap = _cents(constraints[CAP_FIELD["book_" + kind]])
        if self.meta["caps_cents"].get(kind) != cap or set(self.meta["payees"]) != set(constraints["allowed_suppliers"]):
            raise RuntimeError("stale: open mandates no longer match the Anvil mandate; re-run scripts/ap2_issue.py")
        if self.meta.get("exp", 0) < time.time():
            raise RuntimeError("expired: open mandates have expired; re-run scripts/ap2_issue.py")

    def issue(self, constraints, action):
        """Present a closed payment mandate for this exact booking, verify the chain, return (summary, chain_token)."""
        s = _sdk()
        kind = action["type"].replace("book_", "")
        self._check_fresh(kind, constraints)
        client, nonce, tx = s["MandateClient"](), uuid.uuid4().hex, "anvil-" + uuid.uuid4().hex[:16]
        amount = _cents(total_usd(action))
        closed = s["PaymentMandate"](transaction_id=tx, payee=_merchant(s, action["supplier"]),
                                     payment_amount=s["Amount"](amount=amount, currency="USD"),
                                     payment_instrument=s["PaymentInstrument"](id="corp-card-demo", type="credit"))
        chain = client.present(holder_key=self.orch_key, mandate_token=self.meta["mandates"][kind], payloads=[closed], aud=AUD, nonce=nonce)
        payloads = client.verify(token=chain, key_or_provider=lambda _t: self.manager_pub, expected_aud=AUD, expected_nonce=nonce)
        violations = s["PaymentMandateChain"].parse(payloads).verify()
        summary = {"protocol": "AP2 V2 (SD-JWT)", "verified": True, "violations": violations, "transaction_id": tx,
                   "amount_minor": amount, "payee": action["supplier"], "aud": AUD, "nonce": nonce,
                   "chain_sha256": hashlib.sha256(chain.encode()).hexdigest(), "chain_bytes": len(chain),
                   "issuer_kid": self.meta.get("manager_kid"),
                   "open_mandate": {"max_usd": self.meta["caps_cents"][kind] / 100, "payees": self.meta["payees"]}}
        return summary, chain

    def reverify(self, token, aud, nonce):
        """Independent re-verification of a stored chain with the SDK. Never trusts the stored summary."""
        s = _sdk()
        payloads = s["MandateClient"]().verify(token=token, key_or_provider=lambda _t: self.manager_pub, expected_aud=aud, expected_nonce=nonce)
        chain = s["PaymentMandateChain"].parse(payloads)
        return {"verified": True, "violations": chain.verify(), "payee": chain.closed_mandate.payee.id,
                "amount_minor": chain.closed_mandate.payment_amount.amount, "currency": chain.closed_mandate.payment_amount.currency,
                "transaction_id": chain.closed_mandate.transaction_id, "issuer_kid": self.meta.get("manager_kid"),
                "open_constraints": [c.type for c in chain.open_mandate.constraints]}

    def status(self):
        out = {"enabled": self.enabled, "reason": self.reason, "python": sys.version.split()[0], "sdk_commit": SDK_COMMIT}
        if self.enabled:
            out.update({"issuer_kid": self.meta.get("manager_kid"), "orchestrator_kid": self.meta.get("orchestrator_kid"),
                        "expires": self.meta.get("exp"), "payees": self.meta["payees"],
                        "open_mandates": {k: {"max_usd": self.meta["caps_cents"][k] / 100, "bytes": len(self.meta["mandates"][k])} for k in KINDS}})
        return out


_layer = None


def load():
    """Build the layer from the environment and data file. Any failure yields a disabled layer with the reason."""
    env = os.environ.get("ANVIL_AP2_ORCH_KEY", "").strip()
    if not env:
        return Layer(False, "ANVIL_AP2_ORCH_KEY not set")
    try:
        meta = json.loads(DATA_FILE.read_text())
        orch = _sdk()["JWK"].from_json(base64.b64decode(env).decode())
        return Layer(True, "", orch, meta)
    except Exception as e:                                         # includes ImportError on an unsupported Python
        log.warning("AP2 layer disabled: %s: %s", type(e).__name__, e)
        return Layer(False, f"{type(e).__name__}: {str(e)[:160]}")


def get():
    global _layer
    if _layer is None:
        _layer = load()
    return _layer


def configure(layer):
    """Tests and scripts: install a prepared (or disabled) layer."""
    global _layer
    _layer = layer


def configure_for_tests(constraints):
    manager, orch = new_key("manager-test"), new_key("orchestrator-test")
    meta = issue_open_mandates(constraints, manager, public_dict(orch))
    configure(Layer(True, "", orch, meta))
    return manager


def gate(constraints, action, result):
    """Second gate after the Gemini audit. Returns the (possibly downgraded) audit result."""
    L = get()
    if not L.enabled or result.get("verdict") != "MATCH" or result.get("source") == "control":
        return result
    try:
        summary, token = L.issue(constraints, action)
    except Exception as e:                                         # infrastructure problem: visible, never blocking
        log.warning("AP2 issue failed: %s: %s", type(e).__name__, e)
        return {**result, "ap2": {"enabled": True, "verified": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}}
    if summary["violations"]:
        return {"verdict": "DRIFT", "severity": "high", "source": "ap2-constraints", "telemetry": result.get("telemetry"),
                "violations": ["AP2 constraint: " + v for v in summary["violations"]], "ap2": summary,
                "explanation": "Gemini judged this consistent with the mandate, but the AP2 mandate constraints reject it: "
                               + "; ".join(summary["violations"]) + "."}
    return {**result, "ap2": summary, "ap2_token": token}


def issue_for_override(constraints, action):
    """A human approved a REVIEW: issue a chain and record any constraint violations as a manager override."""
    L = get()
    if not L.enabled:
        return None
    try:
        summary, token = L.issue(constraints, action)
    except Exception as e:
        log.warning("AP2 override issue failed: %s: %s", type(e).__name__, e)
        return {"enabled": True, "verified": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    return {**summary, "manager_override": bool(summary["violations"]), "chain_token": token}
