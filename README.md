# ANVIL — governance for autonomous spending agents

AI agents already book travel and spend money on a company's behalf, but nothing checks that they stayed inside what a human actually approved. **Anvil** is the layer that does. A manager signs a **mandate**; a team of agents plans a trip over **A2A**; every proposed action is audited by **Gemini** against the *intent* of that mandate (not just its numbers) and comes back `MATCH` (allow), `REVIEW` (escalate for one-tap human re-consent) or `DRIFT` (block). When an agent drifts, Anvil explains why and the agent **re-plans within policy by itself**. Everything lands in a hash-chained, tamper-evident provenance log you can replay.

**Live demo:** https://dazzling-lodge-511607-m0.web.app  ·  **API:** https://anvil-733520529727.us-central1.run.app

## What it proves (measured, not asserted)

26 scripted scenarios (7 legitimate, 19 violations including 6 adversarial) run through a fair rules-only baseline (budget cap per action type + supplier allowlist + destination check) and through Anvil, against **live Gemini**, 3 repeats each:

| Failure type | Example | Anvil | Rules-only |
|---|---|---|---|
| Overage | fare above the cap | 3/3 | 3/3 |
| Scope | wrong destination, unapproved supplier | 3/3 | 3/3 |
| **Substitution** | business class; non-refundable when refundable required | 3/3 | **0/3** |
| **Structuring** | one fare split into charges to slip under a limit | 2/2 | **0/2** |
| **Smuggling** | unrelated add-on charges | 2/2 | **0/2** |
| **Injection** | note says "manager pre-approved this" / "ignore previous instructions" | 6/6 | 4/6 |

**Anvil caught 19/19 violations, the baseline 10/19, with 0 false blocks on 7 legitimate actions (including exactly-at-the-cap).** 26/26 verdicts were identical across repeats and matched their label; none were served from the cache fallback. These are our own labelled scenarios: a strong signal, not an independent benchmark. Re-run: `python -m anvil.eval 3`, `GET /api/eval?refresh=1&repeats=3`, or the dashboard's *Re-run live eval*.

## Meets the competition requirements

| Requirement | Where it lives |
|---|---|
| Problem and why it matters | AI agents already spend company money; nothing checks that they stayed inside what a human approved (deck slides 2-3) |
| How the solution addresses it | Signed mandate → Gemini audit of every action → deterministic enforcement → self-correction → signed receipt + tamper-evident trail |
| Google AI integration | **Gemini 2.5 Flash on Vertex AI** is the auditor, the booking agent's planner, and the corrector (`anvil/gemini.py`, `anvil/audit.py`, `agents/planner.py`) |
| Working prototype | Live dashboard (Mission Control + Governance) driving real Gemini calls |
| Deployed on GCP | Cloud Run (`anvil`, `anvil-suppliers`), Firestore, Firebase Hosting |

## What is in the product
- **Mission Control:** type a request in plain English; a Gemini booking agent discovers supplier agents over A2A, chooses offers, and every proposal is audited live. A flow diagram, event stream and decision cards show each step as it happens. Rogue-agent simulations (fare split, hidden add-on, fake approval note, prompt injection) show enforcement.
- **Governance console:** agent scorecards and trust scores, **kill switch** (pause an agent or revoke the mandate; blocked without a model call and logged to the chain), spend vs authorized caps, failure taxonomy, **cost of governing** (tokens, latency p50/p95, cost per audit, return on governance) and a downloadable **evidence pack**.
- **Counterfactual receipts:** every block states what it would have cost ("$590, business class instead of economy, carrier not preferred"), computed deterministically from the action and mandate, not by the model.

## Architecture

```mermaid
flowchart LR
    M(["Manager"]) -- "signs" --> IM["Intent Mandate (HMAC)<br/>+ AP2 open mandates (SD-JWT, ES256)"]
    IM --> ORCH

    subgraph CR["Cloud Run · anvil"]
        ORCH["Trip orchestrator"]
        ORCH --> FA["Flight agent"]
        ORCH --> HA["Hotel agent"]
        ORCH --> TA["Transport agent"]
        GUARD["Anvil guard<br/>audit → block → self-correct"]
        CART["Cart Mandate + AP2 mandate chain<br/>(on MATCH / approved REVIEW)"]
    end

    subgraph SUP["Cloud Run · anvil-suppliers"]
        SF["Flight supplier<br/>Agent Card"]
        SH["Hotel supplier<br/>Agent Card"]
        ST["Transport supplier<br/>Agent Card"]
    end

    FA & HA & TA <-- "A2A: discover card,<br/>JSON-RPC message/send" --> SF & SH & ST
    FA & HA & TA -- "proposed action" --> GUARD
    GUARD <-- "mandate + action" --> G["Gemini 2.5 Flash<br/>Vertex AI · JSON schema · temp 0"]
    GUARD -- "MATCH / REVIEW / DRIFT" --> CART
    GUARD -- "every step" --> FS[("Firestore<br/>hash-chained provenance")]
    CART --> FS
    FS -- "live onSnapshot" --> UI["Dashboard<br/>Firebase Hosting"]
    UI -- "run scenario · approve / reject" --> ORCH
```

**One request, end to end**
1. The manager's constraints are stored as a signed **Intent Mandate**. `/run` refuses to proceed if the signature does not verify.
2. The trip orchestrator **discovers** the flight, hotel and transport supplier agents from their **Agent Cards**, then each buyer agent sends a JSON-RPC `message/send` and receives a Task whose artifact holds the offers.
3. Each agent proposes one action. The **guard** asks Gemini to judge it against the mandate and returns a verdict with severity, violations and a plain-language explanation.
4. `MATCH` → a signed **Cart Mandate** is issued. `REVIEW` → the dashboard shows *Needs manager approval*; approving appends a human re-consent entry and issues the Cart Mandate. `DRIFT` → blocked, the reason is handed back to the agent, which **re-plans** (strict, deterministic planner) and is audited again.
5. Every step is appended to the provenance log with a 3-hop **delegation chain** (manager → orchestrator → agent → supplier). Each entry carries the hash of the previous one, so editing any entry visibly breaks the chain.

## Google stack

| Piece | Used for |
|---|---|
| **Gemini 2.5 Flash on Vertex AI** | The drift auditor: structured JSON verdicts, temperature 0, retries + cached-verdict fallback |
| **A2A** | Agent Cards + discovery, Message/Task over JSON-RPC between buyer and supplier agents |
| **AP2 V2 (official SDK)** | Manager-signed open payment mandates and per-booking closed mandates as SD-JWT chains, verified by Google's SDK; deterministic constraints as a second gate. HMAC Intent/Cart Mandates are kept for receipts |
| **Cloud Run** | Two services: `anvil` (orchestrator, guard, API) and `anvil-suppliers` (A2A supplier agents) |
| **Firestore** | Mandates, provenance log, verdict/eval caches |
| **Firebase Hosting** | The live dashboard (real-time Firestore listener) |

### What we claim (and what we don't)
- ✅ **A2A:** our supplier agents interoperate with the **official `a2a-sdk` client** (v1.2.2): it resolves each Agent Card, negotiates the JSON-RPC interface, calls `message/send` and receives a completed Task with the offers (`scripts/a2a_interop.py`, 3/3 pass against the deployed service). Our buyer-side client and the supplier server are hand-written, speaking protocol 0.3.
- ✅ **AP2:** every allowed booking also carries an **AP2 V2 mandate chain built and verified with Google's official AP2 SDK** (vendored in `ap2/`, SD-JWT, ES256). The manager signs one *open payment mandate* per leg (amount range = the leg's cap, allowed payees = the approved suppliers) with a key that is **not on the server** (`scripts/ap2_issue.py`). For each booking the orchestrator presents a *closed payment mandate*; the SDK verifies the chain and evaluates the constraints. A constraint violation turns the verdict into DRIFT (fail closed) and the self-correction loop runs. `GET /api/ap2/verify/<entry>` re-verifies a stored chain independently.
- ✅ **Stacked on purpose:** AP2 constraints are deterministic (amount, payee). They catch overage and unapproved suppliers, but a $590 business-class booking at an approved supplier passes them. That is what Gemini's semantic audit catches. Anvil's original HMAC Intent/Cart Mandates are kept alongside for the receipts and the tamper demo.
- ❌ Not claimed: "fully AP2-compliant". The payment instrument and payee records are demo values, there is no bank/PISP issuer role, and the orchestrator's private key is an environment variable on Cloud Run (production: Secret Manager or KMS). If the AP2 layer is not configured, or has an infrastructure error, nothing is blocked and behaviour is exactly as before AP2 (the error is recorded on the entry).

## Scaling and real-time use

**Measured today (live):** one run is about 20 s (planner call + 3 sequential Gemini audits, ~3.6 s median each, ~$0.002 per audit, estimated). 8 simultaneous runs finish in about 34 s of wall time with correct verdicts and an unbroken hash chain.

**What was done for concurrent use:** log appends are Firestore transactions on a stored chain tip (O(1) reads, the chain cannot fork under concurrent writers; tested with 60 simultaneous appends); gunicorn 8 threads, Cloud Run concurrency 8, one warm instance, autoscaling to 10; pauses and revocations auto-expire (default 3 min) so one visitor cannot leave a shared demo blocked; the AP2 signing key is in Secret Manager.

**Known limits (hackathon scope):** one global chain and one global control state, so write throughput on the chain tip is roughly one entry per second per chain; per-tenant or per-mandate chains remove that. Legs run sequentially. Metrics re-read up to 500 entries per call. Public demo endpoints are unauthenticated.

**Path to production:** expose Anvil as a synchronous authorization call inside the agent's purchase tool (`POST /authorize` returning the verdict plus an AP2 chain) with idempotency keys; per-tenant chains, mandates and controls behind authentication; human approval for REVIEW delivered asynchronously (webhook or chat) while the agent waits or polls; run the deterministic checks (AP2 constraints, caps) before calling Gemini so clear-cut cases cost no tokens; cache identical decisions; audit the three legs in parallel; export the chain to BigQuery; keys in KMS. Decision latency (seconds) suits purchase approvals at human time-scales, not high-frequency payments.

## Repo layout

```
agents/       buyer agents (flight, hotel, transport) + A2A client with Agent Card discovery
suppliers/    supplier agents as an A2A server (own Cloud Run service)
anvil/        audit.py (Gemini auditor + rules baseline), guard.py (self-correction), eval.py (scoreboard)
data/         Firestore access, signing, hash-chained provenance, Cart Mandates, scenarios
dashboard/    Firebase-hosted UI
main.py       Cloud Run API: /run/<scenario>, /approve, /reject, /api/*
hello/        the Day-1 Cloud Run smoke test
```

## Run it

```bash
pip install -r requirements.txt
gcloud auth application-default login          # Vertex AI + Firestore use your gcloud login; no API keys

python -m agents.run        # three agents plan a trip over A2A (in-process when SUPPLIERS_URL is unset)
python -m anvil.audit       # one audit -> MATCH, plus the rules baseline result
python -m anvil.eval        # the Anvil-vs-baseline scoreboard
python main.py              # API on http://localhost:8080  (try /run/trip, /run/business, /api/eval)
```

Deploy (from the repo root):

```bash
gcloud run deploy anvil-suppliers --source suppliers --region us-central1 --allow-unauthenticated
gcloud run deploy anvil --source . --region us-central1 --allow-unauthenticated \
  --set-env-vars SUPPLIERS_URL=https://<anvil-suppliers-url>
firebase deploy --only hosting,firestore
```

AP2 layer (optional): run `python scripts/ap2_issue.py` on the manager's machine (keys go to `~/.anvil/`, never the repo), commit `data/ap2_open_mandates.json`, and set `ANVIL_AP2_ORCH_KEY` on Cloud Run as the script prints. Unset = AP2 off. Details and rollback: `docs/AP2-A2A-TRACKER.md`.

Set `ANVIL_SIGNING_KEY` (Cloud Run env var) for a real signing key; the `dev-only-key` default is for local development.

## Demo endpoints

| Endpoint | What it does |
|---|---|
| `POST /stream/request` | Plain-English request → Gemini agent → guarded, streamed events (NDJSON) |
| `POST /stream/scenario` | Scripted rogue-agent scenarios, streamed |
| `GET /api/ap2`, `/api/ap2/verify/<id>` | AP2 layer status and independent re-verification of a stored chain |
| `GET /api/metrics`, `/api/impact`, `/api/evidence` | Governance numbers, prevented spend, audit-ready evidence pack |
| `POST /api/control` | Pause/resume an agent, revoke/restore the mandate, start a new session (all logged to the chain) |
| `POST /run/trip` | Flight + hotel + transport over A2A, each audited and logged |
| `POST /run/over-cap` | Borderline fare → `REVIEW` with an Approve / Reject card |
| `POST /run/business` | Business-class on a non-preferred carrier → `DRIFT` → agent self-corrects → `MATCH` |
| `GET /api/mandate`, `/api/mandate/tampered` | Signature check, and a forged copy that must be rejected |
| `GET /api/verify` | Walks the provenance hash chain |
| `GET /api/eval` | Cached scoreboard (`?refresh=1` recomputes) |

## Known limits (hackathon scope)
- The demo endpoints and Firestore reads are public so judges can click through; lock both down for real use.
- Agents search hard-coded supplier inventories; the point is the governance layer, not the marketplace.
- Gemini cost figures are estimates from list prices (configurable via env), not billing data.
- The audit trail is tamper-evident (hash chain), not tamper-proof: someone with database write access could rebuild it. Signing entries is the production step.
- Mandate fields are a fixed travel schema; a second domain would generalize the audit prompt.
