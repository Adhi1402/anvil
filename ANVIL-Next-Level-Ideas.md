# Anvil — Next-Level Ideas

> **Status note (2026-10-18):** this is the *idea log* from planning. Most Tier-1/2 items are now built (counterfactual receipts, failure taxonomy, adversarial set, kill switch, governance metrics, second domain, enforcement contrast, guided demo). What is still only an idea: policy what-if, mandate lint, earned autonomy, cross-model referee, phone-approval QR. For what actually exists, see `docs/handover/`.

Ideas to raise Anvil from "working demo" to "hard to beat" in the AI Builder Cup (Future of work and enterprise productivity track, deadline Oct 18).

Legend for effort: **S** = under 2h · **M** = 2–4h · **L** = 4h+. "Needs Gemini" means it can't be verified without Vertex credentials.

> Principle: judges remember one clear story. Three strong additions beat eight half-finished ones. Everything below must still fit a 3-minute demo.

---

## PLAN v2 (current): scored against the official rubric

Rubric (from the AI Builder Cup screenshot): **Technical Merit & Gen AI 40% · Problem Alignment & Impact 25% · Innovation & Creativity 25% · UX & Solution Design 10%.**
Required to demonstrate: problem and why it matters · how the solution addresses it · how Google AI is integrated · working prototype · how it is deployed on GCP.

### Weaknesses found in the audit, and the fix for each
| Weakness | Fix | Rubric |
|---|---|---|
| Buyer agents are scripted Python, not agentic | Gemini planner agent: typed request + A2A offers -> chooses each leg, with rationale; scripted fallback | Technical 40 |
| No cost/latency visibility | One Gemini wrapper records tokens, latency and est. cost per call; stored on every audit | Technical 40 |
| Run result appears all at once (feels canned) | NDJSON streaming: every step is logged and shown as it happens | Technical + UX |
| Eval is only friendly cases | 6 adversarial scenarios (fake "pre-approved" notes, prompt injection, authority claims), new `injection` type | Technical + Innovation |
| Only per-decision view, nothing for operators | Governance Console: `/api/metrics`, agent scorecards, cost and ROI, budget burn, drift analytics | Impact 25 |
| No way to stop an agent | Kill switch: pause an agent or revoke the mandate; logged to the chain | Innovation 25 |
| "Audit-ready" is a claim | `/api/evidence` evidence pack (mandate + audits + receipts + chain status) | Impact 25 |
| Demo log is polluted by tests | "New session" marker (nothing deleted, chain intact); metrics scope to the session | UX / demo |
| Page looks like a report | Dark "Mission Control" UI: command bar, animated flow diagram, verdict reveals, money meter, governance tab | UX 10 |

### Build order
1. Backend foundations: Gemini wrapper with telemetry · adversarial scenarios · Gemini planner agent · streaming guard + step persistence · controls (kill switch, session) · `/api/metrics` · `/api/evidence`. Tests, deploy, live smoke.
2. UI: dark Mission Control + Governance Console on a Firebase preview channel, then promote.
3. Submission polish: README + deck numbers, requirements-mapping slide, impact stats, video script.

---

## Status of the baseline work (A1–A3)

Done in code, **not yet validated with live Gemini** and not committed:

| Item | What changed | Files |
|---|---|---|
| A1 Real correction loop | Gemini reads the auditor's violations plus supplier offers and picks a fix; re-audited, up to 2 attempts; now works for flights, hotels and transport; rule-based fallback if Gemini is down | `agents/run.py`, `anvil/guard.py`, `suppliers/main.py` |
| A2 Bigger eval | 20 scenarios (7 legit, 6 REVIEW, 7 DRIFT); fairer baseline (per-type cap + destination + supplier); exact-match, false-block and stability metrics | `data/scenarios.py`, `anvil/eval.py`, `anvil/audit.py` |
| A3 Stability | `python -m anvil.eval 3` and `/api/eval?refresh=1&repeats=3`; verdicts flag whether they came from the cache fallback | `anvil/eval.py`, `main.py` |

**Before any claim goes in the README or deck:** run `python -m anvil.eval 3` with real credentials and use the real numbers. The old "4/4 vs 1/4" headline is stale: it came from 4 violations and a weaker baseline.

---

## Tier 1 — could change how judges see the project

### 1. Red-team attacker agent
An adversary agent tries to push unauthorized purchases past the auditor: split charges, innocent phrasing, injected notes like "manager pre-approved this", unit tricks (INR vs USD). The dashboard shows attacks blocked vs slipped through. Every miss becomes a permanent regression scenario.
- **Why it wins:** turns "does it over-block or under-block?" into a visible adversarial test, and shows prompt-injection resistance.
- **Scope for a day:** 8–10 scripted attacks plus a Gemini-generated variant set. Run it beforehand and show the fixed rate with the failures you patched.
- **Risk:** it may find real misses. Better to find them now than in front of judges. **Effort: M · Needs Gemini**

### 2. Counterfactual receipts and "prevented spend"
For every blocked or escalated action, show what would have happened: "Would have spent $590 on a class never approved, $110 over cap, no refund path." Total the avoided overspend on the dashboard.
- **Why it wins:** gives a business-value number per block and maps directly to the Impact criterion.
- **Note:** compute the figure from the action vs the mandate (overage over cap, unapproved amounts) rather than asking Gemini to invent it, so the number is defensible. **Effort: S–M**

### 3. Mandate as a conversation (negotiated amendments)
`REVIEW` becomes a short exchange: "Cheapest compliant option is $660 (+$60). Approve?" The manager answers in plain language ("yes, but only if refundable") and Gemini turns it into a signed amendment chained to the original mandate.
- **Why it wins:** human-in-the-loop that isn't a rubber stamp, and the trail shows how authority evolved. **Effort: M–L · Needs Gemini**

### 4. Cross-model referee
Two independent audits (for example Gemini Flash and Gemini Pro). Agreement proceeds; disagreement escalates to `REVIEW`.
- **Why it wins:** a direct answer to "what if Gemini is wrong?" and it turns model uncertainty into a safety feature.
- **Cost:** doubles audit latency and spend; show the numbers. **Effort: S–M · Needs Gemini**

---

## Tier 2 — strong, more work

### 5. Natural-language mandate
The manager types the rules in plain English; Gemini produces the structured mandate for the manager to confirm and sign. Puts Gemini at both ends of the flow. **Effort: M · Needs Gemini**

### 6. Mandate stress-test before signing
Before signing, Gemini generates tricky scenarios against the proposed mandate and flags gaps ("nothing says whether taxis vs car rental are allowed"). Treats the mandate itself as testable. **Effort: M · Needs Gemini**

### 7. Second domain (procurement / SaaS / cloud purchases)
Generalize the audit prompt to read each mandate's own constraints instead of naming flight fields, then add 4–5 procurement scenarios with their own mandate and a Travel / Procurement split on the scoreboard. The strongest answer to "is this just travel?" **Effort: M**

### 8. Per-agent trust score
Agents that repeatedly drift get tighter limits; clean histories earn lower friction. Uses the audit log for something beyond display. **Effort: M**

### 9. Phone-style approval moment
Render `REVIEW` as a push-style message on a phone mock ("Approve $660 flight? Y/N"). Simulated on screen is enough for the video. **Effort: S**

### 10. Drop-in SDK shape
Show a ~10-line `@anvil.guard` decorator that wraps any agent framework's purchase tool (ADK, LangChain). Signals "building block others can adopt". **Effort: S–M**

---

## Tier 3 — framing moves (cheap, high return)

### 11. Named failure taxonomy
Four drift types, with every scenario tagged and catch rates shown per type:
- **Scope drift:** wrong destination, unapproved service
- **Substitution drift:** non-refundable for refundable, business for economy
- **Structuring:** splitting charges to dodge a cap
- **Smuggling:** hidden add-ons and extra fields

A shared vocabulary makes the work read as research, not a demo. **Effort: S**

### 12. "Agents are the new employees" narrative
Frame Anvil as expense policy and approval limits for AI staff, which companies already apply to people. Fits Future of work and is easy to say in one breath. **Effort: S**

### 13. Publish the eval as a benchmark
Release the scenarios as "AnvilBench: mandate-deviation tests" with a one-command runner and per-type results. **Effort: S**

### 14. Pitch line
> AP2 proves who authorized a payment. Anvil proves the payment is still what they meant.

Pitch A2A and AP2 as the standards Anvil plugs into, not as inventions. Claim the combination (signed mandate + semantic check + deterministic enforcement + correction loop + measured eval), not any single piece.

---

## Demo upgrades

| Idea | Effort | Notes |
|---|---|---|
| "Live attack" box: free-text request, then a timeline of attempt → block → reason → self-correction → receipt | M | The strongest 30 seconds of the video |
| Split screen: "agent only" vs "agent + Anvil" with dollars leaked | M | Pairs with idea 2 |
| Tamper button: edit an old log entry and watch chain verification turn red | S | Endpoint `/api/verify` already exists |
| Gemini latency and cost per audit on the dashboard | S | Pre-empts "is it too slow or expensive?" |

---

## Hardening (must-do before going live)
- Set a real `ANVIL_SIGNING_KEY` on Cloud Run and re-seed the mandate.
- Protect `/approve` and `/reject` with a simple token (works in the demo).
- Make the GitHub repo public; confirm no `.env` in history.
- Check the live rules on aibuildercup.com (team info, theme tag, form fields).

## Submission to-dos only the team can do
- Fill the `[ADD: …]` placeholders on deck slides 2, 9 and 10 and re-export the PDF.
- Record the 3-minute demo video from `docs/DEMO-VIDEO-SCRIPT.md`.
- Open every link in an incognito window before submitting, with buffer before the deadline.

---

## Recommended build order

| # | Item | Why now |
|---|---|---|
| 1 | Validate A1–A3 with live Gemini; fix labels or prompt as needed | Everything else depends on real numbers |
| 2 | Counterfactual receipts (2) + failure taxonomy (11) | Cheap, strong Impact and framing, needs no live model |
| 3 | Red-team attacker (1), scaled down | Biggest credibility gain |
| 4 | Natural-language mandate (5) or cross-model referee (4) | Pick one; puts Gemini at the center |
| 5 | Second domain (7) | Answers "is it only travel?" |
| 6 | Live attack box and split screen | Turns the work into a 3-minute story |
| 7 | Hardening + submission to-dos | Non-negotiable before the deadline |

Skip 8–10 unless time is left over.
