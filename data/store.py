"""Firestore access: mandates + provenance (append-only audit log)."""
import os
from datetime import datetime, timezone
from google.cloud import firestore

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "dazzling-lodge-511607-m0")
_db = None


def db():
    global _db
    if _db is None:
        _db = firestore.Client(project=PROJECT)
    return _db


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
    db().collection("mandates").document(mandate["id"]).set(mandate)
    return mandate


def get_mandate(mandate_id="mandate-001"):
    doc = db().collection("mandates").document(mandate_id).get()
    return doc.to_dict() if doc.exists else seed_mandate()


def log_provenance(mandate_id, action, audit):
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mandate_id": mandate_id,
        "action": action,
        "verdict": audit["verdict"],
        "severity": audit["severity"],
        "violations": audit["violations"],
        "explanation": audit["explanation"],
    }
    _, ref = db().collection("provenance").add(entry)
    return ref.id


def list_provenance(limit=20):
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": d.id, **d.to_dict()} for d in q.stream()]
