> **Superseded:** the current beginner guide, narration and timing are in `submission/DEMO-VIDEO-GUIDE.md`. Notes below describe an earlier version of the app.

# Anvil — 3-minute demo script (short form)

> **The full, current version (UI flow, timings, voice-over text, fallbacks) is in `docs/handover/01-UI-FLOW-AND-DEMO-PITCH.md`.** This file is the one-page cheat sheet. The app is role-based since the UI rewrite (see `docs/UX-AUDIT.md`).

**Before recording:** open the site (warms Cloud Run). Three browser tabs: `?as=swathy` (operator), `?as=rahul` (employee), `?as=adhish` (manager). In the operator tab: Audit trail → **Start a new session**; Agents → confirm nothing is paused. 100–110 % zoom, leave Overview open for a minute so simulated agents fill the feed. Single-window option: Guest judge + the **View as** switch.

| Time | Who / page | Do | Say (gist) |
|---|---|---|---|
| 0:00–0:20 | Sign-in | Show the page, sign in as Swathy | Agents spend company money; nothing checks they stayed inside what a human approved. **[add a sourced statistic]** Three roles: employee, finance manager, operator |
| 0:20–0:50 | Operator → Overview | Latest decisions (SIMULATED), KPIs, Needs attention | The control room; every decision checked against a signed policy; AP2-verified; tamper-evident |
| 0:50–1:30 | Rahul → My requests | Single purchase → *Business-class flight* → Submit | Blocked, why, what it would have cost; the agent self-corrects; receipt re-verified |
| 1:30–2:05 | Rahul, then Adhish → Approvals | *Flight over the cap* → Submit; switch tab; add a comment → Approve; back to Rahul | A person stays in charge; a "pre-approved" note carries no authority; Rahul sees "Approved by Adhish Sekar" |
| 2:05–2:30 | Operator → Demo studio | Enforcement **OFF** → *Business-class swap* → **ON** → same chip | No control = $590 leaked; with Anvil: blocked, explained, corrected |
| 2:30–2:45 | Operator → Agents, Audit trail | **Pause** Hotel → resume; **Simulate tampering** | Kill switch with no model call; any edit breaks the chain |
| 2:45–3:00 | Operator → Quality | Scoreboards | 19/19 vs 10/19, 0 false blocks; software 8/8 vs 6/8 |

**Hands-free alternative:** Demo studio → Guided demo → Start. **Fallback if anything stalls:** Demo studio → Recorded runs.
