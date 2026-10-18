# Anvil UI/UX audit and redesign (2026-10-18)

Method: read the whole front end (`index.html` before the rewrite, 1,131 lines), screenshotted every tab as the Employee, the Finance manager and the Operator at 1400 px and phone width, and walked the flows against the live API. Findings below are ordered by how much each one hurt the "this is a product" impression. "Fixed" means shipped in the rewrite and covered by the browser test (`scripts/e2e_ui.py`).

## The reported problem: every user saw the same screens

| # | Finding | Why it matters | Fix | Status |
|---|---|---|---|---|
| 1 | All four tabs, every button and the same global feed were shown to Rahul, Adhish and Swathy. Role only produced an error toast *after* a click ("Only a finance manager can approve"). | Looks like a demo skin, not a product. A user is shown things they cannot use. | Three role workspaces with different navigation and different default pages. Employee: *My requests*, *Policy*. Manager: *Approvals*, *My requests*, *Activity*, *Spend*, *Policy*. Operator: everything plus *Overview*, *Agents*, *Audit trail*, *Quality*, *Demo studio*. Pages a role cannot use are not in the menu and a direct link falls back to the role's home. | Fixed |
| 2 | The employee saw global KPIs and other people's (and simulated) decisions, and had no way to follow their own request after pressing Submit. | The main job of an employee is "did my request go through, and if not why". | *My requests* lists only the person's own requests, grouped (a trip request with its legs, a block followed by the agent's correction), with a plain status and a live update when a manager decides. | Fixed |
| 3 | The approval inbox was a small side card: no requester, no amount over the limit, no comment, and anyone could approve their own request. | Approval is the human-in-the-loop moment the whole pitch rests on. | *Approvals* page: who asked and when, why it needs a person, "$60 over the $600 flight limit", the requester's note flagged as *not* approval, an optional comment, Waiting / Decided tabs. The server now records the approver, the comment and the original requester, and refuses self-approval (403). | Fixed |
| 4 | Demo scaffolding (Showcase, Replay, ON/OFF switch, "Fake approval note" preset, simulated traffic) sat in the main navigation next to the product. | Judges read it as a prototype with a stage, not a product with a demo. | Moved into one **Demo studio** page (operator and guest only): Scenario lab, Guided demo, Recorded runs, Integrate. The product pages carry no demo controls. Runs are labelled "Demo agent" so they never impersonate a user. | Fixed |
| 5 | Sign-in offered a fake email/password form plus personas, and nothing said what each role would see. | Confusing; the form could only ever accept three emails. | Persona cards that say what each role sees, a prominent *Guest judge* path, and the email form tucked under "Sign in with an email instead". The demo disclaimer stays. | Fixed |
| 6 | A guest judge could not experience the roles without signing out. | The three-role story is the product story. | *View as* switch (Employee / Finance manager / Operator) in the header for the guest. Deep links: `?as=rahul`, `?as=adhish`, `?as=swathy`, `?as=guest`, `?theme=light|dark`. | Fixed |

## Information design and language

| # | Finding | Fix | Status |
|---|---|---|---|
| 7 | Jargon to business users: MATCH / REVIEW / DRIFT, mandate, Cart Mandate, provenance, AP2 chain, hashes. | Plain statuses everywhere: *Approved*, *Needs approval*, *Blocked*, *Rejected*, *Approved by Adhish Sekar*. "Mandate" becomes "policy" for non-operators. Technical detail (AP2 chain, delegation, hash, tokens) is one click away and shown in full only to operators. | Fixed |
| 8 | One 6-card KPI row plus agents plus five cards plus two scoreboards on a single Governance scroll; a "Stopped per $1 of Gemini: $60,879" tile that mostly reflected simulated attacks. | Split by job: *Overview* (what needs attention), *Agents*, *Audit trail*, *Quality*, *Spend*. The misleading ratio tile was dropped. | Fixed |
| 9 | The live feed had no filter, search, grouping, or way to hide simulated rows, and relative times went stale. | *Activity* has status filters, search, "Show simulated", paging, expandable rows, and times refresh every 30 s. | Fixed |
| 10 | Dark glow-and-grid styling, 11 px uppercase labels everywhere, emoji as icons. | Light-first neutral palette (dark mode kept, follows the OS), 14 px base text, one consistent icon set, status never conveyed by colour alone. | Fixed |
| 11 | The identity of the mandate signer (`manager@example.com`) does not match the finance manager persona. | Shown as "(finance owner)". The signed value itself is unchanged because it is covered by the signature. | Mitigated |

## Behaviour, feedback and trust

| # | Finding | Fix | Status |
|---|---|---|---|
| 12 | Kill switch, revoke and new session fired on one click. | Confirmation dialogs that say what will happen and that it auto-restores. Re-running the live eval warns about its cost and duration. | Fixed |
| 13 | Errors were toasts that vanished after 3 s; failed panels said "Could not load…" with no way forward. | Errors stay inline with a *Try again* button; toasts last 5 s and are announced to screen readers. | Fixed |
| 14 | Cold start (10 to 20 s on Cloud Run) showed "connecting…" with no explanation. | A banner explains the delay after 4 s; skeleton placeholders while data loads. | Fixed |
| 15 | The purchase form made an employee type vendor, amount and destination, and mixed attack presets ("Fake approval note") into the same row of chips as real use. | Form kept (it exercises `/v1/authorize`) but the headline path is *Plan a trip* in plain English; test cases live in a "Fill with an example" menu; amount must be above zero; a hint says a note never counts as approval. | Fixed |
| 16 | Simulated traffic ran for every viewer and its requests were counted as "by users". | Runs only for managers, operators and guests on feed pages; employees never see it; every simulated row is tagged *Simulated* and can be hidden. | Fixed |
| 17 | Operator controls and the audit trail had no explanation of what a "chain break" means. | The Audit trail page explains it in one sentence and offers *Verify now*, *Simulate tampering* (nothing is written) and *Replay in order*. | Fixed |

## Accessibility and responsiveness

| # | Finding | Fix | Status |
|---|---|---|---|
| 18 | Tabs were buttons without roles, feed rows were clickable divs, no focus ring, no skip link. | Real links for navigation with `aria-current`, `role="tab"` / `aria-selected` for sub-tabs, keyboard-operable rows (`role="button"`, Enter/Space), visible focus, skip link, `aria-live` regions, `prefers-reduced-motion` respected. | Fixed |
| 19 | The header wrapped to four rows on a phone; KPI cards orphaned in a 2-column grid. | Sidebar becomes a compact top bar with a scrollable menu below 960 px. Verified at 390 px for every page of every role: no horizontal overflow. | Fixed |

## Known limits (be upfront about these)
- Sign-in is still a labelled demo. Role-based screens are a UX layer; the API endpoints remain open so judges can click through. The only server-side rule is that a named approver cannot decide their own request.
- *My requests* is built from the 160 most recent entries in the live feed. With simulated traffic on for a long time an employee's oldest requests scroll out. A per-requester Firestore query with a composite index is the production fix.
- The "Demo studio" runs are real calls through the real pipeline, so they appear in Activity and the Audit trail (as "Demo agent").
- Chart-style visuals are deliberately simple (bars and tables with text labels). There is no time-series view yet.

---

# Round 2: would an enterprise actually run this? (2026-10-18)

The first pass fixed *who sees what*. The second pass asked a harder question: does the product model what a company really does when an employee travels? It did not. A "trip" was three loose purchases with no dates, no round trip, no traveller, no cost centre and no business reason, and the approver saw one booking at a time. Everything below is fixed and covered by `scripts/e2e_ui.py` (all checks pass) and by new checks in `tests/test_e2e_local.py`.

| # | Gap against real enterprise travel | Fix |
|---|---|---|
| 20 | **No dates or times anywhere.** Nothing said when a trip leaves, returns or when a booking was made. | Every booking carries real dates and times: flight number and departure/arrival, hotel check-in/out and nights, airport pickup time. Every request shows an absolute timestamp ("18 Oct, 14:32") and the relative one. |
| 21 | **No round trips or one-way trips.** A request was a single flight. | A trip is now outbound flight, airport to hotel, hotel (nights from the dates), hotel to airport, return flight. One way, round trip, hotel and transfers are all optional. Each leg is checked against its own limit; a 3-night stay is priced for every night and its receipt covers the full stay. |
| 22 | **No trip context.** No purpose, cost centre or business reason, so finance could not charge or judge a request. | The form asks for purpose, cost centre and a business reason (required when the trip needs an exception). They travel with every booking, show on the approval card, in Spend by cost centre and in the CSV export. |
| 23 | **Policy that only looked at prices.** Real policy also has advance-notice and trip-length rules. | Two company rules run beside the signed spending limits: at least 7 days' notice and at most 14 days away. Breaking one is escalated as an exception, never blocked, and the form warns before you submit. They are deterministic code, not model judgement, and the auditor never sees trip dates, so the 26-scenario evaluation is unaffected. |
| 24 | **Approving a trip meant approving five separate items.** | Approvals are grouped by trip: one card with the whole itinerary, who asked and when, the dates, how long it has waited, the departure countdown, and one comment with *Approve all* / *Reject all*. Queue sorted by soonest departure. The reason shared by several legs ("booked 3 days ahead") is stated once. |
| 25 | **No way to take a request back.** | The requester can withdraw a pending trip. Recorded in the audit chain as a decision by the requester, and it leaves the approval queue. |
| 26 | **Employees were not told when someone decided.** | A notification appears the moment a manager decides ("Adhish Sekar approved your trip to Mumbai"). |
| 27 | **Roles did not separate duties.** The operator could approve spend, so the people who run the agents could also release money. | Approving is a finance-manager action only. The operator runs the agents, audit and quality and cannot approve. Finance gets an emergency stop (revoke the policy) because they are the people who would want it. A "Who can do what" table on the Policy page states it. The demo studio's approve buttons stay as a labelled stand-in for the finance manager. |
| 28 | **Finance could not slice spend.** | Spend by cost centre, bookings per requester, activity search by city or cost centre, and CSV export of the filtered activity. |
| 29 | **Employee had no sense of the trip's life cycle.** | Each trip shows Departs in N days / Departs today / In progress / Completed, total cost, and how much is still awaiting approval. |
| 30 | **The trip form accepted anything.** | Live validation (dates in the past, return before departure, a hotel with zero nights), a live estimate of the legs and the most the policy allows without approval, and a clear refusal for a city the policy does not cover (it needs a trip authorization from finance). |

## Still open (honest list)
- **Single destination.** The signed policy covers one city (Mumbai). A real deployment would hold approved destinations per employee grade and a per-trip authorization; the form refuses other cities rather than pretending.
- **No traveller-versus-requester split.** An employee books for themselves. Booking on behalf of a colleague, and a line-manager step before finance, are the next approval chain.
- **Schedules are mock supplier data** with fixed times of day; dates are real, flight inventory is not. Times are shown as local airport times.
- **Cancelling or changing an approved trip** is not modelled.
- Sign-in is still the labelled demo (see the first-round limits above).
