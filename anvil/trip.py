"""Trip context: dates, round trips, the legs a trip needs, and the deterministic trip-policy gate.

The signed mandate (caps, suppliers, destination) is unchanged and still judged by the Gemini auditor. Everything a trip adds
(departure and return dates, nights, flight times) travels on each action under SCHEDULE_KEYS, is stripped before the auditor
sees the action (so verdicts and the eval are unaffected) and is judged here, with plain deterministic rules."""
import uuid
from datetime import date, datetime, timedelta, timezone

POLICY = {"min_advance_days": 7, "max_trip_days": 14}
# Cities the company travels to and from. A trip between any two of them is within policy on destination; the signed spending
# limits, refundability, class and supplier rules still apply to every booking. (A real deployment holds this list per grade.)
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Hyderabad", "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Goa", "Dubai", "Singapore"]
ORIGINS = DESTINATIONS = CITIES
AIRPORTS = {"Mumbai": ("BOM", "Chhatrapati Shivaji Intl (BOM)"), "Delhi": ("DEL", "Indira Gandhi Intl (DEL)"), "Bengaluru": ("BLR", "Kempegowda Intl (BLR)"),
            "Chennai": ("MAA", "Chennai Intl (MAA)"), "Hyderabad": ("HYD", "Rajiv Gandhi Intl (HYD)"), "Pune": ("PNQ", "Pune Airport (PNQ)"),
            "Kolkata": ("CCU", "Netaji Subhas Chandra Bose Intl (CCU)"), "Ahmedabad": ("AMD", "Sardar Vallabhbhai Patel Intl (AMD)"), "Jaipur": ("JAI", "Jaipur Intl (JAI)"),
            "Goa": ("GOI", "Dabolim Airport (GOI)"), "Dubai": ("DXB", "Dubai Intl (DXB)"), "Singapore": ("SIN", "Changi Airport (SIN)")}
PURPOSES = ["Client meeting", "Conference or event", "Training", "Internal / team offsite", "Recruiting", "Other"]
COST_CENTERS = {"CC-1042": "Sales, APAC", "CC-2210": "Engineering, Platform", "CC-3105": "Customer Success", "CC-4001": "Leadership"}
PREFS = ("morning", "afternoon", "evening", "any")
# Fields a trip adds to an action. The auditor never sees them; the trip gate and the UI do.
SCHEDULE_KEYS = ("leg", "trip", "flight_no", "from_city", "to_city", "from_code", "to_code", "from_place", "to_place", "route", "depart", "arrive",
                 "check_in", "check_out", "nights", "total", "pickup", "considered")
LEG_ORDER = ["flight_out", "transfer_out", "hotel", "transfer_back", "flight_back"]
LEG_LABEL = {"flight_out": "Outbound flight", "transfer_out": "Airport to hotel", "hotel": "Hotel",
             "transfer_back": "Hotel to airport", "flight_back": "Return flight"}


def policy_action(mandate, action):
    """The auditor's view of a trip booking: the destination is judged by the approved-city list, not by the one city the
    signed mandate happened to be issued for. A destination that is not on the list is left as it is and is still blocked."""
    t = action.get("trip") or {}
    if t.get("destination") in DESTINATIONS and action.get("destination") == t["destination"] and mandate.get("destination"):
        return {**action, "destination": mandate["destination"]}
    return action


def strip(action):
    return {k: v for k, v in action.items() if k not in SCHEDULE_KEYS}


def nights(action):
    return max(1, int(action.get("nights") or 1)) if action.get("type") == "book_hotel" else 1


def stake_usd(total, action):
    """What the company pays for this action: a hotel is priced per night, everything else is a single charge."""
    return total * nights(action)


def _day(s, what):
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        raise ValueError(f"{what} must be a date like 2026-11-03")


def today():
    return datetime.now(timezone.utc).date()


def normalize(t, requester=None):
    """Validate a trip request from a client and return the compact, bounded trip that rides on every action."""
    if not isinstance(t, dict):
        raise ValueError("trip must be an object")
    typ = "one_way" if t.get("type") == "one_way" else "round_trip"
    depart = _day(t.get("depart_date"), "depart_date")
    if depart < today():
        raise ValueError("The departure date is in the past.")
    ret = None
    if typ == "round_trip":
        ret = _day(t.get("return_date"), "return_date")
        if ret < depart:
            raise ValueError("The return date is before the departure date.")
        n = (ret - depart).days
    else:
        n = int(t.get("nights") or 0)
    if n > 90:
        raise ValueError("A trip can be at most 90 days; ask finance for a long-stay authorization.")
    hotel, transport = bool(t.get("hotel", True)), bool(t.get("transport", True))
    if hotel and n < 1:
        raise ValueError("A hotel needs at least one night: choose a later return date or turn the hotel off.")
    origin, dest = str(t.get("origin") or "").strip()[:40], str(t.get("destination") or "").strip()[:40]
    if not origin or not dest:
        raise ValueError("Choose where you are travelling from and to.")
    if origin not in CITIES or dest not in CITIES:
        raise ValueError(f"{dest if dest not in CITIES else origin} is not on the approved city list.")
    if origin.lower() == dest.lower():
        raise ValueError("The origin and destination are the same.")
    pref = lambda k: t.get(k) if t.get(k) in PREFS else "any"
    out = {"id": uuid.uuid4().hex[:8], "type": typ, "origin": origin, "destination": dest, "depart_date": depart.isoformat(),
           "return_date": ret.isoformat() if ret else None, "nights": n if hotel else 0, "hotel": hotel, "transport": transport,
           "depart_pref": pref("depart_pref"), "return_pref": pref("return_pref"),
           "purpose": str(t.get("purpose") or "")[:60], "cost_center": str(t.get("cost_center") or "")[:20],
           "justification": str(t.get("justification") or "")[:300], "traveler": str(t.get("traveler") or requester or "")[:40]}
    return out


def default_trip(requester=None, days_ahead=14, destination="Mumbai", origin="Bengaluru"):
    """For callers that send plain text only (simulated traffic, the demo studio): a one-way trip with a 3-night stay."""
    d = today() + timedelta(days=days_ahead)
    return {"id": uuid.uuid4().hex[:8], "type": "one_way", "origin": origin, "destination": destination, "depart_date": d.isoformat(),
            "return_date": None, "nights": 3, "hotel": True, "transport": True, "depart_pref": "any", "return_pref": "any",
            "purpose": "Client meeting", "cost_center": "CC-1042", "justification": "", "traveler": requester or ""}


def compact(trip):
    """The part of a trip that rides on every action (kept small: it is stored on each provenance entry)."""
    keys = ("id", "type", "origin", "destination", "depart_date", "return_date", "nights", "purpose", "cost_center", "justification", "traveler")
    return {k: trip.get(k) for k in keys}


def legs_for(trip):
    """The bookings a trip needs, in the order the traveller experiences them, with the supplier search for each."""
    d, r = trip["depart_date"], trip.get("return_date")
    stay_out = r or (date.fromisoformat(d) + timedelta(days=trip.get("nights") or 0)).isoformat()
    legs = [{"id": "flight_out", "kind": "flight", "search": {"date": d, "direction": "outbound", "origin": trip["origin"], "pref": trip["depart_pref"]}}]
    if trip["transport"]:
        legs.append({"id": "transfer_out", "kind": "transport", "search": {"date": d, "direction": "outbound"}})
    if trip["hotel"]:
        legs.append({"id": "hotel", "kind": "hotel", "search": {"check_in": d, "check_out": stay_out}})
    if trip["transport"] and r:
        legs.append({"id": "transfer_back", "kind": "transport", "search": {"date": r, "direction": "return"}})
    if r:
        legs.append({"id": "flight_back", "kind": "flight", "search": {"date": r, "direction": "return", "origin": trip["origin"], "pref": trip["return_pref"]}})
    return legs


def search_params(action):
    """Re-derive the supplier search for an action (used when the agent corrects a blocked proposal)."""
    t, leg = action.get("trip") or {}, action.get("leg")
    if not t or not leg:
        return {}
    return next((s["search"] for s in legs_for({**t, "hotel": True, "transport": True, "depart_pref": "any", "return_pref": "any"}) if s["id"] == leg), {})


def clean_schedule(a):
    """Whitelist the schedule fields a caller of /v1/authorize may send, with bounded types."""
    out = {}
    for k in ("leg", "flight_no", "from_city", "to_city", "route", "depart", "arrive", "check_in", "check_out", "pickup"):
        if a.get(k):
            out[k] = str(a[k])[:40]
    for k in ("nights", "total"):
        if isinstance(a.get(k), (int, float)) and not isinstance(a.get(k), bool) and 0 <= a[k] <= 1_000_000:
            out[k] = a[k]
    if isinstance(a.get("trip"), dict):
        out["trip"] = compact(normalize_loose(a["trip"]))
    return out


def normalize_loose(t):
    """Like normalize() but tolerant: an integration may report a trip that already started."""
    return {k: (str(v)[:300] if isinstance(v, str) else v) for k, v in t.items() if isinstance(v, (str, int, float, bool, type(None)))}


def gate(action, result):
    """Deterministic company travel rules that sit on top of the spending limits. Never relaxes a verdict:
    a MATCH becomes REVIEW (a person decides the exception); REVIEW and DRIFT only gain the extra reasons."""
    t = action.get("trip")
    if not t or result.get("verdict") not in ("MATCH", "REVIEW") or result.get("source") == "control":
        return result
    notes = []
    try:
        depart = date.fromisoformat(str(t["depart_date"])[:10])
        notice = (depart - today()).days
        if notice < POLICY["min_advance_days"]:
            notes.append(f"booked {max(notice, 0)} day{'s' if notice != 1 else ''} before departure; the policy asks for at least {POLICY['min_advance_days']} days' notice")
        if t.get("return_date"):
            span = (date.fromisoformat(str(t["return_date"])[:10]) - depart).days
            if span > POLICY["max_trip_days"]:
                notes.append(f"a {span}-day trip is longer than the {POLICY['max_trip_days']}-day limit")
        if action.get("type") == "book_hotel" and t.get("return_date") and action.get("check_out") and str(action["check_out"])[:10] > str(t["return_date"])[:10]:
            notes.append("the hotel stay runs past the return date")
    except (KeyError, ValueError):
        return result
    if not notes:
        return result
    note = "; ".join(notes)
    if result["verdict"] == "REVIEW":
        return {**result, "violations": list(result.get("violations") or []) + notes, "trip_policy": notes,
                "explanation": f"{result.get('explanation', '').rstrip('.')}. Also: {note}."}
    return {**result, "verdict": "REVIEW", "severity": "low", "violations": list(result.get("violations") or []) + notes, "trip_policy": notes,
            "explanation": f"Within the spending limits, but {note}. A finance manager needs to approve the exception."}
