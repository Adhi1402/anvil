"""A2A client: Agent Card discovery + Message/Task over JSON-RPC.

SUPPLIERS_URL set   -> real HTTP to the deployed supplier service (production).
SUPPLIERS_URL unset -> same JSON-RPC calls, routed in-process to suppliers/main.py (offline / local fallback)."""
import asyncio
import logging
import os
import uuid
import requests

log = logging.getLogger("anvil.a2a")

SUPPLIERS_URL = os.environ.get("SUPPLIERS_URL", "").rstrip("/")
OFFICIAL = os.environ.get("ANVIL_A2A_OFFICIAL", "1") != "0"      # "0" forces the hand-written client
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


def _norm(x):
    """Protobuf Structs turn every number into a float; restore ints so data is identical to the hand-written path."""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, dict):
        return {k: _norm(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_norm(v) for v in x]
    return x


def _sdk_usable():
    """Official a2a-sdk client is used only against the deployed suppliers (real HTTP) and only if it imports."""
    if not (SUPPLIERS_URL and OFFICIAL):
        return False
    try:
        import a2a.client  # noqa: F401
        import httpx  # noqa: F401
        return True
    except Exception:
        return False


async def _sdk_discover(agent):
    import httpx
    from a2a.client import A2ACardResolver
    async with httpx.AsyncClient(timeout=20) as h:
        card = await A2ACardResolver(httpx_client=h, base_url=f"{SUPPLIERS_URL}/{agent}").get_agent_card()
    return {"name": card.name, "url": card.supported_interfaces[0].url, "via": "official a2a-sdk", "_sdk_card": card}


async def _sdk_send(card, data):
    import httpx
    from google.protobuf.json_format import MessageToDict
    from a2a.client import ClientConfig, ClientFactory
    from a2a.helpers import new_data_message
    from a2a.types import Role, SendMessageRequest, TaskState
    async with httpx.AsyncClient(timeout=30) as h:
        client = ClientFactory(ClientConfig(httpx_client=h, streaming=False)).create(card["_sdk_card"])
        msg = new_data_message(data, role=Role.ROLE_USER)
        tasks = [ev.task async for ev in client.send_message(SendMessageRequest(message=msg)) if ev.HasField("task")]
    task = tasks[0]
    if task.status.state != TaskState.TASK_STATE_COMPLETED:
        raise RuntimeError(f"A2A task {task.id} ended in state {task.status.state}")
    result = _norm(MessageToDict(task.artifacts[0].parts[0].data))
    return {"id": task.id, "status": {"state": "completed"}}, result


def discover(agent):
    """Fetch (and cache) an agent's card. Official a2a-sdk client when available, else the hand-written fetch."""
    if agent not in _cards:
        if _sdk_usable():
            try:
                _cards[agent] = asyncio.run(_sdk_discover(agent))
                return _cards[agent]
            except Exception as e:                       # never let the official path take the demo down
                log.warning("official A2A discovery failed for %s, using built-in client: %s: %s", agent, type(e).__name__, str(e)[:160])
        base = SUPPLIERS_URL or "http://localhost"
        card = _get_json(f"{base}/{agent}/.well-known/agent-card.json")
        _cards[agent] = {**card, "via": "built-in client" if SUPPLIERS_URL else "built-in client (in-process)"}
    return _cards[agent]


def clear_discovery():
    _cards.clear()


def send(card, data):
    """message/send to the agent's advertised URL. Returns (task, result-data)."""
    if card.get("_sdk_card") is not None:
        try:
            return asyncio.run(_sdk_send(card, data))
        except Exception as e:
            log.warning("official A2A send failed for %s, using built-in client: %s: %s", card.get("name"), type(e).__name__, str(e)[:160])
    req = {"jsonrpc": "2.0", "method": "message/send", "id": str(uuid.uuid4()),
           "params": {"message": a2a_message("user", data)}}
    resp = _post_json(card["url"], req)
    if "error" in resp:
        raise RuntimeError(f"A2A error from {card['name']}: {resp['error']}")
    task = resp["result"]
    if task["status"]["state"] != "completed":
        raise RuntimeError(f"A2A task {task['id']} ended in state {task['status']['state']}")
    return task, task["artifacts"][0]["parts"][0]["data"]


def status():
    try:
        from importlib.metadata import version
        ver = version("a2a-sdk")
    except Exception:
        ver = None
    mode = "official a2a-sdk" if _sdk_usable() else ("built-in client" if SUPPLIERS_URL else "built-in client (in-process)")
    return {"mode": mode, "a2a_sdk_version": ver, "official_enabled": OFFICIAL, "suppliers_url_set": bool(SUPPLIERS_URL)}
