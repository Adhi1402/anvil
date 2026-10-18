"""Guard: propose -> audit -> (if DRIFT) feed the violations back -> agent re-plans -> audit again.
The re-planned action is audited exactly like the original, so the loop can never bypass enforcement.
guard_stream yields events as they happen (for the live UI); book_with_guard collects them into steps."""
from agents.run import replan
from anvil import ap2_layer, trip
from anvil.audit import audit

MAX_CORRECTIONS = 2


def audited(mandate, action):
    """Gemini's semantic audit, then the company's trip rules (notice, length, stay), then (if configured) AP2's deterministic mandate constraints as a second gate."""
    return ap2_layer.gate(mandate, action, trip.gate(action, audit(mandate, action)))


def halted_result(reason):
    """Kill switch: a paused agent or revoked mandate is stopped before any model call."""
    return {"verdict": "DRIFT", "severity": "high", "violations": [reason], "source": "control",
            "explanation": f"Blocked by manager control, no audit needed: {reason}."}


def guard_stream(mandate, action, halt=None, max_corrections=MAX_CORRECTIONS):
    yield {"event": "audit_start", "action": action}
    result = halted_result(halt) if halt else audited(mandate, action)
    yield {"event": "audit", "action": action, "audit": result, "attempt": 0}
    attempts = 0
    while result["verdict"] == "DRIFT" and not halt and attempts < max_corrections:
        attempts += 1
        reason = "; ".join(result["violations"]) or result["explanation"]
        yield {"event": "correction_start", "reason": reason, "attempt": attempts}
        new = replan(mandate, action, reason)            # agent corrects itself using the stated reasons
        if not new:
            yield {"event": "correction_failed", "reason": reason}
            return
        tele = new.pop("replan_telemetry", None)
        action = new
        yield {"event": "audit_start", "action": action, "replan_telemetry": tele}
        result = audited(mandate, action)
        yield {"event": "audit", "action": action, "audit": result, "attempt": attempts, "replan_telemetry": tele}


def book_with_guard(mandate, action, halt=None):
    return [{"action": e["action"], "audit": e["audit"], **({"correction_attempt": e["attempt"]} if e["attempt"] else {})}
            for e in guard_stream(mandate, action, halt) if e["event"] == "audit"]
