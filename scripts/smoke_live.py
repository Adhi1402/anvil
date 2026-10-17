"""Live end-to-end smoke test against a deployed (or local) Anvil API, using the real Gemini and Firestore.
Usage:  python scripts/smoke_live.py [BASE_URL]      (default: the Cloud Run URL in the README)
NOTE: it writes real entries to the provenance log (the trip, a drift, a review + approval) and calls Gemini
~45 times. Run it BEFORE the demo, not after you've staged a clean log."""
import sys
import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "https://anvil-733520529727.us-central1.run.app").rstrip("/")
fails, warns = [], []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  -> {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def get(path, **kw):
    return requests.get(BASE + path, timeout=kw.pop("timeout", 120), **kw)


def post(path):
    return requests.post(BASE + path, timeout=180)


print(f"Target: {BASE}\n")
m = get("/api/mandate").json()
check("mandate signature valid", m["signature_valid"] is True, m.get("signature_valid"))
check("tampered mandate rejected", get("/api/mandate/tampered").json()["signature_valid"] is False)

r = post("/run/trip"); steps = r.json() if r.ok else []
check("trip: HTTP 200 and 3 steps", r.ok and len(steps) == 3, r.text[:200])
check("trip: all MATCH (clean booking not blocked)", all(s["audit"]["verdict"] == "MATCH" for s in steps),
      [s["audit"]["verdict"] for s in steps])
check("trip: audits served live, not cached", all(s["audit"].get("source") == "live" for s in steps))

r = post("/run/business"); steps = r.json() if r.ok else []
verdicts = [s["audit"]["verdict"] for s in steps]
check("business: DRIFT then corrected to MATCH", verdicts[:1] == ["DRIFT"] and verdicts[-1:] == ["MATCH"], verdicts)
if len(steps) > 1:
    f = steps[-1]["action"]
    check("business: corrected action is economy + refundable + preferred",
          f.get("class") == "economy" and f.get("refundable") and f.get("vendor") in ("Air India", "IndiGo"), f)
    check("business: correction used the stated reasons", bool(f.get("replan_reason")), f)

r = post("/run/over-cap"); steps = r.json() if r.ok else []
check("over-cap: REVIEW", steps and steps[0]["audit"]["verdict"] == "REVIEW", [s["audit"]["verdict"] for s in steps])
if steps:
    rid = steps[0]["provenance_id"]
    a = post(f"/approve/{rid}")
    check("approve REVIEW -> APPROVED", a.ok and a.json()["verdict"] == "APPROVED", a.text[:200])
    check("second approve refused", post(f"/approve/{rid}").status_code == 409)

v = get("/api/verify").json()
check("provenance hash chain verifies", v["chain_ok"] is True, v)
imp = get("/api/impact").json()
check("impact reports blocked spend", imp.get("blocked_usd", 0) > 0 and imp.get("held_usd", 0) > 0, imp)
check("provenance API returns entries", len(get("/api/provenance").json()) > 0)

print("\nRunning the eval (20 scenarios x2, live Gemini; ~1 min)...")
ev = get("/api/eval?refresh=1&repeats=2", timeout=290).json()
s = ev["summary"]
for r in ev["rows"]:
    if not r["exact"]:
        print(f"  note: '{r['name']}' expected {r['expect']} got {r['anvil_verdict']} -- {r['explanation'][:140]}")
print({k: s[k] for k in s if k != "by_type"})
for t, v in s["by_type"].items():
    print(f"  {t:13} anvil {v['anvil']}/{v['total']}   rules-only {v['baseline']}/{v['total']}")
check("eval: zero false blocks on legitimate actions", s["anvil_false_blocks"] == 0, s["anvil_false_blocks"])
check("eval: every violation caught (not waved through)", s["anvil_catch_rate"] == s["violations_total"],
      f"{s['anvil_catch_rate']}/{s['violations_total']}")
check("eval: identical verdicts across repeats", s["stable_scenarios"] == s["scenarios"], f"{s['stable_scenarios']}/{s['scenarios']}")
check("eval: nothing served from the cache fallback", s["served_from_cache"] == 0, s["served_from_cache"])
if s["exact_verdict_matches"] != s["scenarios"]:
    warns.append(f"{s['scenarios'] - s['exact_verdict_matches']} scenario(s) got a different verdict level than labelled "
                 "(e.g. REVIEW vs DRIFT): review the notes above; fix the label or the prompt, don't ignore.")

print()
for w in warns:
    print("WARN", w)
print("ALL PASSED" if not fails else f"{len(fails)} FAILED: " + ", ".join(fails))
sys.exit(1 if fails else 0)
