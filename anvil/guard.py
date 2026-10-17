"""Guard: propose -> audit -> (if DRIFT) feed the violations back -> agent re-plans -> audit again.
The re-planned action is audited exactly like the original, so the loop can never bypass enforcement."""
from agents.run import replan
from anvil.audit import audit

MAX_CORRECTIONS = 2


def book_with_guard(mandate, action):
    steps = []
    result = audit(mandate, action)
    steps.append({"action": action, "audit": result})
    attempts = 0
    while result["verdict"] == "DRIFT" and attempts < MAX_CORRECTIONS:
        attempts += 1
        reason = "; ".join(result["violations"]) or result["explanation"]
        action = replan(mandate, action, reason)         # agent corrects itself using the stated reasons
        if not action:
            break
        result = audit(mandate, action)
        steps.append({"action": action, "audit": result, "correction_attempt": attempts})
    return steps
