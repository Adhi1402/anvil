"""Governance metrics: everything an operator would ask of an agent-spend control layer, computed from the
provenance log (no extra bookkeeping to drift out of sync)."""
from anvil.impact import impact_summary, DRIFT_TYPES

KINDS = ("flight", "hotel", "transport")


def _pct(vals, p):
    if not vals:
        return 0
    v = sorted(vals)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))]


def _kind(entry):
    t = (entry.get("action") or {}).get("type", "")
    return t.replace("book_", "") if t.startswith("book_") else None


def metrics_summary(entries, controls=None, mandate=None):
    """entries: provenance entries (any order). Control/re-consent follow-ups are separated from agent actions."""
    controls = controls or {}
    since = controls.get("session_start") or ""
    entries = [e for e in entries if e.get("ts", "") >= since]
    primary = [e for e in entries if _kind(e) and e["verdict"] in ("MATCH", "REVIEW", "DRIFT")]
    followups = [e for e in entries if (e.get("action") or {}).get("re_consent_for")]
    resolved = {(e["action"]["re_consent_for"]) for e in followups}

    agents = {k: {"actions": 0, "match": 0, "review": 0, "drift": 0, "blocked_usd": 0, "corrections": 0,
                  "corrected_ok": 0} for k in KINDS}
    for e in primary:
        a = agents[_kind(e)]
        a["actions"] += 1
        a[e["verdict"].lower()] += 1
        cf = e.get("counterfactual")
        if e["verdict"] == "DRIFT" and cf:
            a["blocked_usd"] += cf["total_usd"]
        if (e["action"] or {}).get("replan_reason"):
            a["corrections"] += 1
            a["corrected_ok"] += e["verdict"] == "MATCH"
    for a in agents.values():
        n = a["actions"]
        a["clean_rate"] = round(100 * (a["match"] + 0.5 * a["review"]) / n) if n else None   # trust score

    tele = [e["telemetry"] for e in entries if e.get("telemetry")]
    agent_tele = [e["agent_telemetry"] for e in entries if e.get("agent_telemetry")]
    agent_cost = round(sum(t["cost_usd"] for t in agent_tele), 6)
    lat = [t["latency_ms"] for t in tele]
    cost = round(sum(t["cost_usd"] for t in tele), 6)
    imp = impact_summary(primary)
    drift_types = {k: 0 for k in DRIFT_TYPES}
    for e in primary:
        if e["verdict"] in ("DRIFT", "REVIEW"):
            for c in (e.get("counterfactual") or {}).get("categories", []):
                drift_types[c] = drift_types.get(c, 0) + 1

    carts = [e["cart_mandate"] for e in entries if e.get("cart_mandate")]
    spend = {k: 0 for k in KINDS}
    largest = {k: 0 for k in KINDS}                  # caps are per booking, so compare the largest booking, not the sum
    count = {k: 0 for k in KINDS}
    for c in carts:
        for it in c["items"]:
            k = it["kind"].replace("book_", "")
            spend[k] += it["amount"] * it.get("quantity", 1); count[k] += 1; largest[k] = max(largest[k], it["amount"])
    caps = {}
    if mandate:
        caps = {"flight": mandate.get("max_flight_price_usd"), "hotel": mandate.get("max_hotel_per_night_usd"),
                "transport": mandate.get("max_transport_usd")}

    ap2s = [e["ap2"] for e in entries if e.get("ap2")]
    ap2 = {"chains_verified": sum(1 for a in ap2s if a.get("verified")),
           "constraint_blocks": sum(1 for e in entries if e.get("gate") == "ap2-constraints"),
           "manager_overrides": sum(1 for a in ap2s if a.get("manager_override")),
           "errors": sum(1 for a in ap2s if a.get("error"))}
    by_origin = {"user": sum(1 for e in primary if e.get("origin", "user") == "user"),
                 "simulated": sum(1 for e in primary if e.get("origin") == "simulated")}
    return {
        "since": since,
        "by_origin": by_origin,
        "ap2": ap2,
        "totals": {"actions": len(primary), "match": sum(e["verdict"] == "MATCH" for e in primary),
                   "review": sum(e["verdict"] == "REVIEW" for e in primary),
                   "drift": sum(e["verdict"] == "DRIFT" for e in primary),
                   "approved": sum(e["verdict"] == "APPROVED" for e in followups),
                   "rejected": sum(e["verdict"] == "REJECTED" for e in followups),
                   "pending": sum(e["verdict"] == "REVIEW" and e["id"] not in resolved for e in primary if "id" in e)},
        "agents": agents,
        "cost": {"audits": len(tele), "prompt_tokens": sum(t["prompt_tokens"] for t in tele),
                 "output_tokens": sum(t["output_tokens"] for t in tele), "cost_usd": cost,
                 "agent_calls": len(agent_tele), "agent_cost_usd": agent_cost,
                 "avg_cost_per_audit_usd": round(cost / len(tele), 6) if tele else 0,
                 "latency_p50_ms": _pct(lat, 0.5), "latency_p95_ms": _pct(lat, 0.95),
                 "stopped_usd_per_dollar": round(imp["blocked_usd"] / cost) if cost else None},
        "spend": {"approved_usd": sum(spend.values()), "by_kind": spend, "largest_by_kind": largest,
                  "count_by_kind": count, "caps": caps},
        "drift_types": drift_types,
        "impact": imp,
        "controls": controls,
    }
