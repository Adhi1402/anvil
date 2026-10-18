# 04 · Why Anvil: product description, usefulness, uniqueness

## One line
**Anvil is a mandate enforcement layer for autonomous business actions: it checks every action an AI agent takes against what a human actually authorized, blocks or escalates what drifts, helps the agent fix itself, and proves it all.**
Travel and expense is the first use case; the same mechanism applies to software licenses, procurement and cloud spend.

## The problem
Companies are starting to let AI agents spend money on their behalf: booking trips, renewing licenses, buying cloud resources. The risks are different from a human overspending:
- **Agents are helpful in the wrong way.** Asked for "the best option", an agent books business class. Asked to "save time", it splits a purchase to avoid an approval limit or adds a paid extra.
- **Rules can't see intent.** A budget cap and a supplier allowlist pass a $590 business-class fare at an approved supplier, a fare split into two charges under the cap, or a membership hidden in the extras.
- **Nobody can prove what was authorized.** When an agent's purchase is questioned, there is no record tying it to a specific human approval.
- **Agents can be talked into things.** A note saying "the manager pre-approved this" or an instruction hidden in a supplier's text can hijack a naive check.

## What Anvil does
1. **Human-approved mandate.** A manager signs what is allowed: destination, class, price caps, approved suppliers, refundability, preferred airlines.
2. **Semantic audit by Gemini.** Every proposed action is judged against the mandate's *letter and intent*, returning `MATCH` (allow), `REVIEW` (a person decides) or `DRIFT` (block), with the exact violations and a plain-language reason.
3. **Deterministic enforcement outside the model.** Only allowed actions (or human-approved escalations) get a signed receipt. Google's official **AP2 SDK** checks amount and payee limits as an independent second gate.
4. **Self-correction.** A blocked agent is told *why*; it re-plans a compliant alternative, which is audited again.
5. **Proof.** Every step goes into a hash-chained, tamper-evident log; each approved booking carries an AP2 mandate chain anyone can re-verify; an evidence pack can be exported.
6. **Operations.** A live feed, an approvals inbox, per-agent scorecards, a kill switch, cost-of-governing telemetry, and an integration endpoint (`POST /v1/authorize`).

## Who it is for and why it is useful
| Who | What they get |
|---|---|
| **Finance / procurement leaders** | Autonomous spend with a signed limit, a reason for every block, and an audit-ready record (evidence pack) instead of trust |
| **Platform / security teams** | A kill switch (pause an agent or revoke authority in one click, no redeploy), failure taxonomy, cost and latency visibility |
| **Employees** | Agents that fix themselves instead of failing, and one-tap approval for borderline cases |
| **Teams building agents** | One call before any spend: `allow / escalate / block`, plus an AP2 chain and receipt |

**Illustrative value (from the demo, not a customer claim):** in a demo session a single blocked business-class swap stops $590 of unauthorized spend for about $0.002 of Gemini cost per audit. Present the *mechanism*, not extrapolated savings.

## What makes it different (honest framing)
We do **not** claim that nothing similar exists: policy engines, LLM guardrails and AP2 all exist. The distinctive thing is the **combination, measured**:

| Approach | What it checks | What it misses |
|---|---|---|
| Budget caps + allowlists (rules engine) | Price, supplier, destination | Class/refundability swaps, split charges, hidden add-ons, manipulation (**caught 10 of 19**) |
| LLM guardrails / content filters | Harmful or off-topic text | Whether a purchase matches a specific signed authorization |
| **AP2 alone** | Who authorized a payment; deterministic limits (amount, payee, dates) | Semantic drift: a $590 business-class booking at an approved price passes its limits |
| **Anvil** | Intent vs a signed mandate **and** AP2's deterministic limits | — (see limits below) |

Distinctive elements, each demonstrable:
1. **Semantic drift detection against a signed mandate** — 19/19 on our scenarios vs 10/19 for a fair rules baseline, with 0 false blocks.
2. **Closed correction loop** — block, explain, self-correct, re-audit.
3. **Two independent gates, both Google's stack** — Gemini (semantic) + official AP2 SDK (deterministic).
4. **Counterfactual receipts** — every block states what it would have cost, computed by arithmetic not by the model.
5. **Prompt-injection posture** — free text never authorizes; six adversarial scenarios, all caught.
6. **A measured product, not a demo** — repeatable eval (26 travel + 12 software scenarios), stability across repeats, cost and latency reported.
7. **Pitch line:** *"AP2 proves who authorized a payment. Anvil proves it's still what they meant."*

## Proof points (all measured live, 2026-10-18)
- Travel: 26 scenarios × 3 repeats — **19/19 violations caught vs 10/19**, **0 false blocks**, 26/26 stable.
- Second domain (software): 12 scenarios — **8/8 vs 6/8**, 0 false blocks, 12/12 stable.
- Cost / speed: ~**$0.002 per audit** (estimated from list prices), **~3.6 s median** decision.
- Load: 8 concurrent runs in ~34 s with an intact audit chain.
- Interop: Google's official A2A client calls our supplier agents (3/3); mandate chains verified with Google's official AP2 SDK.
- *Caveat to state:* scenarios were written and labelled by the team; this is strong evidence, not an independent benchmark.

## Stack (all Google where it counts)
Gemini 2.5 Flash on **Vertex AI** · **A2A** (official client) · **AP2** (official SDK) · **Cloud Run** · **Firestore** · **Firebase Hosting** · **Secret Manager**.

## Honest limits
- The executor is **simulated**; supplier inventories are fixed lists. The subject is the governance layer.
- The in-app sign-in and roles are a **demo** (UI-only); server endpoints are public for judging.
- The mandate schema is travel-specific in the live app; software is **evaluated**, not productized.
- Audit trail is **tamper-evident, not tamper-proof**; one global chain.
- AP2 payment-instrument/payee values are demo data; no bank/PISP role. Say "interoperates with the official A2A client; verified with the official AP2 SDK" — **never** "fully compliant".
- HMAC mandate signing still uses the dev default key (setting a real one needs a re-seed).

## Where it goes next
Per-tenant chains and mandates behind real authentication · `POST /v1/authorize` as an SDK/MCP tool for any agent framework (ADK, LangChain) · asynchronous approvals via chat/webhook · deterministic pre-checks before the model call so clear-cut cases cost no tokens · parallel leg audits · KMS-backed signing and signed log entries · procurement and cloud-spend mandates · policy what-if (replay history under a changed rule) and mandate linting before signing.

## Taglines (pick one)
- "Agents can spend. Anvil makes sure they spend what you meant."
- "The control layer between autonomous agents and the company card."
- "Intent, enforced."
