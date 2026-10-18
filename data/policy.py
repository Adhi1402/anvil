"""Editable company policy. The finance manager changes limits and trip rules; every change is validated, re-signed as a new
version of the Intent Mandate, kept in a version history and written to the tamper-evident audit chain.

The signed document is the single source of truth: spending limits live in `constraints`, trip rules in `trip_rules`, both covered
by the same signature, so nothing the model or an agent sees can differ from what finance approved."""
import json
from datetime import date, datetime, timezone

from anvil import trip as T

KNOWN_AIRLINES = ["Air India", "IndiGo", "Vistara", "Akasa Air", "SpiceJet", "Emirates", "Singapore Airlines"]
CLASSES = ["economy", "premium economy", "business"]
LIMITS = {                          # field -> (label, minimum, maximum)
    "max_flight_price_usd": ("Flight limit (USD, per flight)", 50, 20000),
    "max_hotel_per_night_usd": ("Hotel limit (USD, per night)", 20, 5000),
    "max_transport_usd": ("Ground transport limit (USD, per ride)", 5, 2000),
}
RULES = {"min_advance_days": ("Notice before departure (days)", 0, 60), "max_trip_days": ("Longest trip (days)", 1, 90)}


def default_rules():
    return {"min_advance_days": T.POLICY["min_advance_days"], "max_trip_days": T.POLICY["max_trip_days"], "destinations": list(T.CITIES)}


def rules_of(intent):
    r = intent.get("trip_rules") or {}
    d = default_rules()
    return {"min_advance_days": r.get("min_advance_days", d["min_advance_days"]), "max_trip_days": r.get("max_trip_days", d["max_trip_days"]),
            "destinations": [c for c in r.get("destinations", d["destinations"]) if c in T.CITIES]}


def _int(v, label, lo, hi):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a whole number")
    if not lo <= n <= hi:
        raise ValueError(f"{label} must be between {lo} and {hi}")
    return n


def validate(constraints_in, rules_in):
    """Returns (constraint_changes, rule_changes) with clean types, or raises ValueError with a message a person can act on."""
    c, r = {}, {}
    for k, (label, lo, hi) in LIMITS.items():
        if k in (constraints_in or {}):
            c[k] = _int(constraints_in[k], label, lo, hi)
    ci = constraints_in or {}
    if "flight_class" in ci:
        if ci["flight_class"] not in CLASSES:
            raise ValueError("Flight class must be economy, premium economy or business")
        c["flight_class"] = ci["flight_class"]
    if "preferred_airlines" in ci:
        a = [x for x in ci["preferred_airlines"] if x in KNOWN_AIRLINES] if isinstance(ci["preferred_airlines"], list) else []
        if not a:
            raise ValueError("Choose at least one preferred airline")
        c["preferred_airlines"] = a
    if "refundable_required" in ci:
        c["refundable_required"] = bool(ci["refundable_required"])
    if "book_by" in ci:
        try:
            d = date.fromisoformat(str(ci["book_by"])[:10])
        except ValueError:
            raise ValueError("Book-by must be a date")
        if d < date.today():
            raise ValueError("Book-by cannot be in the past")
        c["book_by"] = d.isoformat()
    ri = rules_in or {}
    for k, (label, lo, hi) in RULES.items():
        if k in ri:
            r[k] = _int(ri[k], label, lo, hi)
    if "destinations" in ri:
        dests = [x for x in ri["destinations"] if x in T.CITIES] if isinstance(ri["destinations"], list) else []
        if not dests:
            raise ValueError("Approve at least one destination")
        r["destinations"] = [x for x in T.CITIES if x in dests]
    return c, r


def _fmt(v):
    return ", ".join(v) if isinstance(v, list) else ("yes" if v is True else "no" if v is False else str(v))


NAMES = {**{k: v[0].split(" (")[0].lower() for k, v in LIMITS.items()}, "flight_class": "flight class", "preferred_airlines": "preferred airlines",
         "refundable_required": "refundable required", "book_by": "book-by date", "min_advance_days": "notice period",
         "max_trip_days": "longest trip", "destinations": "approved destinations"}


def diff(old_c, new_c, old_r, new_r):
    out = []
    for k, v in new_c.items():
        if old_c.get(k) != v:
            out.append(f"{NAMES.get(k, k)}: {_fmt(old_c.get(k))} → {_fmt(v)}")
    for k, v in new_r.items():
        if old_r.get(k) != v:
            if k == "destinations":
                add, rem = [x for x in v if x not in old_r[k]], [x for x in old_r[k] if x not in v]
                out.append("approved destinations: " + "; ".join(([f"added {', '.join(add)}"] if add else []) + ([f"removed {', '.join(rem)}"] if rem else [])))
            else:
                out.append(f"{NAMES.get(k, k)}: {old_r.get(k)} → {v}")
    return out


def apply(db, intent, editor, comment, constraints_in, rules_in, base_version, sign, new_intent, log):
    """Validate, version, re-sign, store, and write to the audit chain. Returns (new_intent, changes). `db`, `sign`, `new_intent` and `log`
    are injected (data.store functions) to keep this module free of storage details."""
    cur_v = int(intent.get("version") or 1)
    if base_version is not None and int(base_version) != cur_v:
        raise PermissionError(f"The policy changed while you were editing (now version {cur_v}). Reload and try again.")
    c_changes, r_changes = validate(constraints_in, rules_in)
    old_c, old_r = intent["constraints"], rules_of(intent)
    changes = diff(old_c, c_changes, old_r, r_changes)
    if not changes:
        raise ValueError("Nothing changed.")
    if not str(comment or "").strip():
        raise ValueError("Say why you are changing the policy: it is recorded with the change.")
    new_c, new_r = {**old_c, **c_changes}, {**old_r, **r_changes}
    m = new_intent(f"{editor} (finance manager)", new_c, intent["mandateId"])
    m.pop("signature", None)
    m.update({"version": cur_v + 1, "trip_rules": new_r, "expiresAt": intent.get("expiresAt", m["expiresAt"]), "previous_signature": intent.get("signature", "")})
    sign(m)
    db().collection("mandates").document(m["mandateId"]).set(m)
    now = datetime.now(timezone.utc).isoformat()
    db().collection("policy_versions").document(f"v{m['version']:04d}").set(
        {"version": m["version"], "ts": now, "editor": editor, "comment": str(comment).strip()[:300], "changes": changes,
         "constraints": new_c, "trip_rules": new_r, "signature": m["signature"]})
    log(m["mandateId"], {"type": "control", "control": "policy_update", "agent": None, "version": m["version"]},
        {"verdict": "CONTROL", "severity": "none", "violations": [],
         "explanation": f"Policy version {m['version']} signed by {editor}: " + "; ".join(changes) + f". Reason: {str(comment).strip()[:200]}"},
        extra={"requester": editor, "approver": editor, "comment": str(comment).strip()[:300]})
    return m, changes


def history(db, limit=25):
    q = db().collection("policy_versions").order_by("version", direction="DESCENDING").limit(limit)
    return [d.to_dict() for d in q.stream()]
