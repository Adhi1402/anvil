"""Guard: propose -> audit -> (if DRIFT) feed the reason back -> re-plan -> audit again."""
from agents.run import replan
from anvil.audit import audit


def book_with_guard(mandate, action):
    steps = []
    result = audit(mandate, action)
    steps.append({"action": action, "audit": result})
    if result["verdict"] == "DRIFT" and action.get("type") == "book_flight":   # self-correction is flight-only
        reason = "; ".join(result["violations"]) or result["explanation"]
        fixed = replan(mandate, reason=reason)          # agent corrects itself
        if fixed:
            result2 = audit(mandate, fixed)
            steps.append({"action": fixed, "audit": result2})
    return steps
