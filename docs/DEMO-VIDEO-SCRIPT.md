# Anvil — 3-minute demo script (new Mission Control UI)

Before recording: open the dashboard, **Governance → New session** (clears the screen, keeps the chain). Use dark theme. Have the deck's Impact slide ready for 0:00. Do one dry run first: Gemini calls take 3-4 s each.

| Time | Beat | On screen | Say (suggested) |
|---|---|---|---|
| 0:00–0:20 | **Problem** | Title card, then the ANVIL header | "AI agents already book travel and spend company money. Nothing checks that they stayed inside what a human approved. Anvil is that check." *(add one sourced statistic here; do not invent numbers)* |
| 0:20–0:40 | **The mandate** | Scroll to **The authorization**. Point at the terms and the green *Signature verified* badge | "The manager signs a mandate: economy, refundable, preferred airlines, price caps. It's cryptographically signed; a forged copy is rejected." |
| 0:40–1:05 | **Clean request** | Click **✓ Clean trip**. Watch the diagram light up: request → A2A discovery → Gemini picks offers → Guard audits → Executor | "A Gemini booking agent discovers three supplier agents over A2A and picks offers. Anvil audits every proposal with Gemini before anything is booked. All three match; each gets a signed Cart Mandate." |
| 1:05–1:55 | **Hero beat** *(slow down)* | Click **😤 Tempt the agent**. The agent proposes Emirates business class. Card stamps **BLOCKED**, shows the reason and the 💸 counterfactual, then **SELF-CORRECTED** to Air India economy. The *Unauthorized spend stopped* meter ticks up | "The employee pushes for business class and the agent obliges. Anvil blocks it, explains exactly why, and tells the agent. The agent re-plans from that reason and the fixed booking passes. $590 of unauthorized spend, stopped before it happened." |
| 1:55–2:20 | **Attack** | Click **🗣 Fake “pre-approved” note** | "Here a rogue agent writes 'manager pre-approved this' on an over-cap fare. Free text can't authorize anything. Anvil still escalates it for the manager's one-tap approval." Click **Approve**. |
| 2:20–2:45 | **Governance** | Open the **Governance** tab. Point at agent scorecards, cost per audit, and click **⏸ Pause agent** on Hotel, then run the trip | "Operators get scorecards, cost of governing — about a fifth of a cent per decision — and a kill switch. Pause the hotel agent and its next action is blocked with no model call." |
| 2:45–3:00 | **Proof and close** | Scroll to the scoreboard (19/19 vs 10/19, 0 false blocks), then **⚠ Simulate tampering** on the trail | "Across 26 scenarios on live Gemini, Anvil caught 19 of 19 violations; rules-only caught 10. Zero false blocks. Every decision is in a tamper-evident chain. Today it's travel; the same engine governs procurement and cloud spend. Anvil." |

## Fallbacks
- If a run stalls, click **↺ New session** and retry; the backend is on Cloud Run and may cold-start on the first call (hit the URL once before recording).
- Local fallback: `python main.py` (API on :8080) and open the dashboard with `?api=http://localhost:8080`.
