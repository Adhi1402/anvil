# Submission form text

## Brief description (limit: 1024 characters excluding spaces; this one is 957)

Anvil is a domain-neutral policy-enforcement engine for AI agents that spend company money. A person signs a mandate; for every action an agent proposes, Gemini judges it against the mandate's intent, code enforces hard limits (company rules plus Google's AP2 SDK), and the verdict is approve, send to a person, or block. A blocked agent is told why and corrects itself, and the fix is audited again. Our enterprise example is business trip booking: an employee plans a trip, a Gemini agent compares offers from A2A supplier agents, and finance approves exceptions and edits the signed policy. Employees, finance managers and platform operators each get their own workspace. Every decision is hash-chained, and every Gemini call is traced with its exact input and output. Gemini 2.5 Flash on Vertex AI plans, audits and corrects. Cloud Run runs the API and supplier agents. Firestore holds the tamper-evident log, policy versions and AI traces, and streams live decisions. Firebase Hosting serves the web app. Measured live: 19/19 violations caught vs 10/19 for rules-only, 0 false blocks; software purchases run on the same engine (8/8).

---

## Longer version (for the deck, README or Q&A)

**Anvil: spend control for AI agents.** Anvil sits between autonomous AI agents and company money. Finance signs a travel policy (limits, approved cities, notice and trip-length rules). An employee plans a trip with real dates, one way or round trip; a Gemini booking agent compares real offers from supplier agents over the A2A protocol and picks one per leg (flights, airport cabs, hotel). Before any money moves, Anvil audits every booking: Gemini judges the booking against the intent of the signed policy, company rules and Google's AP2 SDK check the hard limits, and the verdict is enforced in code as approve, send to a finance manager, or block. A blocked agent is told exactly why and corrects itself, and the correction is audited again. Approved bookings get a signed receipt and a day-by-day itinerary. Every decision is written to a tamper-evident log, and every Gemini call is stored with its exact input and output on an AI traces page. Measured live: 19 of 19 violations caught vs 10 of 19 for a rules-only check, with 0 false blocks.

**How we use Firebase, Firestore, Cloud Run and Gemini**
- **Gemini (Vertex AI, Gemini 2.5 Flash):** three jobs, all with structured JSON output at temperature 0: the booking agent (plans each trip), the auditor (judges every booking against the signed policy), and the corrector (picks a compliant alternative after a block).
- **Cloud Run:** two services. `anvil` is the API (planner, Anvil Guard, policy and approvals, evidence); `anvil-suppliers` hosts the flight, hotel and transport agents as A2A servers with Agent Cards. Deployed from source with Cloud Build.
- **Firestore:** the system of record. A hash-chained audit log (each entry carries the hash of the previous one, appended in a transaction so the chain cannot fork), the signed policy and its version history, the kill-switch state, and the full input and output of every Gemini call. The browser listens to the audit log live, so approvals and decisions appear in real time.
- **Firebase Hosting:** serves the web app, with three role workspaces: employee, finance manager and platform operator.
- Also: Secret Manager (AP2 orchestrator key) and the official A2A and AP2 SDKs.

**Links**
- Prototype: https://dazzling-lodge-511607-m0.web.app (choose a person, or continue as a guest judge and switch roles)
- Repository: https://github.com/Adhi1402/anvil

**Honest limits:** the demo sign-in is UI-only, the spending executor and supplier data are simulated, and the benchmark scenarios were written by our team.
