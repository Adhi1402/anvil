"""Official a2a-sdk client path vs the hand-written one, against a REAL local supplier server.
Run (needs a2a-sdk):  python -m tests.test_a2a_official"""
import importlib
import os
import sys
import threading

from werkzeug.serving import make_server

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  -> {detail}" if not cond and detail else ""))
    if not cond:
        failures.append(name)


from suppliers.main import app as suppliers_app
srv = make_server("127.0.0.1", 0, suppliers_app, threaded=True)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}"

# 1. reference results through the in-process (built-in) path
os.environ.pop("SUPPLIERS_URL", None)
import agents.a2a as a2a
importlib.reload(a2a)
ref = {}
for kind in ("flight", "hotel", "transport"):
    card = a2a.discover(kind)
    ref[kind] = a2a.send(card, {"destination": "Mumbai", "max_price": None})[1]
check("in-process path reports itself as built-in", a2a.status()["mode"] == "built-in client (in-process)", a2a.status())

# 2. official SDK path over real HTTP
os.environ["SUPPLIERS_URL"] = URL
os.environ.pop("ANVIL_A2A_OFFICIAL", None)
importlib.reload(a2a)
check("official mode is selected when SUPPLIERS_URL is set and the SDK imports", a2a.status()["mode"] == "official a2a-sdk" and a2a.status()["a2a_sdk_version"], a2a.status())
for kind in ("flight", "hotel", "transport"):
    card = a2a.discover(kind)
    check(f"{kind}: card resolved by the official client", card["via"] == "official a2a-sdk" and card["name"].endswith("Supplier Agent") and "_sdk_card" in card, card.get("via"))
    task, data = a2a.send(card, {"destination": "Mumbai", "max_price": None})
    check(f"{kind}: completed task from the official client", task["status"]["state"] == "completed")
    check(f"{kind}: offers identical to the built-in path (ints preserved)", data == ref[kind], (data, ref[kind]))
check("price numbers are ints, not floats", all(type(o["price"]) is int for o in data["offers"]) if data["offers"] else True)
capped = a2a.send(a2a.discover("flight"), {"destination": "Mumbai", "max_price": 500})[1]
check("price cap respected through the official client", capped["offers"] and all(o["price"] <= 500 for o in capped["offers"]), capped)

# 3. fallback: break the official send; the call must still succeed via the built-in client
async def boom(*a, **k):
    raise RuntimeError("simulated SDK failure")
real = a2a._sdk_send
a2a._sdk_send = boom
task, data = a2a.send(a2a.discover("hotel"), {"destination": "Mumbai", "max_price": None})
check("fallback: SDK failure falls back to the built-in client and returns the same data", data == ref["hotel"] and task["status"]["state"] == "completed")
a2a._sdk_send = real

# 4. discovery fallback: SDK discovery fails -> built-in fetch
async def boom_disc(agent):
    raise RuntimeError("simulated discovery failure")
real_d = a2a._sdk_discover
a2a._sdk_discover = boom_disc
a2a.clear_discovery()
card = a2a.discover("transport")
check("fallback: SDK discovery failure falls back to the built-in fetch", card["via"] == "built-in client" and a2a.send(card, {"destination": "Mumbai", "max_price": None})[1] == ref["transport"], card.get("via"))
a2a._sdk_discover = real_d

# 5. kill switch
os.environ["ANVIL_A2A_OFFICIAL"] = "0"
importlib.reload(a2a)
check("ANVIL_A2A_OFFICIAL=0 forces the built-in client", a2a.status()["mode"] == "built-in client", a2a.status())

srv.shutdown()
print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
