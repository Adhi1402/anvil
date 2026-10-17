"""Anvil vs a fair rules-only baseline over the scripted scenarios, repeated to measure stability."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from anvil.audit import audit, rules_baseline
from data.store import DEMO_MANDATE
from data.scenarios import SCENARIOS


def _row(mandate, s, repeats):
    a = s["action"]
    runs = [audit(mandate, a) for _ in range(repeats)]
    verdicts = [r["verdict"] for r in runs]
    v = runs[0]
    return {
        "name": s["name"], "domain": s.get("domain", "travel"), "drift_type": s.get("drift_type", "none"), "type": a["type"], "expect": s["expect"],
        "anvil_verdict": v["verdict"], "exact": v["verdict"] == s["expect"],
        "anvil_caught": v["verdict"] != "MATCH",              # not waved straight through
        "baseline_caught": not rules_baseline(mandate, a),
        "stable": len(set(verdicts)) == 1,
        "from_cache": any(r.get("source") == "cache" for r in runs),
        "explanation": v["explanation"],
    }


def run_eval(mandate=DEMO_MANDATE, scenarios=SCENARIOS, repeats=1):
    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(lambda s: _row(mandate, s, repeats), scenarios))
    violations = [r for r in rows if r["expect"] != "MATCH"]
    legit = [r for r in rows if r["expect"] == "MATCH"]
    summary = {
        "scenarios": len(rows), "repeats": repeats,
        "violations_total": len(violations), "legit_total": len(legit),
        "anvil_catch_rate": sum(r["anvil_caught"] for r in violations),
        "baseline_catch_rate": sum(r["baseline_caught"] for r in violations),
        "anvil_false_blocks": sum(r["anvil_caught"] for r in legit),      # legit actions not allowed: want 0
        "baseline_false_blocks": sum(r["baseline_caught"] for r in legit),
        "exact_verdict_matches": sum(r["exact"] for r in rows),
        "stable_scenarios": sum(r["stable"] for r in rows),
        "served_from_cache": sum(r["from_cache"] for r in rows),
    }
    by_type = {}
    for r in violations:
        t = by_type.setdefault(r["drift_type"], {"total": 0, "anvil": 0, "baseline": 0})
        t["total"] += 1; t["anvil"] += r["anvil_caught"]; t["baseline"] += r["baseline_caught"]
    summary["by_type"] = by_type
    return {"rows": rows, "summary": summary}


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    res = run_eval(repeats=n)
    for r in res["rows"]:
        flag = "ok " if r["exact"] else "MISS"
        print(f"{flag} {r['expect']:6} -> {r['anvil_verdict']:6} base_caught={r['baseline_caught']!s:5} {r['name']}")
    print(json.dumps(res["summary"], indent=2))
