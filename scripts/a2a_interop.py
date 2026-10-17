"""Interop check: the OFFICIAL a2a-sdk client against Anvil's hand-built supplier agents.
Not part of the app's requirements; run it in a scratch venv:
    python -m venv /tmp/a2a && /tmp/a2a/bin/pip install a2a-sdk httpx
    /tmp/a2a/bin/python scripts/a2a_interop.py [SUPPLIERS_URL]
Proves: the official client resolves each Agent Card, negotiates the JSON-RPC interface, sends message/send
and receives a completed Task whose data artifact holds the offers."""
import asyncio
import sys
import httpx
from google.protobuf.json_format import MessageToDict
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.helpers import new_data_message
from a2a.types import Role, SendMessageRequest

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://anvil-suppliers-733520529727.us-central1.run.app").rstrip("/")


async def main():
    bad = 0
    async with httpx.AsyncClient(timeout=30) as h:
        for kind in ("flight", "hotel", "transport"):
            try:
                card = await A2ACardResolver(httpx_client=h, base_url=f"{BASE}/{kind}").get_agent_card()
                client = ClientFactory(ClientConfig(httpx_client=h, streaming=False)).create(card)
                msg = new_data_message({"destination": "Mumbai", "max_price": None}, role=Role.ROLE_USER)
                tasks = [ev.task async for ev in client.send_message(SendMessageRequest(message=msg)) if ev.HasField("task")]
                data = [MessageToDict(p.data) for a in tasks[0].artifacts for p in a.parts if p.HasField("data")]
                offers = data[0]["offers"]
                ok = tasks[0].status.state == 3 and len(offers) > 0      # TASK_STATE_COMPLETED
                print(f"{'PASS' if ok else 'FAIL'} {kind}: card '{card.name}' skills={[s.id for s in card.skills]} "
                      f"state={tasks[0].status.state} supplier={data[0]['supplier']} offers={len(offers)} e.g. {offers[0]}")
                bad += not ok
            except Exception as e:
                print(f"FAIL {kind}: {type(e).__name__}: {str(e)[:300]}")
                bad += 1
    print("ALL PASSED" if not bad else f"{bad} FAILED")
    sys.exit(1 if bad else 0)


asyncio.run(main())
