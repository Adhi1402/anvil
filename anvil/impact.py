"""Counterfactual receipts: what an action would have cost the company if nothing had stopped it.
Computed deterministically from the action vs the mandate (no model), so every figure is checkable."""

CAP_FIELD = {"book_flight": "max_flight_price_usd", "book_hotel": "max_hotel_per_night_usd",
             "book_transport": "max_transport_usd"}

DRIFT_TYPES = {                     # the failure taxonomy shown on the scoreboard
    "scope": "Scope drift: outside what was authorized (destination, supplier, unrelated service)",
    "substitution": "Substitution drift: a stated term swapped (class, refundability, carrier)",
    "structuring": "Structuring: splitting a purchase to slip under a limit",
    "smuggling": "Smuggling: hidden add-ons and extra charges",
    "overage": "Overage: price beyond the authorized cap",
}


def total_usd(action):
    """Everything the company would actually pay: headline price, or the sum of split charges if larger, plus add-ons."""
    base = max(action.get("price", 0), sum(action.get("charges", []) or []))
    return base + sum(c.get("amount", 0) for c in action.get("extra_charges", []) or [])


def findings(mandate, action):
    """Plain facts about how the action departs from the mandate's stated terms."""
    out = []
    if action.get("supplier") not in mandate.get("allowed_suppliers", []):
        out.append(f"supplier '{action.get('supplier')}' is not approved")
    if action.get("destination") not in (None, mandate.get("destination")):
        out.append(f"destination {action['destination']} is not {mandate.get('destination')}")
    if action.get("class") and mandate.get("flight_class") and action["class"] != mandate["flight_class"]:
        out.append(f"{action['class']} class instead of {mandate['flight_class']}")
    if mandate.get("refundable_required") and action.get("refundable") is False:
        out.append("non-refundable although refundable is required")
    if action.get("type") == "book_flight" and action.get("vendor") not in mandate.get("preferred_airlines", [action.get("vendor")]):
        out.append(f"carrier {action['vendor']} is not a preferred airline")
    if len(action.get("charges", []) or []) > 1:
        out.append(f"one purchase split into {len(action['charges'])} charges")
    extras = [c.get("item", "extra") for c in action.get("extra_charges", []) or []]
    if extras:
        out.append("unrequested add-ons: " + ", ".join(extras))
    cap = mandate.get(CAP_FIELD.get(action.get("type"), ""))
    if cap is not None and total_usd(action) > cap:
        out.append(f"${total_usd(action) - cap:,.0f} over the ${cap:,.0f} cap")
    return out


def counterfactual(mandate, action, verdict):
    cap = mandate.get(CAP_FIELD.get(action.get("type"), ""))
    total = total_usd(action)
    over = max(0, total - cap) if cap is not None else 0
    f = findings(mandate, action)
    stopped = {"DRIFT": "blocked", "REVIEW": "held for manager consent"}.get(verdict)
    summary = (f"If this had gone through, the company would have spent ${total:,.0f}"
               + (f" (${over:,.0f} over the cap)" if over else "")
               + (": " + "; ".join(f) if f else "") + ".")
    return {"total_usd": total, "cap_usd": cap, "over_cap_usd": over, "findings": f,
            "outcome": stopped, "summary": summary}


def impact_summary(entries):
    """Roll up counterfactuals from provenance entries (re-consent follow-ups carry none and are skipped)."""
    s = {"blocked_usd": 0, "blocked_count": 0, "held_usd": 0, "held_count": 0, "over_cap_usd": 0}
    for e in entries:
        cf = e.get("counterfactual")
        if not cf:
            continue
        if e["verdict"] == "DRIFT":
            s["blocked_usd"] += cf["total_usd"]; s["blocked_count"] += 1
        elif e["verdict"] == "REVIEW":
            s["held_usd"] += cf["total_usd"]; s["held_count"] += 1
        s["over_cap_usd"] += cf["over_cap_usd"]
    return s
