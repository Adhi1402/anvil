# 02 · Code changes, high level

Repo: `github.com/Adhi1402/anvil` (branch `main`). 27 commits. Local path: `/home/swathy-s/Documents/anvil/anvil`.
This is a map of *what changed and where*, not a line-by-line review. For design reasons see `03-ARCHITECTURE-AND-DESIGN-FLOW.md`; for the integration work's decisions and rollback see `docs/AP2-A2A-TRACKER.md`.

## 1. How the project grew

| Phase | When | What landed | Key commits |
|---|---|---|---|
| **Days 1–5 (original build)** | Oct 14–17 | Walking skeleton; Gemini auditor with MATCH/REVIEW/DRIFT; signed mandate; hash-chained provenance; A2A-style supplier agents on a separate Cloud Run service; hotel/transport agents; self-correction (flights); REVIEW approve/reject; first dashboard; deck; README | `7602e19` … `dd28422` |
| **Phase 1 — credibility** | Oct 17 | Real correction loop (Gemini reads the violations), 20-scenario eval with fair baseline and stability/cache reporting, counterfactual receipts, failure taxonomy, live smoke test, timeouts/retries, prompt-aware cache key | `7ed62f3`, `4de802e` |
| **Phase 2 — agentic + governance** | Oct 17 | Gemini planner agent, NDJSON streaming, kill switch, session marker, `/api/metrics`, `/api/evidence`, adversarial scenarios, cost/latency telemetry, dark "Mission Control" + Governance UI | `f115ed1`, `f0dc49c` |
| **Phase 3 — Google protocols** | Oct 17–18 | Official **A2A client** interop (and in-app use), official **AP2 V2 SDK** vendored and wired as a second gate, Secret Manager key, transactional hash-chain tip, capacity settings, auto-expiring controls, flaky-verdict fix | `7329f8b`, `6068c94`, `830d19f`, `a82b90b`, `be71a90` |
| **Phase 4 — real-app feel** | Oct 18 | Live ops tab with simulated traffic, demo sign-in with roles, Showcase + Replay tabs, enforcement ON/OFF contrast, guided demo, recorded runs, `POST /v1/authorize`, per-IP rate limit, second domain (software), account renames | `e3f105d`, `7a8119b`, `d4ba9f6`, `f1597f4`, `b7010b1` |

## 2. Backend (Python / Flask on Cloud Run) — by module

| Path | Role | Notable changes |
|---|---|---|
| `main.py` | HTTP API, streaming runs, controls, metrics, authorize, sim | `run_stream` (the one execution path; `enforce=false` simulates an unprotected agent); `/stream/*` NDJSON; `/v1/authorize` (validated, optional `X-Anvil-Key`); `/api/sim/tick` (global lease); `/api/control`; `/api/metrics`, `/api/impact`, `/api/evidence`; `/api/ap2*`, `/api/a2a`; `/api/eval?domain=`; per-IP rate limit; metadata (`requester`, `origin`, `request`) on every entry |
| `anvil/audit.py` | Gemini semantic auditor + rules baseline | Hardened prompt: untrusted free text, structuring, add-ons, inclusive caps, refundability applies only to flights/hotels, generic non-travel clause; fair baseline per action type incl. software |
| `anvil/gemini.py` | Single door to Gemini (Vertex AI) | One thread-safe client, 20 s timeout, retries/backoff, per-call tokens/latency/estimated cost |
| `anvil/guard.py` | Audit → AP2 gate → block → self-correct | Generator (`guard_stream`) so the UI can animate; kill-switch short-circuit (no model call); bounded corrections |
| `anvil/ap2_layer.py` | Official AP2 V2 SDK layer | Per-leg manager-signed open mandates; closed mandate per booking; chain verify; constraint violations ⇒ DRIFT (fail closed); infra errors never block; off unless key present |
| `anvil/impact.py` | Counterfactual receipts + failure taxonomy | Deterministic arithmetic (no model) |
| `anvil/metrics.py` | Governance numbers | Scorecards, cost of governing, spend vs caps, taxonomy, AP2 counters, origin split |
| `anvil/eval.py` | Scoreboard | Parallel, repeats, stability, per-type results, domain-agnostic |
| `agents/planner.py` | Gemini booking agent | Reads a plain-English request + A2A offers; picks a leg each; scripted fallback |
| `agents/a2a.py` | A2A client | **Official `a2a-sdk` client** against the deployed suppliers, per-call fallback to the built-in client; `/api/a2a` status |
| `agents/run.py` | Buyer logic + corrector | Generic `replan` (Gemini picks a fix from stated violations; rule fallback) |
| `suppliers/main.py` | A2A supplier server (separate Cloud Run service) | Richer inventories so the correction loop has real choices |
| `data/store.py` | Firestore access | Signed mandate, **transactional** hash-chain append (`meta/chain_tip`), per-instance append lock, auto-expiring controls, simulation lease |
| `data/scenarios.py`, `data/domains.py` | Eval sets | 26 travel scenarios (6 adversarial); 12 software scenarios + mandate |
| `ap2/` | Vendored official AP2 SDK (Apache-2.0) | Unmodified; `NOTICE-VENDORED.md` has source and commit |
| `data/ap2_open_mandates.json` | Public artifacts | Manager **public** key + three signed open mandates (no private keys) |

## 3. Frontend (`dashboard/public/index.html`, static, Firebase Hosting)
Single file (no build step). Four tabs (Live / Governance / Showcase / Replay); demo sign-in with roles; Firestore real-time listener with REST fallback; NDJSON stream consumer driving the flow diagram, cards and run summary; Live feed/inbox/KPIs/health/forms; simulated-traffic driver; guided-demo autopilot and recorded-run player; second-domain scoreboard; light/dark themes; mobile-safe. `dashboard/public/recordings/*.json` are real captured runs.

## 4. Tests and scripts
| Path | What it does |
|---|---|
| `tests/test_e2e_local.py` | ~115 checks with an in-memory Firestore and a rule-based Gemini stand-in; run **with AP2 on and off** (`TEST_AP2=0`). Covers streaming, controls, metrics, evidence, authorize + validation + rate limit, simulation lease, unprotected mode, chain concurrency (60 appends), control expiry, second-domain eval |
| `tests/test_a2a_official.py` | Official A2A client vs a real local supplier server; identical data; both fallbacks; kill switch |
| `scripts/smoke_live.py` | Live end-to-end suite against the deployed API (real Gemini): flows, AP2 re-verify, kill switch, 8 concurrent trips, chain intact, authorize, sim, and the full 26-scenario eval |
| `scripts/a2a_interop.py`, `scripts/ap2_spike.py` | Standalone proofs of official-SDK interop |
| `scripts/ap2_issue.py` | Manager-side key + open-mandate issuance (keys go to `~/.anvil/`, never the repo) |
| `scripts/record_runs.py` | Captures live runs into `dashboard/public/recordings/` |

Run locally (needs the pinned deps): `pip install -r requirements.txt` then `python -m tests.test_e2e_local` and `TEST_AP2=0 python -m tests.test_e2e_local`; live: `python scripts/smoke_live.py`.

## 5. Infrastructure and configuration
- **Cloud Run `anvil`** (Flask/gunicorn, 8 threads, concurrency 8, **min-instances 1**, max 10) and **`anvil-suppliers`** (min-instances 1). Python 3.14 runtime.
- **Firebase Hosting** (dashboard) and **Firestore** (`firestore.rules`: public read, no client writes).
- **Secret Manager** secret `anvil-ap2-orch-key` mounted as env `ANVIL_AP2_ORCH_KEY`.
- **Env vars:** `SUPPLIERS_URL`, `ANVIL_AP2_ORCH_KEY`, optional `ANVIL_API_KEY`, `ANVIL_SIGNING_KEY` (⚠ still the dev default — see limits), `ANVIL_CONTROL_TTL_S` (180), `ANVIL_RATE_PER_MIN` (120), `ANVIL_SIM_MIN_GAP_S` (20), `ANVIL_SIM_DAILY_CAP` (1500), `ANVIL_A2A_OFFICIAL` (`0` forces built-in), `GEMINI_MODEL`, `GEMINI_PRICE_IN_PER_M`/`OUT`.
- **Dependencies added:** `a2a-sdk==1.2.2`, `cryptography==46.0.5`, `jwcrypto==1.5.6`, `sd-jwt==0.10.4`, `pydantic==2.12.5` (pinned to what the AP2 repo tests against). The PyPI package named `ap2` is **not** Google's — never install it.

## 6. Known limits to be aware of when taking over
1. `ANVIL_SIGNING_KEY` (HMAC for the Intent/Cart mandates) is still the **dev default**. Setting a real key requires re-seeding the stored mandate (no admin endpoint exists yet).
2. Demo endpoints (`/approve`, `/reject`, `/api/control`, streams) are **public** by design for judging; the in-app sign-in is a UI-only demo.
3. One global provenance chain and one global control state (production would be per tenant/mandate).
4. AP2 payment instrument/payee data are demo values; no bank/PISP role.
5. Gemini cost figures are estimates from list prices.
6. **After judging, set Cloud Run min-instances to 0** on both services to stop idle cost.
