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


_KIND = {"book_flight": "flight", "book_hotel": "hotel", "book_transport": "transport"}
_CAP = {"book_flight": "max_flight_price_usd", "book_hotel": "max_hotel_per_night_usd",
        "book_transport": "max_transport_usd"}

_PICK_SCHEMA = {"type": "OBJECT", "properties": {"choice": {"type": "INTEGER"}, "rationale": {"type": "STRING"}},
                "required": ["choice", "rationale"]}
_PICK_PROMPT = """You are a booking agent. Your last proposal was BLOCKED by the mandate auditor.
Pick the one OFFER that fixes every violation below while staying inside the mandate, or -1 if none does.
Change only what the violations require; prefer the cheapest compliant offer.

MANDATE:
{mandate}

BLOCKED PROPOSAL:
{action}

VIOLATIONS: {violations}

OFFERS (0-indexed):
{offers}
"""


def _pick_with_gemini(mandate, action, violations, offers):
    """Let Gemini read the auditor's reasons and choose a fix. The pick is still re-audited by the guard."""
    import json
    from google.genai import types
    from anvil.audit import MODEL, _client_
    prompt = _PICK_PROMPT.format(
        mandate=json.dumps(mandate, indent=2), action=json.dumps(action), violations=violations or "(none given)",
        offers="\n".join(f"{i}: {json.dumps(o)}" for i, o in enumerate(offers)))
    cfg = types.GenerateContentConfig(response_mime_type="application/json", response_schema=_PICK_SCHEMA,
                                      temperature=0)
    out = json.loads(_client_().models.generate_content(model=MODEL, contents=prompt, config=cfg).text)
    i = out["choice"]
    return (offers[i], out["rationale"]) if 0 <= i < len(offers) else (None, out["rationale"])


def _rule_pick(mandate, kind, offers):
    """Deterministic fallback if Gemini is unavailable: cheapest offer meeting the mandate's stated terms."""
    ok = [o for o in offers
          if (not mandate.get("refundable_required") or o.get("refundable", True))
          and ("class" not in o or o["class"] == mandate.get("flight_class"))
          and (kind != "flight" or o["vendor"] in mandate.get("preferred_airlines", [o["vendor"]]))]
    return sorted(ok, key=lambda o: o["price"])[0] if ok else None


def replan(mandate, action, violations=""):
    """Correction loop: re-search the same supplier, then choose an offer that fixes the stated violations."""
    kind = _KIND[action["type"]]
    supplier, offers = _offers(kind, {"destination": mandate["destination"], "max_price": mandate.get(_CAP[action["type"]])})
    if not offers:
        return None
    try:
        best, why = _pick_with_gemini(mandate, action, violations, offers)
    except Exception:
        best, why = _rule_pick(mandate, kind, offers), "rule-based fallback (Gemini unavailable)"
    if not best:
        return None
    return {"type": action["type"], "supplier": supplier, "replan_reason": violations,
            "replan_rationale": why, **best}


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
