"""Travel agent <-> supplier agent exchange one A2A-style message; yields a proposed action."""
import uuid

SUPPLIER_ID = "supplier-agent-1"
INVENTORY = [
    {"vendor": "Air India", "price": 480, "class": "economy", "refundable": True, "destination": "Mumbai"},
    {"vendor": "Air India", "price": 520, "class": "economy", "refundable": True, "destination": "Mumbai"},
    {"vendor": "IndiGo", "price": 430, "class": "economy", "refundable": False, "destination": "Mumbai"},
]


def message(sender, to, kind, body):
    return {"id": str(uuid.uuid4()), "from": sender, "to": to, "type": kind, "body": body}


def supplier_agent(msg):
    """Hard-coded supplier: replies to a flight query with its options."""
    q = msg["body"]
    offers = [o for o in INVENTORY if o["destination"] == q["destination"] and o["price"] <= q["max_price"]]
    return message(SUPPLIER_ID, msg["from"], "flight_offers", {"offers": offers})


def travel_agent(mandate):
    query = message("travel-agent", SUPPLIER_ID, "flight_query",
                    {"destination": mandate["destination"], "max_price": mandate["max_flight_price_usd"]})
    reply = supplier_agent(query)
    offers = reply["body"]["offers"]
    if not offers:
        return None
    best = sorted(offers, key=lambda o: (mandate.get("refundable_required") and not o["refundable"],
                                           o["vendor"] not in mandate["preferred_airlines"], o["price"]))[0]
    return {"type": "book_flight", "supplier": reply["from"], **best}


def replan(mandate, reason=""):
    """Strict planner: honor class, preferred airlines, refundability, cap. Used after a block."""
    query = message("travel-agent", SUPPLIER_ID, "flight_query",
                    {"destination": mandate["destination"], "max_price": mandate["max_flight_price_usd"]})
    offers = supplier_agent(query)["body"]["offers"]
    compliant = [o for o in offers
                 if o["class"] == mandate["flight_class"]
                 and o["vendor"] in mandate["preferred_airlines"]
                 and (not mandate.get("refundable_required") or o["refundable"])
                 and o["price"] <= mandate["max_flight_price_usd"]]
    if not compliant:
        return None
    best = sorted(compliant, key=lambda o: o["price"])[0]
    return {"type": "book_flight", "supplier": SUPPLIER_ID, "replan_reason": reason, **best}


if __name__ == "__main__":
    import json
    from data.store import DEMO_MANDATE
    print(json.dumps(travel_agent(DEMO_MANDATE), indent=2))
