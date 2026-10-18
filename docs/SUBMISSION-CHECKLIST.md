# Anvil — rubric self-check & submission checklist (current as of 2026-10-18)

Legend: ✅ done and verified · 🟡 prepared, needs you · ⬜ only you can do it

## Rubric walk-through (Technical 40 · Impact 25 · Innovation 25 · UX 10)
| Criterion | Evidence in the product |
|---|---|
| **Technical Merit & Gen AI (40%)** | Gemini 2.5 Flash on Vertex AI is the booking agent, the auditor and the corrector; structured JSON at temperature 0 with retries/timeouts and per-call cost/latency telemetry; **official `a2a-sdk` client** discovers and calls the supplier agents; **official AP2 V2 SDK** verifies a mandate chain per approved booking as a deterministic second gate; transactional hash-chained audit log; live eval **19/19 vs 10/19 (travel, 26 scenarios, 6 adversarial) and 8/8 vs 6/8 (software)**, 0 false blocks, stable across repeats; ~115 local checks in two modes + a live smoke suite incl. 8 concurrent runs. ✅ |
| **Problem alignment & impact (25%)** | Agents spend company money; nothing proves a human authorized it. Counterfactual receipts, unprotected-vs-protected contrast, evidence pack, cost of governing. **Deck slides 2, 9, 10 still need the sourced statistic, team and ask.** 🟡 |
| **Innovation & creativity (25%)** | Semantic drift vs a signed mandate stacked with AP2's deterministic limits; block→explain→self-correct loop; failure taxonomy; prompt-injection posture; second domain; kill switch; "AP2 proves who authorized it, Anvil proves it's still what they meant". ✅ |
| **UX & solution design (10%)** | Role-based app (employee, finance manager, operator workspaces; see docs/UX-AUDIT.md) with simulated traffic and a demo sign-in, operator pages, Demo studio, Showcase stage with enforcement ON/OFF, Replay (guided demo + recorded runs), dark/light, mobile-safe. ✅ |

## Required demonstrations (competition brief)
- [x] ✅ Problem and why it matters — deck + `docs/handover/04-WHY-ANVIL-PRODUCT.md`
- [x] ✅ How the solution addresses it — README, `docs/handover/03-ARCHITECTURE-AND-DESIGN-FLOW.md`
- [x] ✅ How Google AI is integrated — Gemini (Vertex AI), A2A, AP2, Cloud Run, Firestore, Hosting, Secret Manager (README table, deck slide 7)
- [x] ✅ Working prototype — https://dazzling-lodge-511607-m0.web.app
- [x] ✅ Deployed on GCP — Cloud Run `anvil` + `anvil-suppliers`, Firebase Hosting, Firestore

## Submission checklist
- [ ] ⬜ **Push the local commits** to `github.com/Adhi1402/anvil` (this machine has no GitHub credentials).
- [ ] ⬜ **3-minute demo video** (public/unlisted). Script and voice-over: `docs/handover/01-UI-FLOW-AND-DEMO-PITCH.md` (short form: `docs/DEMO-VIDEO-SCRIPT.md`).
- [ ] 🟡 **Pitch deck** `docs/Anvil-Pitch-Deck.pdf` (10 slides; source `docs/deck/deck.html`). **Fill the yellow `[ADD: …]` placeholders on slides 2, 9, 10** (sourced statistic, team, ask), then re-print: `google-chrome --headless=new --no-sandbox --no-pdf-header-footer --print-to-pdf=docs/Anvil-Pitch-Deck.pdf docs/deck/deck.html`.
- [ ] ⬜ **Make the GitHub repo public** and confirm no secrets in history (`.env` is git-ignored; AP2 private keys live in `~/.anvil/`, not the repo; the orchestrator key is in Secret Manager).
- [ ] ⬜ **Check the live rules on aibuildercup.com** (team info, track = *Future of work and enterprise productivity*, form fields, deadline).
- [ ] ⬜ **Submission form text** — see "Brief description" wording in `docs/handover/04-WHY-ANVIL-PRODUCT.md` and the safe claims below.
- [ ] ⬜ Open every link in an **incognito window** before submitting.

## Safe claims (use these words)
- "Interoperates with Google's official A2A client; the buyer agents use it" · "Mandate chains are built and verified with Google's official AP2 SDK" · "Measured on our own labelled scenarios".
- **Never:** "fully A2A/AP2 compliant", "completely novel", or an unsourced statistic.

## Known gaps (state them if asked)
- HMAC mandate signing still uses the dev default key (`ANVIL_SIGNING_KEY`); demo endpoints and the in-app sign-in are open/UI-only for judging; one global chain; executor simulated.

## Cost hygiene
- Both Cloud Run services run **min-instances 1** (fast first click). **After judging:** `gcloud run services update anvil --region us-central1 --min-instances 0` and the same for `anvil-suppliers`. Consider a GCP billing budget alert; the Gemini-calling endpoints are public.

## Day-of
- [ ] Open the dashboard 2 minutes before (warms Cloud Run); sign in; Governance → New session; no agent PAUSED.
- [ ] Keep the recorded video, the deck PDF and **Replay → recorded runs** ready as fallbacks.
- [ ] Killer Qs: *"Isn't this a rules engine?"* (10/19 vs 19/19) · *"What if Gemini is wrong?"* (REVIEW + deterministic enforcement + 0 false blocks) · *"vs AP2?"* (they stack; we measured the gap).
