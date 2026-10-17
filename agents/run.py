"""Buyer-side agents. They DISCOVER supplier agents via Agent Cards and talk A2A (JSON-RPC)."""
from agents.a2a import discover, send, clear_discovery

TRIP_ORCHESTRATOR = "trip-orchestrator"


def _offers(agent, data):
    result = send(discover(agent), data)[1]
    return result["supplier"], result["offers"]


def travel_agent(mandate):
    supplier, offers = _offers("flight", {"destination": mandate["destination"],
                                          "max_price": mandate["max_flight_price_usd"]})
    if not offers:
        return None
    best = sorted(offers, key=lambda o: (mandate.get("refundable_required") and not o["refundable"],
                                         o["vendor"] not in mandate["preferred_airlines"], o["price"]))[0]
    return {"type": "book_flight", "supplier": supplier, **best}


def replan(mandate, reason=""):
    """Strict planner: honor class, preferred airlines, refundability, cap. Used after a block."""
    supplier, offers = _offers("flight", {"destination": mandate["destination"],
                                          "max_price": mandate["max_flight_price_usd"]})
    compliant = [o for o in offers
                 if o["class"] == mandate["flight_class"]
                 and o["vendor"] in mandate["preferred_airlines"]
                 and (not mandate.get("refundable_required") or o["refundable"])
                 and o["price"] <= mandate["max_flight_price_usd"]]
    if not compliant:
        return None
    best = sorted(compliant, key=lambda o: o["price"])[0]
    return {"type": "book_flight", "supplier": supplier, "replan_reason": reason, **best}


def hotel_agent(mandate):
    cap = mandate["max_hotel_per_night_usd"]
    supplier, offers = _offers("hotel", {"destination": mandate["destination"], "max_price": cap})
    opts = [h for h in offers if h["price"] <= cap
            and (not mandate.get("refundable_required") or h["refundable"])]
    if not opts:
        return None
    best = sorted(opts, key=lambda h: h["price"])[0]
    return {"type": "book_hotel", "supplier": supplier, **best}


def transport_agent(mandate):
    supplier, offers = _offers("transport", {"destination": mandate["destination"],
                                             "max_price": mandate.get("max_transport_usd")})
    return {"type": "book_transport", "supplier": supplier, **offers[0]} if offers else None


def plan_trip(mandate):
    """One mandate dispatches three sub-agents over A2A. Discovery runs once, at trip start."""
    clear_discovery()
    for agent in ("flight", "hotel", "transport"):
        discover(agent)
    return [a for a in (travel_agent(mandate), hotel_agent(mandate), transport_agent(mandate)) if a]


if __name__ == "__main__":
    import json
    from data.store import DEMO_MANDATE
    print(json.dumps(plan_trip(DEMO_MANDATE), indent=2))
