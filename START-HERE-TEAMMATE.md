# START HERE — Teammate onboarding for Anvil

Welcome! This guide takes you from "nothing installed" to "running the whole project on your laptop", and explains what the project is so you can talk about it confidently. Do the parts in order; each step has a **✅ check** so you know it worked.

- **Project:** Anvil — a governance layer for autonomous spending agents (Travel & Expense). A manager signs a *mandate*; AI agents plan a trip; **Gemini audits every action** against the mandate and says `MATCH` (allow), `REVIEW` (ask the manager) or `DRIFT` (block, then the agent re-plans itself).
- **Repo:** https://github.com/Adhi1402/anvil
- **Live dashboard:** https://dazzling-lodge-511607-m0.web.app
- **Live API:** https://anvil-733520529727.us-central1.run.app
- **Google Cloud project ID:** `dazzling-lodge-511607-m0` (its display name is "Google AI builder"; always use the **ID**)

> **The project is already built and deployed.** You do *not* need to create a cloud project, enable services, or deploy anything to get started. You just need access, tools, and a login.

---

## Part 0 — Get access (ask the project owner, ~2 min)

Ask the owner (Adhish) to do these two things for the Google account **you** will use:

1. **GitHub:** repo → *Settings → Collaborators → Add people* → your GitHub username. Accept the email invite.
2. **Google Cloud:** console → *IAM & Admin → IAM → Grant access* → your Google email → role **Editor** (or Owner) on project `dazzling-lodge-511607-m0`.

**✅ check:** you can open https://github.com/Adhi1402/anvil, and https://console.cloud.google.com shows the project `dazzling-lodge-511607-m0` in your project list.

---

## Part 1 — Install the tools (~20 min)

| Tool | Get it | Notes |
|---|---|---|
| **Python 3.11+** | https://www.python.org/downloads/ | Tick **"Add Python to PATH"** in the installer |
| **Git** | https://git-scm.com/downloads | |
| **Google Cloud CLI (`gcloud`)** | https://cloud.google.com/sdk/docs/install | |
| **Node.js (LTS)** | https://nodejs.org | Only needed for the Firebase CLI |
| **VS Code** | https://code.visualstudio.com | Any editor is fine |

Then install the Firebase CLI (only needed if you will deploy the dashboard):
```powershell
npm install -g firebase-tools
```

Open a **new** PowerShell window and check each one prints a version:
```powershell
python --version
git --version
gcloud --version
node --version
```

### ⚠ Windows gotcha: "running scripts is disabled on this system"
If `gcloud` or `firebase` fails with *"cannot be loaded because running scripts is disabled"*, run this **once** (no admin needed), answer `Y`, then open a new window:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
(Or, without changing policy, call the `.cmd` versions: `gcloud.cmd ...`, `firebase.cmd ...`.)

---

## Part 2 — Get the code (~3 min)

```powershell
git clone https://github.com/Adhi1402/anvil.git
cd anvil
pip install -r requirements.txt
```

**✅ check:** `pip` finishes without red errors, and `dir` shows `main.py`, `agents`, `anvil`, `data`, `suppliers`, `dashboard`, `README.md`.

> **Never commit secrets.** `.env`, `*-key.json` are already in `.gitignore`. This project needs **no API keys** (see Part 3), so you should never need a `.env` at all.

---

## Part 3 — Log in to Google Cloud (~5 min)

The code talks to **Gemini (Vertex AI)** and **Firestore** using *your Google login*, not an API key. Run these three commands (a browser window opens for each login — use the Google account you were added with in Part 0):

```powershell
gcloud auth login
gcloud config set project dazzling-lodge-511607-m0
gcloud auth application-default login
```

**✅ check:**
```powershell
gcloud config get-value project
```
prints `dazzling-lodge-511607-m0`.

The **second** login (`application-default`) is the one Python uses. If you skip it you'll see *"Your default credentials were not found"*.

---

## Part 4 — Run it (the "does it work?" tour, ~10 min)

Run these from the repo folder, one at a time. Each shows a different layer of the system.

```powershell
python -m agents.run
```
→ Three agents (flight, hotel, transport) discover supplier agents and print **three proposed bookings**.
*(Local runs route the agent-to-agent calls in-process; production uses real HTTP between two Cloud Run services. Same code path.)*

```powershell
python -m anvil.audit
```
→ Gemini audits one clean action and prints JSON with `"verdict": "MATCH"`, plus the dumb `rules_baseline` result.

```powershell
python -m anvil.eval
```
→ **The scoreboard.** Five scenarios through Anvil *and* a rules-only baseline. Expect: Anvil catches 4/4 violations, baseline 1/4, **0 false blocks**. (Takes ~30 s: five Gemini calls.)

```powershell
python main.py
```
→ Starts the API on http://localhost:8080. Open these in a browser:
- http://localhost:8080/run/trip → full trip: three `MATCH` verdicts
- http://localhost:8080/run/business → `DRIFT` (business class blocked) then `MATCH` (agent self-corrects)
- http://localhost:8080/run/over-cap → `REVIEW` (needs manager approval)
- http://localhost:8080/api/verify → `{"chain_ok": true}`

> ⚠ **Heads-up:** your local runs write to the **same shared Firestore** as the live demo, so they appear on the live dashboard. That's fine while learning, but **don't spam runs right before a demo**, and **never edit or delete provenance entries by hand** — each entry is hash-chained to the previous one, so editing breaks the chain (the dashboard will show "chain broken").

**✅ check:** open https://dazzling-lodge-511607-m0.web.app and see your runs appear in the Provenance trail live.

---

## Part 5 — Understand the project (read in this order, ~30 min)

1. **`README.md`** — the pitch, architecture diagram, measured results, what we do/don't claim.
2. **The dashboard** — click the three buttons (*Clean trip*, *Borderline*, *Drift → self-correct*) and watch each section react. This *is* the demo.
3. **`ANVIL-Day1-Kickoff.md`** — how the project was bootstrapped (Part 4 is a Day-1 snapshot).
4. **`ANVIL-Build-Playbook-Day2-to-Submission.md`** — the build plan (Days 2–5) and the demo story.
5. **`docs/DEMO-VIDEO-SCRIPT.md`** and **`docs/SUBMISSION-CHECKLIST.md`** — what's left to ship.

### The story in one paragraph
A manager signs a **mandate** ("economy, preferred airlines, ≤ $600 flight, ≤ $300/night, refundable"). Three buyer agents (flight, hotel, transport) find suppliers over **A2A** and each proposes one booking. **Anvil** asks **Gemini** whether each action honors the *intent* of the mandate (not just the numbers): `MATCH` → allowed and gets a signed **Cart Mandate**; `REVIEW` → the manager gets an Approve/Reject button; `DRIFT` → blocked with a plain-language reason, and the agent **re-plans within policy by itself**. Everything is logged in a **hash-chained** provenance trail with a delegation chain (manager → orchestrator → agent → supplier).

### Where things live

| Path | What it is |
|---|---|
| `main.py` | The Cloud Run API: `/run/<scenario>`, `/approve/<id>`, `/reject/<id>`, `/api/mandate`, `/api/verify`, `/api/eval`, `/api/provenance` |
| `agents/run.py` | Buyer agents (flight, hotel, transport), the strict `replan()` used for self-correction, `plan_trip()` |
| `agents/a2a.py` | A2A client: discovers Agent Cards, sends JSON-RPC `message/send` |
| `suppliers/main.py` | Supplier agents as an A2A server (its own Cloud Run service) |
| `anvil/audit.py` | **The core:** Gemini auditor (JSON schema, temp 0, retries, cache) + the dumb `rules_baseline` |
| `anvil/guard.py` | propose → audit → if `DRIFT`, feed the reason back → re-plan → audit again |
| `anvil/eval.py` | The Anvil-vs-baseline scoreboard |
| `data/store.py` | Firestore access, mandate signing/verification (HMAC), Cart Mandates, hash-chained provenance, `verify_chain()` |
| `data/scenarios.py` | The 5 scripted test/demo scenarios |
| `dashboard/public/index.html` | The Firebase-hosted dashboard (live Firestore listener) |
| `firestore.rules`, `firebase.json` | Firestore security rules and Firebase Hosting config |
| `hello/` | The Day-1 "hello world" Cloud Run smoke test |

### Key words
- **Mandate (AP2 Intent Mandate):** the manager's signed authorization. Tampering with any field makes the signature fail.
- **Cart Mandate (AP2):** a signed per-purchase authorization, issued only after `MATCH` or an approved `REVIEW`.
- **A2A / Agent Card:** the agent-to-agent protocol; each supplier publishes a card at `/.well-known/agent-card.json` so agents *discover* it instead of hard-coding it.
- **Drift:** an action that looks plausible but breaks the human's intent (e.g. business class under budget, or splitting a charge to dodge a cap).
- **Provenance:** the append-only log; each entry includes the previous entry's hash so any edit is detectable.

---

## Part 6 — Make changes and share them

```powershell
git pull                      # always first, to get the others' work
# ...edit files...
git add -A
git commit -m "Short description of what you changed"
git push
```
Work on `main`, keep commits small, and **pull before you push**. If you change the auditor prompt (`anvil/audit.py`), re-run `python -m anvil.eval` **at least 3 times** and confirm Anvil still gets 4/4 with 0 false blocks and identical verdicts each time.

### Deploying (only when the team agrees)
```powershell
# supplier agents (A2A server)
gcloud run deploy anvil-suppliers --source suppliers --region us-central1 --allow-unauthenticated
# main API (keep SUPPLIERS_URL!)
gcloud run deploy anvil --source . --region us-central1 --allow-unauthenticated --set-env-vars SUPPLIERS_URL=https://anvil-suppliers-733520529727.us-central1.run.app
# dashboard + Firestore rules
firebase login
firebase deploy --only hosting,firestore --project dazzling-lodge-511607-m0
```
⚠ Deploying `anvil` **without** `SUPPLIERS_URL` makes it call suppliers in-process instead of over HTTP. Always include it. Test the live URL right after deploying.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, new window (Part 1) |
| `Your default credentials were not found` | Run `gcloud auth application-default login` |
| Firestore / Vertex **`PermissionDenied` / 403** | You're logged in with the wrong Google account, or you haven't been given the IAM role (Part 0). Check `gcloud auth list` |
| `404 NOT_FOUND ... model` | Use `gemini-2.5-flash` (the default). Override only via `GEMINI_MODEL`. `gemini-3.8-flash` returned 404 on Vertex for this project when we tried it |
| `429 RESOURCE_EXHAUSTED` | Gemini quota blip. The auditor retries and falls back to cached verdicts; just wait a few seconds and retry |
| `ModuleNotFoundError` | Run commands from the **repo root**, using `python -m anvil.eval` style (not `python anvil/eval.py`), and `pip install -r requirements.txt` |
| Dashboard says "chain broken" | Someone edited/deleted a provenance entry. Tell the owner; don't "fix" it by deleting more |
| `gcloud run deploy` fails with a Cloud Build permissions error | Already fixed project-wide (roles granted to the default Compute service account). If it recurs, ask the owner |
| Dashboard shows "connecting…" for a few seconds | Normal; it falls back to the REST API after 6 s |

---

## Current status & what's left (as of the last commit)

**Done and deployed:** signed Intent Mandate, A2A agents with Agent Cards, flight/hotel/transport trip, Gemini auditor with 3 verdicts, self-correction, `REVIEW` approve/reject, Cart Mandates, hash-chained provenance, scoreboard (Anvil 4/4 vs baseline 1/4, 0 false blocks), professional dashboard, README, deck PDF, demo script.

**Still to do (needs people, not code):**
1. ⬜ **Record the 3-minute demo video** and upload it as unlisted → script: `docs/DEMO-VIDEO-SCRIPT.md`.
2. ⬜ **Fill the yellow `[ADD: …]` boxes** in `docs/deck/deck.html` (slides 2, 9, 10: sourced stats from the project brief, team names, the ask) and re-print the PDF.
3. ⬜ **Check the contest rules** on aibuildercup.com (required fields, deadline) and **submit** — see `docs/SUBMISSION-CHECKLIST.md`.
4. ⬜ Make the GitHub repo **public** if the rules require it.
5. ⬜ Set a real `ANVIL_SIGNING_KEY` on Cloud Run before judging (then re-seed the mandate).

**Suggested split:** one person records/edits the video; one person fills the deck + checks the contest rules; both rehearse the demo using the dashboard buttons (not typed URLs) and hit the live URL once right before presenting.

Questions? Read the README first, then ask the owner. You've got this.
