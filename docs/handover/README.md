# Anvil — handover index

**Start here.** This folder is the handover pack for the `main` branch (repo `github.com/Adhi1402/anvil`, local `/home/swathy-s/Documents/anvil/anvil`). State as of **2026-10-18**; all numbers below were measured live that day.

## 1. The four handover documents (read in this order)
| # | File | What it gives you |
|---|---|---|
| 1 | [`01-UI-FLOW-AND-DEMO-PITCH.md`](01-UI-FLOW-AND-DEMO-PITCH.md) | UI flow end to end, every scenario covered, the strengths to highlight, the **3-minute demo flow** and the **voice-over script** |
| 2 | [`02-CODE-CHANGES-HIGH-LEVEL.md`](02-CODE-CHANGES-HIGH-LEVEL.md) | What changed and where (by phase, module, tests, infra), env vars, known limits |
| 3 | [`03-ARCHITECTURE-AND-DESIGN-FLOW.md`](03-ARCHITECTURE-AND-DESIGN-FLOW.md) | Architecture and sequence diagrams, decision gate, data model, trust boundaries, scaling/failure modes, API, deploy commands |
| 4 | [`04-WHY-ANVIL-PRODUCT.md`](04-WHY-ANVIL-PRODUCT.md) | Product description, why it is useful, who it is for, uniqueness (honestly framed), proof points, limits, roadmap |

## 2. Other markdown files — which to share
Paths are relative to the repo root (`/home/swathy-s/Documents/anvil/anvil`).

**Share with judges / reviewers / the wider team**
| Path | Why |
|---|---|
| `README.md` | Public face of the repo: results, requirements mapping, architecture, how to run, honest claims |
| `docs/SUBMISSION-CHECKLIST.md` | Rubric self-check, what is done, what only a person can do, safe claims |
| `docs/Anvil-Pitch-Deck.pdf` (source `docs/deck/deck.html`) | The deck — **slides 2, 9, 10 still have `[ADD: …]` placeholders** |
| `docs/DEMO-VIDEO-SCRIPT.md` | One-page cheat sheet of the 3-minute demo (full version is `01-…`) |
| Interactive guide: https://claude.ai/artifact/HA5UwwjRKbo4tDxFSrmAsz | Screen map, every button, scenario lab, demo scripts, Q&A, troubleshooting (shared as "anyone with the link") |

**Share with whoever continues the engineering**
| Path | Why |
|---|---|
| `docs/AP2-A2A-TRACKER.md` | Decisions, verified facts, rollout and **rollback** commands, key custody, what is left — written so work can resume without the chat history |
| `START-HERE-TEAMMATE.md` | Laptop setup steps (setup still valid; its numbers/screens are superseded, see its status note) |

**Historical — keep, but do not send as current**
| Path | Note |
|---|---|
| `ANVIL-Day1-Kickoff.md`, `ANVIL-Build-Playbook-Day2-to-Submission.md` | Original build plans (Oct 14–17) |
| `ANVIL-Next-Level-Ideas.md` | Planning idea log; most items are now built (see its status note) |
| `ap2/NOTICE-VENDORED.md`, `ap2/sdk/README.md` | Third-party (Google AP2 SDK) docs, vendored unmodified — not Anvil documentation |

## 3. Live links
| What | URL |
|---|---|
| Dashboard | https://dazzling-lodge-511607-m0.web.app |
| API | https://anvil-733520529727.us-central1.run.app (e.g. `/api/verify`, `/api/ap2`, `/api/a2a`) |
| Supplier agents (A2A) | https://anvil-suppliers-733520529727.us-central1.run.app |
| Interactive guide | https://claude.ai/artifact/HA5UwwjRKbo4tDxFSrmAsz |

Demo accounts (password `demo`; UI-only, not real auth): **Rahul** (employee) · **Adhish Sekar** (finance manager) · **Swathy S** (platform operator) · or the *guest judge* link.

## 4. Where things are (repo map)
```
main.py                     HTTP API, streaming, controls, metrics, authorize, simulation
anvil/                      audit (Gemini), gemini (client+telemetry), guard, ap2_layer, impact, metrics, eval
agents/                     planner (Gemini agent), run (corrector), a2a (official A2A client + fallback)
suppliers/                  A2A supplier server (separate Cloud Run service)
data/                       store (Firestore, chain), scenarios, domains, ap2_open_mandates.json
ap2/                        vendored official AP2 SDK (Apache-2.0)
dashboard/public/           index.html (the whole UI) and recordings/
tests/, scripts/            local tests (two modes), live smoke test, interop proofs, recorder
docs/                       handover/, deck, checklist, tracker, demo script
```

## 5. Status and what is still open
- **Done and verified:** everything in documents 01–04; live smoke suite passes; browser tests pass on the deployed site; eval travel 19/19 vs 10/19 (26 scenarios), software 8/8 vs 6/8 (12 scenarios), 0 false blocks.
- **Needs a person:**
  1. **Push** the local commits to GitHub (this machine has no GitHub credentials).
  2. Fill deck placeholders (slides 2, 9, 10): **a sourced statistic, team, the ask** — do not invent numbers.
  3. Record the **3-minute video** (script and voice-over in `01-…`).
  4. Make the repo **public**; confirm no secrets in history.
  5. Check the live competition rules/form on aibuildercup.com.
  6. After judging: set Cloud Run **min-instances to 0** on both services; consider a billing budget alert.
- **Known gaps (say them before someone finds them):** HMAC mandate signing still uses the dev default key; demo endpoints and sign-in are open/UI-only; one global chain; simulated executor; AP2 payment data are demo values; never claim "fully A2A/AP2 compliant".
- **Before the demo:** open the dashboard 2 minutes earlier, sign in, Governance → *New session*, confirm no agent is paused. Fallbacks: Replay → recorded runs; the video.
