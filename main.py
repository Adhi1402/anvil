"""Anvil walking skeleton: mandate -> travel agent -> Gemini auditor -> Firestore -> dashboard."""
import html
import json
import os
from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from flask import Flask, jsonify, request, redirect
from agents.run import travel_agent, plan_trip
from anvil.audit import audit, rules_baseline
from anvil.guard import book_with_guard
from anvil.impact import counterfactual, impact_summary
from data.store import (db, get_mandate, verify_mandate, log_provenance, list_provenance, verify_chain,
                        delegation_for, cart_mandate)

app = Flask(__name__)


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"      # public read API for the Firebase-hosted dashboard
    return resp

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Anvil</title>
<style>body{{font-family:system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}}
.e{{border:1px solid #ccc;border-radius:8px;padding:.8rem;margin:.6rem 0}}
.MATCH{{border-left:6px solid #1a7f37}}.REVIEW{{border-left:6px solid #bf8700}}.DRIFT{{border-left:6px solid #cf222e}}
pre{{white-space:pre-wrap;margin:.3rem 0}}button{{padding:.5rem 1rem;font-size:1rem}}</style>
<h1>Anvil provenance log</h1>
<form method=post action=/run><button>Run agent now</button></form>
{entries}"""


@app.route("/")
def dashboard():
    rows = []
    for e in list_provenance():
        rows.append(
            f'<div class="e {html.escape(e["verdict"])}"><b>{html.escape(e["verdict"])}</b> '
            f'({html.escape(e["severity"])}) &middot; {html.escape(e["ts"])} &middot; mandate {html.escape(e["mandate_id"])}'
            f'<pre>Action: {html.escape(json.dumps(e["action"]))}</pre>'
            f'<pre>{html.escape(e["explanation"])}</pre></div>')
    return PAGE.format(entries="".join(rows) or "<p>No entries yet.</p>")


@app.route("/run", methods=["GET", "POST"])
def run():
    intent = get_mandate()
    if not verify_mandate(intent):
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    mandate = intent["constraints"]
    action = travel_agent(mandate)
    result = audit(mandate, action)
    entry_id = log_provenance(intent["mandateId"], action, result)
    out = {"mandate": intent, "action": action, "audit": result,
           "rules_baseline_pass": rules_baseline(mandate, action), "provenance_id": entry_id}
    return redirect("/") if request.method == "POST" else jsonify(out)


def _log_steps(intent, steps):
    """Log every step with its 3-hop delegation chain; MATCH steps also get a signed Cart Mandate."""
    for st in steps:
        extra = {"intent_signature": intent["signature"]}
        if st["audit"]["verdict"] in ("DRIFT", "REVIEW"):
            extra["counterfactual"] = counterfactual(intent["constraints"], st["action"], st["audit"]["verdict"])
        if st["audit"]["verdict"] == "MATCH":
            extra["cart_mandate"] = cart_mandate(intent, st["action"])
        st["provenance_id"] = log_provenance(intent["mandateId"], st["action"], st["audit"],
                                             delegation=delegation_for(intent, st["action"]), extra=extra)


@app.route("/run/<scenario>", methods=["GET", "POST"])
def run_scenario(scenario):
    """Fire a named scenario on demand ('trip' = flight+hotel+transport). Guard logs every step."""
    from data.scenarios import SCENARIOS
    intent = get_mandate()
    if not verify_mandate(intent):
        return jsonify({"error": "mandate signature invalid - refusing to proceed"}), 403
    mandate = intent["constraints"]
    if scenario.lower() == "trip":
        actions = plan_trip(mandate)
    else:
        s = next((x for x in SCENARIOS if x["name"].lower().startswith(scenario.lower())), None)
        actions = [s["action"] if s else travel_agent(mandate)]
    steps = [st for action in actions for st in book_with_guard(mandate, action)]
    _log_steps(intent, steps)
    return jsonify(steps)


def _resolve_review(entry_id, approved):
    """Human re-consent on a REVIEW entry: appends a new provenance entry, once per REVIEW."""
    doc = db().collection("provenance").document(entry_id).get()
    if not doc.exists:
        return jsonify({"error": "no such provenance entry"}), 404
    e = doc.to_dict()
    if e["verdict"] != "REVIEW":
        return jsonify({"error": "only REVIEW entries need approval"}), 400
    if list(db().collection("provenance").where(filter=FieldFilter("action.re_consent_for", "==", entry_id)).limit(1).stream()):
        return jsonify({"error": "already resolved"}), 409
    verdict = "APPROVED" if approved else "REJECTED"
    audit_like = {"verdict": verdict, "severity": "none", "violations": [],
                  "explanation": ("Human re-consented: manager approved the escalated action."
                                  if approved else "Manager rejected the escalated action; it will not proceed.")}
    intent = get_mandate()
    action = {**e["action"], "re_consent_for": entry_id}
    extra = {"intent_signature": intent["signature"]}
    if approved:                                   # AP2: a human-approved REVIEW earns a Cart Mandate
        extra["cart_mandate"] = cart_mandate(intent, e["action"])
    new_id = log_provenance(e["mandate_id"], action, audit_like,
                            delegation=delegation_for(intent, e["action"]), extra=extra)
    return jsonify({"verdict": verdict, "provenance_id": new_id})


@app.route("/approve/<entry_id>", methods=["POST"])
def approve(entry_id):
    return _resolve_review(entry_id, True)


@app.route("/reject/<entry_id>", methods=["POST"])
def reject(entry_id):
    return _resolve_review(entry_id, False)


@app.route("/api/eval")
def api_eval():
    """Scoreboard. Cached in Firestore (one Gemini call per scenario per repeat); ?refresh=1 recomputes, &repeats=N measures stability."""
    from anvil.eval import run_eval
    ref = db().collection("meta").document("eval_latest")
    if not request.args.get("refresh"):
        cached = ref.get()
        if cached.exists:
            return jsonify(cached.to_dict()["result"])
    result = run_eval(repeats=max(1, min(int(request.args.get("repeats", 1)), 5)))
    ref.set({"result": result, "ts": datetime.now(timezone.utc).isoformat()})
    return jsonify(result)


@app.route("/api/impact")
def api_impact():
    """Prevented-spend rollup from the counterfactual receipts in the provenance log."""
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(500)
    return jsonify(impact_summary([d.to_dict() for d in q.stream()]))


@app.route("/api/mandate")
def api_mandate():
    intent = get_mandate()
    return jsonify({"mandate": intent, "signature_valid": verify_mandate(intent)})


@app.route("/api/mandate/tampered")
def api_mandate_tampered():
    """Demo: a copy of the mandate with one term changed must fail verification."""
    forged = json.loads(json.dumps(get_mandate()))
    old = forged["constraints"]["max_flight_price_usd"]
    forged["constraints"]["max_flight_price_usd"] = 99999
    return jsonify({"changed": f"max_flight_price_usd: {old} -> 99999", "signature_valid": verify_mandate(forged)})


@app.route("/api/verify")
def api_verify():
    ok, broken_at = verify_chain()
    return jsonify({"chain_ok": ok, "broken_at": broken_at})


@app.route("/api/provenance")
def api_provenance():
    return jsonify(list_provenance())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
