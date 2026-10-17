# Anvil — rubric self-check & submission checklist (Playbook Step D4)

Legend: ✅ done and verified · 🟡 prepared, needs you · ⬜ only you can do it

## Rubric walk-through
| Criterion | Evidence in the product |
|---|---|
| **Technical & Gen AI (40%)** | Gemini intent-drift auditor with structured JSON (temp 0, retries, cached-verdict fallback); multi-agent A2A (Agent Cards, JSON-RPC, 3 buyer agents + 3 supplier agents on a separate Cloud Run service); measured scoreboard: **Anvil 4/4 vs rules-only 1/4, 0 false blocks**, identical across repeated runs; signed AP2 Intent + Cart Mandates; hash-chained provenance. ✅ |
| **Impact (25%)** | Story: agents spend money today; nothing proves a human authorized it. Slide 9 needs the sourced figures from the project brief. 🟡 |
| **Innovation (25%)** | Guard + **self-correction** (block → explain → agent re-plans → audit again), `REVIEW` as one-tap re-consent instead of a block, tamper-evident trail with delegation chain. ✅ |
| **UX (10%)** | Professional dashboard: light/dark, responsive, live Firestore updates with REST fallback, mandate card with signature badge, trip board, drift → self-correction strip, scoreboard, replayable trail. ✅ |

## Submission checklist
- [ ] ⬜ **3-minute demo video**, public/unlisted link. Script + shot list: `docs/DEMO-VIDEO-SCRIPT.md`. (I can't record or upload it for you.)
- [x] ✅ **Deployed, reachable URL** — dashboard https://dazzling-lodge-511607-m0.web.app, API https://anvil-733520529727.us-central1.run.app, suppliers https://anvil-suppliers-733520529727.us-central1.run.app. Verified from a fresh browser load: populated dashboard, signature verified, chain verified, 15/15 scenario clicks identical.
- [x] ✅ **Code repo with README** — https://github.com/Adhi1402/anvil (README: pitch, measured results, architecture diagram, Google stack, how to run, honest claims).
- [ ] ⬜ **Make the GitHub repo public** (Settings → General → Danger Zone → Change visibility) if the rules require a public repo, and confirm `.env` is not in history (it is git-ignored; no keys were ever committed).
- [x] 🟡 **Pitch deck PDF** — `docs/Anvil-Pitch-Deck.pdf` (10 slides, source `docs/deck/deck.html`). **Fill the yellow `[ADD: …]` placeholders on slides 2, 9 and 10** (sourced stats from the brief, team, ask), then re-print: `msedge --headless --no-pdf-header-footer --print-to-pdf=Anvil-Pitch-Deck.pdf deck.html` (or open deck.html in Edge/Chrome → Print → Save as PDF, 1280×720, no margins/headers).
- [x] ✅ **Google-stack story explicit** — Gemini (Vertex AI), A2A, AP2, Cloud Run, Firebase, Firestore (README + slide 7).
- [ ] ⬜ **Anything else the rules require** — confirm exact rules on aibuildercup.com (team info, theme tag *Future of Work*, form fields, deadline). I could not check the live rules.
- [ ] ⬜ Open every link in an **incognito window** before submitting; submit with buffer before the deadline.

## Before you go live (security hardening — hackathon shortcuts to be aware of)
- Cloud Run endpoints (`/run/*`, `/approve`, `/reject`) are **public and unauthenticated**, and Firestore `provenance`/`mandates` are **publicly readable** so judges can click through. Anyone with the URL can trigger runs or approve a pending REVIEW. Acceptable for judging; lock down for real use.
- Set a real `ANVIL_SIGNING_KEY` on Cloud Run (`gcloud run services update anvil --update-env-vars ANVIL_SIGNING_KEY=...`). The `dev-only-key` default is used today, and the stored mandate is signed with it, so re-seed the mandate after changing the key (`python -c "import data.store as s; s.seed_mandate()"` with the same env var set).
- The Firebase web API key in `index.html` is public by design; access is governed by `firestore.rules` (public read, no client writes).

## Day-of (judgment day) checklist
- [ ] Hit the live URL once right before presenting (Cloud Run cold start).
- [ ] Keep a local fallback: `python main.py` (API on :8080) and the recorded video.
- [ ] Killer Q: *"How do you know it doesn't over-block?"* → 0 false blocks on legitimate actions, measured (`/api/eval`).
- [ ] *"Isn't this just a rules engine?"* → rules caught 1 of 4; Anvil 4 of 4 — it reasons about intent (refundability swap, class upgrade, split charge).
- [ ] Say "faithful to the A2A / AP2 model", not "fully SDK-compliant".
