"""Supplier agents (flight, hotel, transport) as A2A servers: Agent Card + JSON-RPC `message/send`.
Self-contained so it can be deployed on its own:  gcloud run deploy anvil-suppliers --source suppliers"""
import os
import uuid
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

FLIGHTS = [
    {"vendor": "Air India", "price": 480, "class": "economy", "refundable": True, "destination": "Mumbai"},
    {"vendor": "Air India", "price": 520, "class": "economy", "refundable": True, "destination": "Mumbai"},
    {"vendor": "IndiGo", "price": 430, "class": "economy", "refundable": False, "destination": "Mumbai"},
]
HOTELS = [
    {"vendor": "Taj", "price": 280, "refundable": True, "destination": "Mumbai"},
    {"vendor": "OYO", "price": 180, "refundable": False, "destination": "Mumbai"},
]
TRANSPORT = [{"vendor": "Uber", "price": 40, "destination": "Mumbai"}]


def _search(inventory, data):
    cap = data.get("max_price")
    return [o for o in inventory if o["destination"] == data.get("destination")
            and (cap is None or o["price"] <= cap)]


AGENTS = {
    "flight": {
        "supplier": "supplier-agent-1", "name": "Flight Supplier Agent",
        "description": "Returns flight offers for a destination under a price cap.",
        "skill": {"id": "flight_search", "name": "Flight search", "tags": ["travel", "flights"],
                  "description": "Find flights to a destination under a max price."},
        "search": lambda d: _search(FLIGHTS, d)},
    "hotel": {
        "supplier": "hotel-supplier-1", "name": "Hotel Supplier Agent",
        "description": "Returns hotel offers (price per night) for a destination under a price cap.",
        "skill": {"id": "hotel_search", "name": "Hotel search", "tags": ["travel", "hotels"],
                  "description": "Find hotels in a destination under a max nightly price."},
        "search": lambda d: _search(HOTELS, d)},
    "transport": {
        "supplier": "transport-supplier-1", "name": "Transport Supplier Agent",
        "description": "Returns ground-transport offers for a destination.",
        "skill": {"id": "transport_search", "name": "Transport search", "tags": ["travel", "transport"],
                  "description": "Find ground transport in a destination."},
        "search": lambda d: _search(TRANSPORT, d)},
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
