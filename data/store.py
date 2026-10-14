"""Firestore access: mandates + provenance (append-only audit log)."""
import os, json, hmac, hashlib
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
    "allowed_suppliers": ["supplier-agent-1"],
    "max_hotel_per_night_usd": 300,
    "refundable_required": True,
    "book_by": "2026-11-01",
}


def seed_mandate(mandate=DEMO_MANDATE):
    mandate = sign_mandate(dict(mandate))
    db().collection("mandates").document(mandate["id"]).set(mandate)
    return mandate


def get_mandate(mandate_id="mandate-001"):
    doc = db().collection("mandates").document(mandate_id).get()
    return doc.to_dict() if doc.exists else seed_mandate()


def _latest_hash():
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(1)
    docs = list(q.stream())
    return docs[0].to_dict().get("hash", "") if docs else "GENESIS"


def log_provenance(mandate_id, action, audit, delegation=None):
    prev = _latest_hash()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mandate_id": mandate_id,
        "action": action,
        "verdict": audit["verdict"], "severity": audit["severity"],
        "violations": audit["violations"], "explanation": audit["explanation"],
        "delegation": delegation or [],
        "prev_hash": prev,
    }
    entry["hash"] = hashlib.sha256((prev + _canonical(entry)).encode()).hexdigest()
    _, ref = db().collection("provenance").add(entry)
    return ref.id


def verify_chain():
    """Walk the log oldest-first. Returns (True, None) or (False, id_of_first_broken_entry).
    Entries logged before hash-chaining existed (no 'hash') are legacy and skipped."""
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.ASCENDING)
    prev = None
    for d in q.stream():
        e = d.to_dict()
        if "hash" not in e:
            continue
        body = {k: v for k, v in e.items() if k != "hash"}
        if prev is not None and e.get("prev_hash") != prev:
            return False, d.id
        if hashlib.sha256((e["prev_hash"] + _canonical(body)).encode()).hexdigest() != e["hash"]:
            return False, d.id
        prev = e["hash"]
    return True, None


def list_provenance(limit=20):
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": d.id, **d.to_dict()} for d in q.stream()]
