"""Offline end-to-end test: real Flask apps + real guard/enforcement code, fake Gemini and Firestore.
Run:  python -m tests.test_e2e_local"""
import json
import os
import sys

os.environ.pop("SUPPLIERS_URL", None)            # route A2A calls in-process
from tests.fakes import install

fake_db, app = install()
c = app.test_client()
failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  -> {detail}" if not cond and detail else ""))
    if not cond:
        failures.append(name)


def post(path):
    r = c.post(path)
    return r.status_code, r.get_json()


# --- mandate integrity
m = c.get("/api/mandate").get_json()
check("mandate signature valid", m["signature_valid"] is True)
t = c.get("/api/mandate/tampered").get_json()
check("tampered mandate rejected", t["signature_valid"] is False)

# --- clean trip: 3 agents, all MATCH, 3 cart mandates, no counterfactual
code, steps = post("/run/trip")
check("trip returns 3 steps", code == 200 and len(steps) == 3, steps)
check("trip all MATCH", all(s["audit"]["verdict"] == "MATCH" for s in steps))
check("trip kinds", {s["action"]["type"] for s in steps} == {"book_flight", "book_hotel", "book_transport"})
check("trip prices are the expected cheapest compliant", {s["action"]["vendor"] for s in steps} == {"Air India", "Taj", "Uber"})
prov = {d.id: d.to_dict() for d in fake_db.collection("provenance").stream()}
check("every MATCH has a cart mandate", sum(1 for e in prov.values() if "cart_mandate" in e) == 3)
check("MATCH entries have no counterfactual", not any("counterfactual" in e for e in prov.values()))

# --- drift -> self-correction (flight)
code, steps = post("/run/business")
check("business: blocked then corrected", [s["audit"]["verdict"] for s in steps] == ["DRIFT", "MATCH"], [s["audit"]["verdict"] for s in steps])
fixed = steps[-1]["action"]
check("corrected action is compliant", fixed["class"] == "economy" and fixed["vendor"] in ("Air India", "IndiGo") and fixed["refundable"])
check("correction carries the reason", fixed.get("replan_reason") and fixed.get("replan_rationale"))
check("correction attempt recorded", steps[-1].get("correction_attempt") == 1)
blocked_entry = next(e for e in fake_db.collection("provenance").stream() if e.to_dict()["verdict"] == "DRIFT").to_dict()
check("DRIFT entry has counterfactual", blocked_entry["counterfactual"]["total_usd"] == 590 and blocked_entry["counterfactual"]["outcome"] == "blocked")
check("no cart mandate for the blocked action", "cart_mandate" not in blocked_entry)

# --- REVIEW + human re-consent
code, steps = post("/run/over-cap")
check("over-cap is REVIEW", steps[0]["audit"]["verdict"] == "REVIEW")
rid = steps[0]["provenance_id"]
check("REVIEW has counterfactual with overage", fake_db.collection("provenance").document(rid).get().to_dict()["counterfactual"]["over_cap_usd"] == 60)
check("approve before... first approve ok", post(f"/approve/{rid}")[0] == 200)
check("double-resolve refused (409)", post(f"/approve/{rid}")[0] == 409)
check("reject after approve refused (409)", post(f"/reject/{rid}")[0] == 409)
check("approve unknown id 404", post("/approve/nope")[0] == 404)
approved = [d.to_dict() for d in fake_db.collection("provenance").stream() if d.to_dict()["verdict"] == "APPROVED"]
check("approved REVIEW earns a cart mandate", len(approved) == 1 and "cart_mandate" in approved[0])
check("approve on a MATCH entry refused (400)", post(f"/approve/{next(i for i, e in prov.items() if e['verdict'] == 'MATCH')}")[0] == 400)

# --- hotel / transport corrections via the guard directly
from anvil.guard import book_with_guard
from data.store import DEMO_MANDATE
from data.scenarios import SCENARIOS
mand = {k: v for k, v in DEMO_MANDATE.items() if k not in ("id", "signed_by")}
hotel_bad = next(s for s in SCENARIOS if s["name"] == "Hotel booked at unapproved supplier")["action"]
st = book_with_guard(mand, hotel_bad)
check("hotel DRIFT is re-planned and ends compliant", st[-1]["audit"]["verdict"] == "MATCH" and st[-1]["action"]["type"] == "book_hotel", [s["audit"]["verdict"] for s in st])
st = book_with_guard(mand, {"type": "book_flight", "supplier": "x", "destination": "Mumbai", "vendor": "Air India", "price": 1})
check("unfixable-by-name still re-audited, bounded attempts", len(st) <= 3)

# --- provenance chain
v = c.get("/api/verify").get_json()
check("hash chain verifies", v["chain_ok"] is True, v)
eid = next(iter(fake_db.collection("provenance").docs))
fake_db.collection("provenance").docs[eid]["explanation"] = "tampered"
check("tampering breaks the chain", c.get("/api/verify").get_json()["chain_ok"] is False)
fake_db.collection("provenance").docs[eid]["explanation"] = prov.get(eid, {}).get("explanation", fake_db.collection("provenance").docs[eid]["explanation"])

# --- impact + eval + provenance API
imp = c.get("/api/impact").get_json()
check("impact: blocked spend counted", imp["blocked_usd"] >= 590 and imp["blocked_count"] >= 1, imp)
check("impact: held spend counted", imp["held_usd"] >= 660, imp)
ev = c.get("/api/eval?refresh=1&repeats=2").get_json()
s = ev["summary"]
check("eval ran 26 scenarios x2", s["scenarios"] == 26 and s["repeats"] == 2)
check("eval stable", s["stable_scenarios"] == 26)
check("eval has taxonomy", set(s["by_type"]) == {"overage", "substitution", "structuring", "smuggling", "scope", "injection"}, s["by_type"])
check("eval: no false blocks (fake judge)", s["anvil_false_blocks"] == 0)
check("eval served nothing from cache", s["served_from_cache"] == 0)
check("eval cached for next call", c.get("/api/eval").get_json()["summary"]["scenarios"] == 26)
check("provenance API returns rows", len(c.get("/api/provenance").get_json()) > 5)

# --- baseline sanity: legit actions pass the rules-only check
from anvil.audit import rules_baseline
check("baseline passes every legit scenario", all(rules_baseline(mand, x["action"]) for x in SCENARIOS if x["expect"] == "MATCH"))

# --- streaming: Gemini-driven agent end to end
def stream(path, body):
    r = c.post(path, json=body)
    return r.status_code, [json.loads(l) for l in r.get_data(as_text=True).splitlines() if l.strip()]

fake_db.collection("provenance").docs.clear()                  # fresh chain for the streaming section
fake_db.collection("controls").docs.clear()
code, evs = stream("/stream/request", {"text": "Book my Mumbai trip, cheapest compliant options."})
kinds = [e["event"] for e in evs]
check("stream: starts, discovers 3 agents, plans, finishes", code == 200 and kinds[0] == "agent_start" and kinds.count("discovered") == 3 and "planning" in kinds and kinds[-1] == "run_done", kinds)
check("stream: 3 proposals each carry a rationale", [e["rationale"] for e in evs if e["event"] == "proposal"] == ["fake planner"] * 3)
check("stream: clean request -> 3 MATCH steps", [e["step"]["audit"]["verdict"] for e in evs if e["event"] == "step"] == ["MATCH"] * 3)
check("stream: steps are logged as they happen", len(list(fake_db.collection("provenance").stream())) == 3)
check("stream: step telemetry recorded", all(e["step"]["audit"]["telemetry"]["cost_usd"] > 0 for e in evs if e["event"] == "step"))
code, evs = stream("/stream/request", {"text": "I need business class on the way out, I will be exhausted."})
steps = [e for e in evs if e["event"] == "step"]
verds = [e["step"]["audit"]["verdict"] for e in steps]
check("stream: tempted agent proposes business, Anvil blocks then corrects", verds[:2] == ["DRIFT", "MATCH"], verds)
check("stream: correction events emitted in order", [e["event"] for e in evs if e["event"] in ("correction_start",)] == ["correction_start"])
check("stream: planner rationale is NOT part of the audited action", all("rationale" not in e["step"]["action"] for e in steps))
check("stream: empty request rejected", c.post("/stream/request", json={"text": " "}).status_code == 400)
code, evs = stream("/stream/scenario", {"name": "Fare split"})
check("stream: scripted rogue scenario blocked", [e["step"]["audit"]["verdict"] for e in evs if e["event"] == "step"][0] == "DRIFT")

# --- governance: metrics, controls, evidence
mt = c.get("/api/metrics").get_json()
check("metrics: agents scorecard present", set(mt["agents"]) == {"flight", "hotel", "transport"} and mt["agents"]["flight"]["actions"] >= 4)
check("metrics: cost of governance tracked", mt["cost"]["audits"] >= 8 and mt["cost"]["cost_usd"] > 0 and mt["cost"]["latency_p50_ms"] >= 0)
check("metrics: agent (planner/replan) cost tracked separately", mt["cost"]["agent_calls"] >= 2 and mt["cost"]["agent_cost_usd"] > 0)
check("metrics: drift types counted", mt["drift_types"]["substitution"] >= 1 and mt["drift_types"]["structuring"] >= 1, mt["drift_types"])
check("metrics: approved spend sums cart mandates", mt["spend"]["approved_usd"] > 0)
check("control: unknown action rejected", c.post("/api/control", json={"action": "nuke"}).status_code == 400)
c.post("/api/control", json={"action": "pause", "agent": "hotel"})
code, evs = stream("/stream/scenario", {"name": "trip"})
by = {e["kind"]: e["step"]["audit"] for e in evs if e["event"] == "step"}
check("kill switch: paused hotel agent is blocked without a model call", by["hotel"]["verdict"] == "DRIFT" and by["hotel"]["source"] == "control", by.get("hotel"))
check("kill switch: other agents unaffected", by["flight"]["verdict"] == "MATCH" and by["transport"]["verdict"] == "MATCH")
c.post("/api/control", json={"action": "resume", "agent": "hotel"})
c.post("/api/control", json={"action": "revoke"})
code, evs = stream("/stream/scenario", {"name": "trip"})
check("revoked mandate blocks every leg", [e["step"]["audit"]["verdict"] for e in evs if e["event"] == "step"] == ["DRIFT"] * 3)
check("revoked mandate: no correction attempted", not any(e["event"] == "correction_start" for e in evs))
c.post("/api/control", json={"action": "restore"})
check("controls are written to the chain", sum(1 for d in fake_db.collection("provenance").stream() if d.to_dict()["verdict"] == "CONTROL") == 4)
check("chain still verifies after controls", c.get("/api/verify").get_json()["chain_ok"] is True)
c.post("/api/control", json={"action": "new_session"})
mt2 = c.get("/api/metrics").get_json()
check("new session: metrics restart from zero, history kept", mt2["totals"]["actions"] == 0 and len(list(fake_db.collection("provenance").stream())) > 10)
stream("/stream/scenario", {"name": "trip"})
ev = c.get("/api/evidence")
pack = json.loads(ev.get_data(as_text=True))
check("evidence pack: session-scoped, signed mandate, chain ok, digest", ev.status_code == 200 and pack["signature_valid"] and pack["chain_ok"] and len(pack["pack_sha256"]) == 64 and len([e for e in pack["entries"] if e["verdict"] == "MATCH"]) == 3, [e["verdict"] for e in pack["entries"]])

tv = c.get("/api/verify/tamper").get_json()
check("tamper simulation: breaks the chain without writing", tv["chain_ok"] is False and c.get("/api/verify").get_json()["chain_ok"] is True, tv)

# --- tampered intent must stop /run
from data.store import get_mandate
doc = fake_db.collection("mandates").docs["mandate-001"]
doc["constraints"]["max_flight_price_usd"] = 99999
check("forged stored mandate -> /run refused (403)", post("/run/trip")[0] == 403)

print(f"\n{'ALL PASSED' if not failures else str(len(failures)) + ' FAILED: ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
