"""Firestore access: mandates + provenance (append-only audit log)."""
import os, json, hmac, hashlib, time, uuid
from datetime import datetime, timezone
from google.cloud import firestore

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "dazzling-lodge-511607-m0")
_db = None


def db():
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT)
    return _db


SIGNING_KEY = os.environ.get("ANVIL_SIGNING_KEY", "dev-only-key").encode()


def _canonical(d):
    body = {k: v for k, v in d.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def sign_mandate(m):
    m["signature"] = hmac.new(SIGNING_KEY, _canonical(m).encode(), hashlib.sha256).hexdigest()
    return m


def verify_mandate(m):
    expected = hmac.new(SIGNING_KEY, _canonical(m).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(m.get("signature", ""), expected)


DEMO_MANDATE = {
    "id": "mandate-001",
    "signed_by": "manager@example.com",
    "traveler": "Priya",
    "destination": "Mumbai",
    "flight_class": "economy",
    "max_flight_price_usd": 600,
    "preferred_airlines": ["Air India", "IndiGo"],
    "allowed_suppliers": ["supplier-agent-1", "hotel-supplier-1", "transport-supplier-1"],
    "max_hotel_per_night_usd": 300,
    "max_transport_usd": 100,
    "refundable_required": True,
    "book_by": "2026-11-01",
}


def intent_mandate(user, constraints, mandate_id="mandate-001"):
    """AP2 Intent Mandate: the human's signed authorization (see Appendix F2a)."""
    m = {
        "type": "IntentMandate",
        "mandateId": mandate_id,
        "user": user,                     # who authorized (the manager)
        "constraints": constraints,       # destination, class, caps, preferred airlines, refundable, book_by
        "issuedAt": datetime.now(timezone.utc).isoformat(),
        "expiresAt": "2026-11-01T00:00:00Z",
        "nonce": uuid.uuid4().hex,
    }
    return sign_mandate(m)


def cart_mandate(intent, action):
    """AP2 Cart Mandate: signed purchase authorization, issued only after a MATCH (or an approved REVIEW)."""
    c = {
        "type": "CartMandate",
        "cartId": uuid.uuid4().hex,
        "intentMandateId": intent["mandateId"],      # links the booking back to the human approval
        "merchant": action["supplier"],
        "items": [{"name": action.get("vendor"), "kind": action["type"], "amount": action["price"]}],
        "currency": "USD",
        "total": action["price"],
        "authorizedBy": intent["user"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return sign_mandate(c)


def delegation_for(intent, action):
    """Who delegated to whom, all under the single human-signed Intent Mandate."""
    kind = action["type"].replace("book_", "") + "-agent"
    mid = intent["mandateId"]
    return [
        {"from": intent["user"], "to": "trip-orchestrator", "mandate": mid},
        {"from": "trip-orchestrator", "to": kind, "mandate": mid},
        {"from": kind, "to": action["supplier"], "mandate": mid},
    ]


def seed_mandate(mandate=DEMO_MANDATE):
    constraints = {k: v for k, v in mandate.items() if k not in ("id", "signed_by")}
    im = intent_mandate(mandate["signed_by"], constraints, mandate["id"])
    db().collection("mandates").document(im["mandateId"]).set(im)
    return im


def get_mandate(mandate_id="mandate-001"):
    """Returns the signed Intent Mandate. Re-seeds if missing or stored in the pre-AP2 flat shape."""
    doc = db().collection("mandates").document(mandate_id).get()
    m = doc.to_dict() if doc.exists else None
    return m if m and m.get("type") == "IntentMandate" else seed_mandate()


def _hashed_entries():
    """All chained entries (legacy Day-1 entries have no 'hash' and are ignored)."""
    out = {}
    for d in db().collection("provenance").stream():
        e = d.to_dict()
        if "hash" in e:
            out[d.id] = e
    return out


def _latest_hash():
    """Chain tip = the entry no other entry points at. Found by hash links, NOT timestamps,
    so clock skew between writers (laptops vs Cloud Run) can't fork the chain."""
    entries = _hashed_entries()
    if not entries:
        return "GENESIS"
    pointed_at = {e["prev_hash"] for e in entries.values()}
    tips = [e for e in entries.values() if e["hash"] not in pointed_at]
    return max(tips, key=lambda e: e["ts"])["hash"]


def _tip_ref():
    return db().collection("meta").document("chain_tip")


def _ensure_tip():
    """One-time bootstrap: the stored chain tip starts from the scan result (or GENESIS). After that, appends never scan."""
    if not _tip_ref().get().exists:
        _tip_ref().set({"hash": _latest_hash()})


def _run_txn(work):
    """Run work(txn) atomically (Firestore transaction, or the in-memory test double)."""
    client = db()
    if hasattr(client, "atomic"):                      # in-memory test double
        return client.atomic(work)
    return firestore.transactional(work)(client.transaction())


def _append(build):
    """Atomically read the chain tip, build the next entry on top of it, and write entry + new tip.
    Two writers (two judges, two instances) can never both extend the same tip, so the chain cannot fork,
    and an append costs O(1) reads however long the log is."""
    client = db()

    def work(txn):
        tip = _tip_ref().get(transaction=txn).to_dict()["hash"]
        entry = build(tip)
        new_ref = client.collection("provenance").document()
        txn.set(new_ref, entry)
        txn.set(_tip_ref(), {"hash": entry["hash"], "ts": entry["ts"]})
        return new_ref.id

    return _run_txn(work)


def sim_lease(min_gap_s, daily_cap, now=None):
    """Global lease for simulated traffic: however many browsers ask, at most one tick per min_gap_s and daily_cap per day."""
    now = now or time.time()
    day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
    ref = db().collection("meta").document("sim")

    def work(txn):
        d = ref.get(transaction=txn).to_dict() or {}
        count = d.get("count", 0) if d.get("day") == day else 0
        if now - d.get("last", 0) < min_gap_s:
            return {"ok": False, "reason": "too soon", "wait_s": round(min_gap_s - (now - d["last"]), 1)}
        if count >= daily_cap:
            return {"ok": False, "reason": "daily cap reached"}
        txn.set(ref, {"last": now, "day": day, "count": count + 1})
        return {"ok": True, "count_today": count + 1}

    return _run_txn(work)


def log_provenance(mandate_id, action, audit, delegation=None, extra=None):
    _ensure_tip()

    def build(prev):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mandate_id": mandate_id,
            "action": action,
            "verdict": audit["verdict"], "severity": audit["severity"],
            "violations": audit["violations"], "explanation": audit["explanation"],
            "delegation": delegation or [],
            "prev_hash": prev,
        }
        entry.update(extra or {})                 # e.g. cart_mandate, intent_signature
        entry["hash"] = hashlib.sha256((prev + _canonical(entry)).encode()).hexdigest()
        return entry

    return _append(build)


def verify_chain():
    """Returns (True, None) or (False, id_of_first_broken_entry).
    Checks every entry's own hash, then that the entries form ONE unbroken line (no forks, no gaps)."""
    return verify_entries(_hashed_entries())


def verify_entries(entries):
    for id_, e in entries.items():
        body = {k: v for k, v in e.items() if k != "hash"}
        if hashlib.sha256((e["prev_hash"] + _canonical(body)).encode()).hexdigest() != e["hash"]:
            return False, id_
    by_hash = {e["hash"]: id_ for id_, e in entries.items()}
    children = {}
    for id_, e in entries.items():
        children.setdefault(e["prev_hash"], []).append(id_)
    for kids in children.values():
        if len(kids) > 1:                                   # fork
            return False, sorted(kids, key=lambda i: entries[i]["ts"])[1]
    roots = [i for i, e in entries.items() if e["prev_hash"] not in by_hash]
    if len(roots) > 1:                                      # gap: an entry's parent is missing
        return False, sorted(roots, key=lambda i: entries[i]["ts"])[1]
    return True, None


def list_provenance(limit=20):
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": d.id, **d.to_dict()} for d in q.stream()]


# ---- operator controls (kill switch + demo session marker). Changes are logged to the provenance chain. ----
CONTROL_TTL_S = int(os.environ.get("ANVIL_CONTROL_TTL_S", "180"))


def _raw_controls():
    doc = db().collection("controls").document("state").get()
    return doc.to_dict() if doc.exists else {}


def get_controls():
    """Effective controls. Pauses and revocations AUTO-EXPIRE (default 3 min) so one visitor cannot leave a shared demo
    blocked for everyone. Production: per-tenant controls with no expiry."""
    d, now = _raw_controls(), time.time()
    paused_until = {k: v for k, v in (d.get("paused_until") or {}).items() if v > now}
    revoked_until = d.get("revoked_until", 0)
    return {"paused_agents": sorted(paused_until), "mandate_revoked": revoked_until > now,
            "paused_until": paused_until, "revoked_until": revoked_until if revoked_until > now else 0,
            "ttl_s": CONTROL_TTL_S, "session_start": d.get("session_start", "")}


def set_controls(**changes):
    db().collection("controls").document("state").set({**_raw_controls(), **changes})
    return get_controls()
