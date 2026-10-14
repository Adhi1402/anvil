import json
from anvil.audit import audit, rules_baseline
from data.store import DEMO_MANDATE
from data.scenarios import SCENARIOS

def run_eval(mandate=DEMO_MANDATE):
    rows = []
    for s in SCENARIOS:
        a = s["action"]
        verdict = audit(mandate, a)                 # MATCH / REVIEW / DRIFT
        base_pass = rules_baseline(mandate, a)      # True = baseline thinks it's fine
        # "caught" = system did NOT wave a non-MATCH action straight through
        anvil_caught = verdict["verdict"] != "MATCH"
        base_caught = not base_pass
        rows.append({
            "name": s["name"], "expect": s["expect"],
            "anvil_verdict": verdict["verdict"], "anvil_caught": anvil_caught,
            "baseline_caught": base_caught,
            "explanation": verdict["explanation"],
        })
    # headline metrics
    violations = [r for r in rows if r["expect"] != "MATCH"]
    legit = [r for r in rows if r["expect"] == "MATCH"]
    summary = {
        "anvil_catch_rate": sum(r["anvil_caught"] for r in violations),
        "baseline_catch_rate": sum(r["baseline_caught"] for r in violations),
        "violations_total": len(violations),
        "anvil_false_blocks": sum(r["anvil_caught"] for r in legit),  # should be 0
    }
    return {"rows": rows, "summary": summary}

if __name__ == "__main__":
    print(json.dumps(run_eval(), indent=2))
