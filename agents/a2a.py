"""A2A client: Agent Card discovery + Message/Task over JSON-RPC.

SUPPLIERS_URL set   -> real HTTP to the deployed supplier service (production).
SUPPLIERS_URL unset -> same JSON-RPC calls, routed in-process to suppliers/main.py (offline / local fallback)."""
import os
import uuid
import requests

SUPPLIERS_URL = os.environ.get("SUPPLIERS_URL", "").rstrip("/")
_cards = {}
_inproc = None


def a2a_message(role, data):                     # role: "user" | "agent"
    return {"kind": "message", "role": role, "messageId": str(uuid.uuid4()),
            "parts": [{"kind": "data", "data": data}]}


def _local_client():
    global _inproc
    if _inproc is None:
        from suppliers.main import app
        _inproc = app.test_client()
    return _inproc


def _path(url):
    return "/" + url.split("://", 1)[-1].split("/", 1)[-1]


def _get_json(url):
    if SUPPLIERS_URL:
        r = requests.get(url, timeout=20); r.raise_for_status(); return r.json()
    return _local_client().get(_path(url)).get_json()


def _post_json(url, body):
    if SUPPLIERS_URL:
        r = requests.post(url, json=body, timeout=30); r.raise_for_status(); return r.json()
    return _local_client().post(_path(url), json=body).get_json()


def discover(agent):
    """Fetch (and cache) an agent's card from /<agent>/.well-known/agent-card.json."""
    if agent not in _cards:
        base = SUPPLIERS_URL or "http://localhost"
        _cards[agent] = _get_json(f"{base}/{agent}/.well-known/agent-card.json")
    return _cards[agent]


def clear_discovery():
    _cards.clear()


def send(card, data):
    """JSON-RPC message/send to the agent's advertised URL. Returns (task, result-data)."""
    req = {"jsonrpc": "2.0", "method": "message/send", "id": str(uuid.uuid4()),
           "params": {"message": a2a_message("user", data)}}
    resp = _post_json(card["url"], req)
    if "error" in resp:
        raise RuntimeError(f"A2A error from {card['name']}: {resp['error']}")
    task = resp["result"]
    if task["status"]["state"] != "completed":
        raise RuntimeError(f"A2A task {task['id']} ended in state {task['status']['state']}")
    return task, task["artifacts"][0]["parts"][0]["data"]
