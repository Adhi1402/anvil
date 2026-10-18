"""Supplier agents (flight, hotel, transport) as A2A servers: Agent Card + JSON-RPC `message/send`.
Self-contained so it can be deployed on its own:  gcloud run deploy anvil-suppliers --source suppliers"""
import os
import uuid
from datetime import date, datetime, timedelta
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# price factor and block-time factor by city (Mumbai is the baseline). Same carriers, hotel chains and ground operators everywhere.
CITY = {"Mumbai": (1.0, 1.0), "Delhi": (1.02, 1.1), "Bengaluru": (0.9, 1.0), "Chennai": (0.95, 1.1), "Hyderabad": (0.92, 1.0), "Pune": (0.88, 0.9),
        "Kolkata": (1.05, 1.4), "Ahmedabad": (0.9, 0.9), "Jaipur": (0.93, 1.0), "Goa": (1.05, 1.0), "Dubai": (1.2, 2.6), "Singapore": (1.18, 3.6)}


def _everywhere(rows):
    return [{**r, "destination": c, "price": round(r["price"] * pf)} for c, (pf, _) in CITY.items() for r in rows]


# out / back = scheduled departure time of day on the outbound and the return sector; mins = block time
_FLIGHTS = [
    {"vendor": "Air India", "price": 480, "class": "economy", "refundable": True, "destination": "Mumbai", "no": "AI 631", "out": "06:10", "back": "19:30", "mins": 130},
    {"vendor": "Air India", "price": 520, "class": "economy", "refundable": True, "destination": "Mumbai", "no": "AI 657", "out": "18:40", "back": "08:05", "mins": 135},
    {"vendor": "IndiGo", "price": 430, "class": "economy", "refundable": False, "destination": "Mumbai", "no": "6E 204", "out": "07:25", "back": "21:10", "mins": 125},
    {"vendor": "IndiGo", "price": 495, "class": "economy", "refundable": True, "destination": "Mumbai", "no": "6E 512", "out": "13:50", "back": "16:20", "mins": 130},
    {"vendor": "Emirates", "price": 590, "class": "business", "refundable": True, "destination": "Mumbai", "no": "EK 508", "out": "22:10", "back": "10:45", "mins": 140},
    {"vendor": "Vistara", "price": 540, "class": "economy", "refundable": True, "destination": "Mumbai", "no": "UK 861", "out": "09:30", "back": "12:55", "mins": 130},
]
_HOTELS = [
    {"vendor": "Taj", "price": 280, "refundable": True, "destination": "Mumbai", "room": "Deluxe room, breakfast included"},
    {"vendor": "OYO", "price": 180, "refundable": False, "destination": "Mumbai", "room": "Standard room"},
    {"vendor": "Lemon Tree", "price": 140, "refundable": False, "destination": "Mumbai", "room": "Superior room, breakfast included"},
    {"vendor": "Marriott", "price": 295, "refundable": True, "destination": "Mumbai", "room": "Executive room, breakfast included"},
]
_TRANSPORT = [{"vendor": "Uber", "price": 40, "destination": "Mumbai", "vehicle": "Sedan (UberX)"},
             {"vendor": "Ola Prime", "price": 85, "destination": "Mumbai", "vehicle": "Prime Sedan"}]
FLIGHTS, HOTELS, TRANSPORT = _everywhere(_FLIGHTS), _everywhere(_HOTELS), _everywhere(_TRANSPORT)


def _search(inventory, data):
    cap = data.get("max_price")
    return [o for o in inventory if o["destination"] == data.get("destination")
            and (cap is None or o["price"] <= cap)]


def _flights(data):
    """Offers as scheduled flights when a date is given (outbound: origin -> destination, return: destination -> origin)."""
    found = _search(FLIGHTS, data)
    if not data.get("date"):
        return [{k: v for k, v in o.items() if k not in ("no", "out", "back", "mins")} for o in found]
    back, origin, dest = data.get("direction") == "return", data.get("origin") or "Bengaluru", data.get("destination")
    out = []
    for o in found:
        start = datetime.fromisoformat(f"{str(data['date'])[:10]}T{o['back'] if back else o['out']}")
        row = {k: v for k, v in o.items() if k not in ("no", "out", "back", "mins")}
        row.update({"flight_no": o["no"], "from_city": dest if back else origin, "to_city": origin if back else dest,
                    "depart": start.strftime("%Y-%m-%dT%H:%M"), "arrive": (start + timedelta(minutes=round(o["mins"] * CITY.get(dest, (1, 1))[1]))).strftime("%Y-%m-%dT%H:%M")})
        out.append(row)
    pref = data.get("pref")
    band = {"morning": (0, 12), "afternoon": (12, 18), "evening": (18, 24)}.get(pref)
    if band:                                                   # the traveller's preferred time of day first, otherwise by price
        out.sort(key=lambda r: (not band[0] <= int(r["depart"][11:13]) < band[1], r["price"]))
    return out


def _hotels(data):
    found = _search(HOTELS, data)
    if not (data.get("check_in") and data.get("check_out")):
        return found
    n = max(1, (date.fromisoformat(str(data["check_out"])[:10]) - date.fromisoformat(str(data["check_in"])[:10])).days)
    return [{**o, "check_in": str(data["check_in"])[:10], "check_out": str(data["check_out"])[:10], "nights": n, "total": o["price"] * n} for o in found]


def _transfers(data):
    found = _search(TRANSPORT, data)
    if not data.get("date"):
        return found
    route = "Hotel to airport" if data.get("direction") == "return" else "Airport to hotel"
    return [{**o, "route": route} for o in found]


AGENTS = {
    "flight": {
        "supplier": "supplier-agent-1", "name": "Flight Supplier Agent",
        "description": "Returns flight offers for a destination under a price cap.",
        "skill": {"id": "flight_search", "name": "Flight search", "tags": ["travel", "flights"],
                  "description": "Find flights to a destination under a max price."},
        "search": _flights},
    "hotel": {
        "supplier": "hotel-supplier-1", "name": "Hotel Supplier Agent",
        "description": "Returns hotel offers (price per night) for a destination under a price cap.",
        "skill": {"id": "hotel_search", "name": "Hotel search", "tags": ["travel", "hotels"],
                  "description": "Find hotels in a destination under a max nightly price."},
        "search": _hotels},
    "transport": {
        "supplier": "transport-supplier-1", "name": "Transport Supplier Agent",
        "description": "Returns ground-transport offers for a destination.",
        "skill": {"id": "transport_search", "name": "Transport search", "tags": ["travel", "transport"],
                  "description": "Find ground transport in a destination."},
        "search": _transfers},
}


def agent_card(key):
    a = AGENTS[key]
    return {
        "protocolVersion": "0.3.0",
        "name": a["name"],
        "description": a["description"],
        "url": f"{request.url_root}{key}/a2a",
        "preferredTransport": "JSONRPC",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [a["skill"]],
    }


def a2a_task(task_id, context_id, state, result=None):          # state: submitted|working|completed|failed
    return {"kind": "task", "id": task_id, "contextId": context_id, "status": {"state": state},
            "artifacts": ([{"artifactId": str(uuid.uuid4()), "parts": [{"kind": "data", "data": result}]}]
                          if result else [])}


@app.route("/")
def index():
    return jsonify({"service": "anvil-suppliers", "agents": {
        k: {"card": f"{request.url_root}{k}/.well-known/agent-card.json"} for k in AGENTS}})


@app.route("/<key>/.well-known/agent-card.json")
def card(key):
    if key not in AGENTS:
        return jsonify({"error": "unknown agent"}), 404
    return jsonify(agent_card(key))


@app.route("/<key>/a2a", methods=["POST"])
def a2a(key):
    if key not in AGENTS:
        return jsonify({"error": "unknown agent"}), 404
    req = request.get_json(silent=True) or {}
    rid = req.get("id")
    if req.get("jsonrpc") != "2.0" or req.get("method") != "message/send":
        return jsonify({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "Method not found"}})
    msg = (req.get("params") or {}).get("message") or {}
    data = next((p["data"] for p in msg.get("parts", []) if p.get("kind") == "data"), None)
    if data is None:
        return jsonify({"jsonrpc": "2.0", "id": rid, "error": {"code": -32602, "message": "Expected a data part"}})
    a = AGENTS[key]
    task_id, ctx = str(uuid.uuid4()), msg.get("contextId") or str(uuid.uuid4())
    # Task lifecycle: submitted -> working -> completed (single-shot, so we return the final state)
    result = {"supplier": a["supplier"], "offers": a["search"](data)}
    return jsonify({"jsonrpc": "2.0", "id": rid, "result": a2a_task(task_id, ctx, "completed", result)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8081)))
