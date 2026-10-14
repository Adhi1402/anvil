"""Anvil walking skeleton: mandate -> travel agent -> Gemini auditor -> Firestore -> dashboard."""
import html
import json
import os
from flask import Flask, jsonify
from agents.run import travel_agent
from anvil.audit import audit, rules_baseline
from data.store import get_mandate, log_provenance, list_provenance

app = Flask(__name__)

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
    mandate = get_mandate()
    action = travel_agent(mandate)
    result = audit(mandate, action)
    entry_id = log_provenance(mandate["id"], action, result)
    out = {"mandate": mandate, "action": action, "audit": result,
           "rules_baseline_pass": rules_baseline(mandate, action), "provenance_id": entry_id}
    from flask import request, redirect
    return redirect("/") if request.method == "POST" else jsonify(out)


@app.route("/api/provenance")
def api_provenance():
    return jsonify(list_provenance())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
