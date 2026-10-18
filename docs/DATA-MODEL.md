# How Anvil uses Firestore

Firestore (Native mode, project `dazzling-lodge-511607-m0`) is the only database. The backend (Cloud Run) reads and writes it with its service identity, which bypasses security rules. The browser reads two collections directly for the live feed and nothing else (see `firestore.rules`).

| Collection / document | What it holds | Written by | Read by |
|---|---|---|---|
| `provenance/{id}` | The audit chain. One entry per decision or control: the action, verdict, explanation, violations, delegation, `prev_hash` and `hash` (SHA-256 of the previous hash plus the entry), plus receipts (`cart_mandate`), the AP2 chain, `telemetry` (with `trace_id`), `counterfactual`, `considered` (the offers weighed), `rationale`, `requester`, `origin`, and decisions (`re_consent_for`, `approver`, `comment`). Append-only. | Backend only, inside a transaction | Browser live listener (`onSnapshot`, newest 300), the API |
| `meta/chain_tip` | Hash and id of the latest entry. Updated in the same transaction as each append, so two writers can never fork the chain. | Backend | Backend |
| `mandates/mandate-001` | The signed policy (Intent Mandate): spending limits in `constraints`, trip rules and approved cities in `trip_rules`, `version`, `user` (who signed), HMAC `signature`. A forged edit fails verification and every request is refused. | Backend (seed, and the finance manager's policy edits) | Browser (policy page), backend on every request |
| `policy_versions/v0002…` | Policy history: who changed what, when and why, with the full constraints at that version. | Backend (on each edit) | API only |
| `llm_traces/{id}` and `llm_trace_bodies/{id}` | Every Gemini call. The first is a small summary (model, latency, tokens, cost, status, context) that the list reads; the second holds the full prompt and raw response and is read only when a trace is opened. | Backend (`anvil/gemini.py`, the single door to Gemini) | API only (the operator's AI traces page) |
| `controls/state` | Kill-switch state (paused agents, revoked policy, with expiry times) and the demo session start. | Backend | Backend |
| `verdict_cache/{sha256}` | Last good verdict per exact (policy, action, prompt, model); used only if Gemini is unavailable. | Backend | Backend |
| `meta/eval_latest`, `meta/eval_latest_software` | Cached scoreboard results. | Backend | API |
| `meta/sim` | Lease that keeps simulated traffic to one request at a time. | Backend | Backend |

## Rules (`firestore.rules`)
`provenance` and `mandates` are publicly readable and never client-writable; everything else (including `policy_versions` and `llm_traces`) is closed to browsers and reachable only through the API. Because the activity feed is world-readable in this demo, a production deployment should replace the live listener with per-user queries behind sign-in.

## Notes
- The audit chain is integrity-protected, not secret: anyone with read access can verify it and nobody can alter it without breaking the chain.
- A policy edit rewrites only `mandates/mandate-001` (new version, new signature) and appends a `policy_update` entry to `provenance`; earlier decisions keep the policy version they were made under.
