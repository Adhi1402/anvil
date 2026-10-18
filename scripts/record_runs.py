"""Capture real runs from the deployed API as static recordings for the dashboard's Replay tab.
    python scripts/record_runs.py [API_URL]      -> dashboard/public/recordings/*.json + index.json
Each recording is the exact NDJSON event stream the live UI consumes (with server timestamps), so replay is faithful and free."""
import json
import sys
from pathlib import Path
import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://anvil-733520529727.us-central1.run.app").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "dashboard" / "public" / "recordings"
OUT.mkdir(parents=True, exist_ok=True)
RUNS = [
    ("unprotected-tempt", "Without Anvil: a tempted agent books business class", "An agent is tempted by business class. With enforcement off, nothing checks it and the money is gone.",
     "/stream/scenario", {"name": "business", "enforce": False, "requester": "Demo"}),
    ("protected-tempt", "With Anvil: blocked, explained, self-corrected", "The same business-class booking, with Anvil on: blocked, the reason handed back, the agent corrects itself, the new booking is verified.",
     "/stream/scenario", {"name": "business", "requester": "Demo"}),
    ("clean-trip", "A clean trip, planned by the Gemini agent", "Natural-language request, A2A discovery, Gemini picks offers, every booking audited and verified.",
     "/stream/request", {"text": "Book my Mumbai trip with the cheapest options that fit our travel policy.", "requester": "Demo"}),
    ("cheapest-no-rules", "Cheaper but weaker than policy: escalated to a person", "Non-refundable options are not forbidden, so Anvil escalates them for a one-tap human decision.",
     "/stream/request", {"text": "Cheapest possible everything, I don't care about refunds or the usual suppliers.", "requester": "Demo"}),
    ("fare-split", "Splitting a fare to slip under a limit", "Total is under the cap and the supplier is approved, so a rules check passes it. Anvil sees the structuring.",
     "/stream/scenario", {"name": "Fare split", "requester": "Demo"}),
    ("fake-approval", "A fake 'manager pre-approved' note", "Free text cannot authorize anything. The over-cap fare is still escalated to the manager.",
     "/stream/scenario", {"name": "Adversarial: fake pre-approval", "requester": "Demo"}),
]
index = []
for slug, title, desc, path, body in RUNS:
    r = requests.post(BASE + path, json=body, timeout=240, stream=True)
    evs = [json.loads(l) for l in r.iter_lines(decode_unicode=True) if l]
    errs = [e for e in evs if e["event"] in ("error", "planner_fallback")]
    assert not errs, (slug, errs)
    dur = round(evs[-1]["t"] - evs[0]["t"], 1)
    (OUT / f"{slug}.json").write_text(json.dumps({"title": title, "description": desc, "duration_s": dur, "events": evs}))
    index.append({"file": f"recordings/{slug}.json", "slug": slug, "title": title, "description": desc, "duration_s": dur,
                  "events": len(evs), "unprotected": body.get("enforce") is False})
    print(f"recorded {slug}: {len(evs)} events, {dur}s, steps={[e['step']['audit']['verdict'] for e in evs if e['event']=='step']}")
(OUT / "index.json").write_text(json.dumps(index, indent=1))
requests.post(BASE + "/api/control", json={"action": "new_session"}, timeout=30)
print("wrote", OUT)
