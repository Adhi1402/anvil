# Anvil — 3-minute demo video: script & shot list (Playbook Step D2)

**You record this** (screen + voice). Everything below is tested against the live dashboard: https://dazzling-lodge-511607-m0.web.app
Record each beat separately and stitch; add captions. Record at 1080p, browser zoom 100%, dark or light mode (both work). Before recording: open the URL once to warm Cloud Run, and hard-refresh.

**Buttons (control bar, top):** `Clean trip` (~13 s) · `Borderline (REVIEW)` (~5 s) · `Drift → self-correct` (~9 s). Rehearse by clicking these, not typing URLs.
**Tip:** the page shows "Running …" while a scenario runs. Wait for "complete." before moving on; use the wait to narrate.

| Time | Beat | On screen | Say (suggested) |
|---|---|---|---|
| 0:00–0:20 | **The problem** | Title card, then the ANVIL header | "AI agents already book travel and spend company money. But nothing checks that they stayed inside what a human actually approved. Anvil is that check." *(Add one sourced stat from the project brief here — we do not invent numbers.)* |
| 0:20–0:45 | **The signed mandate** | Scroll to **The authorization** card. Point at the terms, then the green **✓ Signature verified** badge. Click **Test a tampered copy** → red "✗ rejected — signature does not match". | "The manager signs a mandate: economy, preferred airlines, price caps, refundable. It's cryptographically signed. Watch what happens to a forged copy — someone raised the flight cap to 99,999. Rejected." |
| 0:45–1:15 | **Happy path** | Click **Clean trip**. While it runs, narrate. Show **Trip board**: Flight / Hotel / Transport all green MATCH. Scroll to the **Provenance trail**: three entries with the delegation line and 🧾 Cart Mandate. | "One mandate, three agents. They discover each other over A2A, negotiate, and propose bookings. Anvil checks each against the mandate — all match. Every entry traces back to the one human approval: manager, orchestrator, agent, supplier." |
| 1:15–2:05 | **The hero beat** *(slow down)* | Click **Drift → self-correct**. The **Drift → self-correction** strip appears: red BLOCKED (Emirates business $590) → arrow → green SELF-CORRECTED (Air India economy $480). Read the red reason aloud. Then click **Borderline (REVIEW)**: gold *Needs manager approval* card → click **Approve** → trail shows APPROVED. | "Rushing to hit a deadline, the agent books business class on a non-preferred airline. Price is under the cap — a rules engine would let it through. Anvil blocks it and says why: the cabin class doesn't match what the manager authorized. And it doesn't just say no — the agent re-plans on its own: economy, preferred carrier, refundable, booked. A borderline case isn't blocked, it's escalated: one tap from the manager." |
| 2:05–2:35 | **The proof** | Scroll to **Scoreboard**. Highlight the headline and the ✗ marks in the *Rules-only caught* column. | "Same five actions, two systems. A rules-only baseline caught one of four violations. Anvil caught all four — including the refundability swap, the class upgrade and the split charge a rule can't express — with zero false blocks on legitimate actions." |
| 2:35–3:00 | **The vision** | Scroll to the trail, point at **🔗 chain verified**, click **▶ Replay**. End on the ANVIL wordmark. | "Every decision is in a hash-chained, tamper-evident trail you can replay. Today it's travel and expenses; the same engine governs cloud spend, SaaS and procurement — the control plane for agent spending. Anvil." |

## Checklist before you hit record
- [ ] Open the live URL once to warm Cloud Run (cold start adds a few seconds).
- [ ] Click each of the 3 buttons once as a dry run; confirm the strip + trip board look right.
- [ ] If a run fails on stage, the verdicts are cached and stable (temperature 0); just click again.
- [ ] Fallback if Wi-Fi dies: run locally (`python main.py`, API at http://localhost:8080) and use the recorded video.

## Publish
- [ ] Upload as **unlisted** on YouTube, open the link in an incognito window, confirm it plays and is ≤ 3:00.
