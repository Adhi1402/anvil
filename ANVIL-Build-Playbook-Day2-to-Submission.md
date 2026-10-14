# Anvil — Build Playbook (Day 2 → Submission)

**Project:** Anvil — the governance layer for autonomous spending agents (Travel & Expense)
**Goal of this doc:** take the Day-1 walking skeleton and turn it into a **winning** submission — professional UI, a measured result, a flawless 3-minute demo.
**Read this with:** the project brief (the "why / what / pitch") and `ANVIL-Day1-Kickoff.md` (how we got here).

---

## How to use this document
- Each **PART = one day**. Inside each part are numbered **STEPS**, each tagged with an **owner** and a **✅ Definition of done**.
- At the end of every day there's a **"Demo-ready checkpoint"** — if that story plays on screen, the day succeeded.
- **Never break the deploy.** Every day ends with a working, deployed system. A feature that isn't deployed by end of day doesn't exist yet.
- **Owners** (from Day 1): **A** = Agents & A2A · **B** = Anvil auditor / drift / self-correct · **C** = Data, mandates & provenance · **D** = UI, deploy & demo.

---

## Where we are now (end of Day 1) — the real code
You already have, and deployed:

| File | What it does |
|---|---|
| `anvil/audit.py` | Vertex **Gemini** auditor → `MATCH / REVIEW / DRIFT` with structured JSON schema, temp 0. Plus `rules_baseline()` (the dumb control). |
| `agents/run.py` | `travel_agent` ↔ `supplier_agent` exchange one A2A-style message, pick a flight → a proposed action. |
| `data/store.py` | `DEMO_MANDATE`, `get_mandate`, append-only `log_provenance`, `list_provenance` (Firestore). |
| `main.py` | `/run` orchestrates mandate → agent → audit → log; `/` renders the log; `/api/provenance` JSON. |
| `dashboard/public/index.html` | Live Firestore `onSnapshot` dashboard + "Run agent" button. |
| Cloud Run + Firebase Hosting | Backend live at the `anvil-…run.app` URL; dashboard on Firebase. |

**What's missing to win** (and this is exactly what Days 2–5 build):
1. The mandate isn't **signed/verified** yet, and provenance isn't **tamper-evident** (hash-chained).
2. There's no **self-correction** loop — the strongest demo beat.
3. There are no **scripted drift scenarios** and no **eval scoreboard** vs the baseline — your strongest Technical-Merit evidence.
4. One agent only — no **multi-agent trip** or **delegation chain**.
5. The UI is functional, not **professional** — it won't win UX as-is.

---

## The finish line — what "done" looks like
Lock these now so every decision serves them.

**The winning demo (3 minutes), in one breath:**
> Manager signs a mandate → agents plan a full trip over A2A → Anvil passes the clean ones, **escalates** a borderline one (REVIEW), and **blocks** a drifting one with a plain-language reason → the agent **self-corrects** and books in policy → the **scoreboard** shows Anvil caught what a rules-only system missed, with zero false blocks → the **provenance trail** replays every agent and approval, tamper-evident → one line: "same engine governs cloud, SaaS, procurement."

**Submission checklist (confirm the exact rules on aibuildercup.com — don't trust memory):**
- [ ] **3-min demo video** (public link, e.g. YouTube unlisted) — the single most-watched artifact. Make it perfect.
- [ ] **Deployed, reachable URL** (Cloud Run + Firebase) that stays up through judging.
- [ ] **Public code repo** (GitHub) with a clean README (what it is, stack, how to run, architecture diagram).
- [ ] **Pitch deck / PDF** (≤ ~10 slides) with the platform-vision slide.
- [ ] **Google-stack story** explicit: Gemini, A2A, AP2, Cloud Run, Firebase, (Vertex AI).
- [ ] Anything else the rules require (team info, theme tag = Future of Work).

**North-star principles**
- **One flawless flow beats broad coverage.** One trip, a few scripted cases, hardened end-to-end.
- **Measured, not asserted.** The baseline scoreboard is the proof judges can't argue with.
- **Lead with the scenario, not the standards.** AP2/A2A are how, not the pitch.

---
---

# PART A — DAY 2 · Harden the spine, sign the mandate, build the eval harness

**Day 2 theme:** make the skeleton *trustworthy and measurable*. By tonight the mandate is cryptographically signed, provenance is tamper-evident, and you can run a set of scenarios through Anvil **and** the baseline and see a scoreboard.

### Step A1 — Sign & verify the mandate (AP2-style) · Owner C
A signed mandate is the whole premise ("prove a human authorized this"). Keep it simple and real: HMAC-sign the canonical mandate JSON.

Add to `data/store.py`:
```python
import os, json, hmac, hashlib

SIGNING_KEY = os.environ.get("ANVIL_SIGNING_KEY", "dev-only-key").encode()

def _canonical(d):
    body = {k: v for k, v in d.items() if k != "signature"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))

def sign_mandate(m):
    m["signature"] = hmac.new(SIGNING_KEY, _canonical(m).encode(), hashlib.sha256).hexdigest()
    return m

def verify_mandate(m):
    expected = hmac.new(SIGNING_KEY, _canonical(m).encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(m.get("signature", ""), expected)
```
Sign `DEMO_MANDATE` when you seed it (`seed_mandate` → `sign_mandate(mandate)`), and have `/run` **refuse to proceed if `verify_mandate` fails** (that refusal is itself a great thing to show).

**✅ Done:** `get_mandate()` returns a mandate with a `signature`; tampering with any field makes `verify_mandate` return `False`.

### Step A2 — Make provenance tamper-evident (hash chain) · Owner C
"Append-only signed log" = each entry carries the hash of the previous one. Break any entry and the chain visibly breaks.

Update `log_provenance` in `data/store.py`:
```python
def _latest_hash():
    q = db().collection("provenance").order_by("ts", direction=firestore.Query.DESCENDING).limit(1)
    docs = list(q.stream())
    return docs[0].to_dict().get("hash", "") if docs else "GENESIS"

def log_provenance(mandate_id, action, audit, delegation=None):
    prev = _latest_hash()
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "mandate_id": mandate_id,
        "action": action,
        "verdict": audit["verdict"], "severity": audit["severity"],
        "violations": audit["violations"], "explanation": audit["explanation"],
        "delegation": delegation or [],
        "prev_hash": prev,
    }
    entry["hash"] = hashlib.sha256((prev + _canonical(entry)).encode()).hexdigest()
    _, ref = db().collection("provenance").add(entry)
    return ref.id
```

**✅ Done:** every new provenance entry has `prev_hash` + `hash`; the chain links head-to-tail. Add a tiny `verify_chain()` helper that walks the log and returns `True/where-it-breaks` — you'll surface this in the UI.

### Step A3 — Script the drift scenarios · Owner B
Create `data/scenarios.py` — the exact cases you'll demo and evaluate. Each is an action proposed against `DEMO_MANDATE`.
```python
SCENARIOS = [
  {"name": "Clean economy booking", "expect": "MATCH",
   "action": {"type": "book_flight", "supplier": "supplier-agent-1", "vendor": "Air India",
              "destination": "Mumbai", "price": 480, "class": "economy", "refundable": True}},

  {"name": "Over-cap fare (borderline)", "expect": "REVIEW",
   "action": {"type": "book_flight", "supplier": "supplier-agent-1", "vendor": "Air India",
              "destination": "Mumbai", "price": 660, "class": "economy", "refundable": True}},

  {"name": "Non-refundable when refundable required", "expect": "REVIEW",
   "action": {"type": "book_flight", "supplier": "supplier-agent-1", "vendor": "IndiGo",
              "destination": "Mumbai", "price": 430, "class": "economy", "refundable": False}},

  {"name": "Business-class upgrade on non-preferred carrier", "expect": "DRIFT",
   "action": {"type": "book_flight", "supplier": "supplier-agent-1", "vendor": "Emirates",
              "destination": "Mumbai", "price": 590, "class": "business", "refundable": True}},

  {"name": "Fare split to dodge the approval cap", "expect": "DRIFT",
   "action": {"type": "book_flight", "supplier": "supplier-agent-1", "vendor": "Air India",
              "destination": "Mumbai", "price": 590, "class": "economy", "refundable": True,
              "charges": [300, 290], "note": "single booking split into two charges"}},
]
```
> Tune the `expect` values to match your auditor's actual output once you run them (A4). The prompt in `audit.py` already defines MATCH/REVIEW/DRIFT — align the scenarios to it, or tighten the prompt. Keep it stable (temp 0 already helps).

**✅ Done:** `python -c "from data.scenarios import SCENARIOS; print(len(SCENARIOS))"` prints 5.

### Step A4 — Build the eval harness + scoreboard · Owner B
This is your **Technical-Merit centerpiece**: same actions, two systems, a measured table.

Create `anvil/eval.py`:
```python
import json
from anvil.audit import audit, rules_baseline
from data.store import DEMO_MANDATE
from data.scenarios import SCENARIOS

def run_eval(mandate=DEMO_MANDATE):
    rows = []
    for s in SCENARIOS:
        a = s["action"]
        verdict = audit(mandate, a)                 # MATCH / REVIEW / DRIFT
        base_pass = rules_baseline(mandate, a)      # True = baseline thinks it's fine
        # "caught" = system did NOT wave a non-MATCH action straight through
        anvil_caught = verdict["verdict"] != "MATCH"
        base_caught = not base_pass
        rows.append({
            "name": s["name"], "expect": s["expect"],
            "anvil_verdict": verdict["verdict"], "anvil_caught": anvil_caught,
            "baseline_caught": base_caught,
            "explanation": verdict["explanation"],
        })
    # headline metrics
    violations = [r for r in rows if r["expect"] != "MATCH"]
    legit = [r for r in rows if r["expect"] == "MATCH"]
    summary = {
        "anvil_catch_rate": sum(r["anvil_caught"] for r in violations),
        "baseline_catch_rate": sum(r["baseline_caught"] for r in violations),
        "violations_total": len(violations),
        "anvil_false_blocks": sum(r["anvil_caught"] for r in legit),  # should be 0
    }
    return {"rows": rows, "summary": summary}

if __name__ == "__main__":
    print(json.dumps(run_eval(), indent=2))
```
Add an endpoint in `main.py` so the UI can read it:
```python
@app.route("/api/eval")
def api_eval():
    from anvil.eval import run_eval
    return jsonify(run_eval())
```

**✅ Done:** hitting `/api/eval` (or running `python -m anvil.eval`) returns a table where Anvil catches the refundability swap, the class upgrade and the split that the baseline misses — and `anvil_false_blocks == 0`.

### Step A5 — Keep it deployed · Owner D
Redeploy after A1–A4 and confirm `/api/eval` works on the live URL (not just locally). Commit everything.
```
gcloud run deploy anvil --source . --region us-central1 --allow-unauthenticated
git add -A && git commit -m "Day 2: signed mandate, hash-chained provenance, eval harness"
git push
```

**✅ Done:** live `/api/eval` returns the scoreboard JSON.

### 🎬 Day 2 demo-ready checkpoint
> "This mandate is signed — watch it reject a tampered copy. Every log entry is hash-chained. And here's the proof the whole thing works: five actions, a rules-only baseline vs Anvil — the baseline missed three, Anvil caught all of them, zero false blocks."

---
---

# PART B — DAY 3 · The twist: intent-drift live + self-correction + REVIEW

**Day 3 theme:** the moat. The agent proposes a drifting action, Anvil blocks it with a reason, and the agent **re-plans within policy and succeeds**. Protect this day — it's the win.

### Step B1 — A deterministic, policy-honoring re-plan · Owner A
Add a "strict" planner that always honors every mandate constraint, so self-correction is reliable on stage.

Add to `agents/run.py`:
```python
def replan(mandate, reason=""):
    """Strict planner: honor class, preferred airlines, refundability, cap. Used after a block."""
    query = message("travel-agent", SUPPLIER_ID, "flight_query",
                    {"destination": mandate["destination"], "max_price": mandate["max_flight_price_usd"]})
    offers = supplier_agent(query)["body"]["offers"]
    compliant = [o for o in offers
                 if o["class"] == mandate["flight_class"]
                 and o["vendor"] in mandate["preferred_airlines"]
                 and (not mandate.get("refundable_required") or o["refundable"])
                 and o["price"] <= mandate["max_flight_price_usd"]]
    if not compliant:
        return None
    best = sorted(compliant, key=lambda o: o["price"])[0]
    return {"type": "book_flight", "supplier": SUPPLIER_ID, "replan_reason": reason, **best}
```
> Add one compliant option to `INVENTORY` so `replan` always has something to land on (e.g. refundable Air India economy under cap). Optional "wow": let a **Gemini** planner propose the re-plan and keep `replan` as the deterministic fallback.

**✅ Done:** `replan(DEMO_MANDATE)` returns an economy, preferred-airline, refundable, under-cap action.

### Step B2 — The guard + self-correction loop · Owner B
Wire propose → audit → (if DRIFT) feed the reason back → re-plan → audit again. Return the whole sequence so the UI can show both beats.

Add to `main.py` (or a small `anvil/guard.py`):
```python
def book_with_guard(mandate, action):
    steps = []
    result = audit(mandate, action)
    steps.append({"action": action, "audit": result})
    if result["verdict"] == "DRIFT":
        reason = "; ".join(result["violations"]) or result["explanation"]
        fixed = replan(mandate, reason=reason)          # agent corrects itself
        result2 = audit(mandate, fixed)
        steps.append({"action": fixed, "audit": result2})
    return steps
```
Log **every** step to provenance (both the blocked and the corrected one — the block belongs in the audit trail).

**✅ Done:** running the guard on the business-class scenario logs two entries: `DRIFT` (blocked, with reason) then `MATCH` (the self-corrected booking).

### Step B3 — The REVIEW escalation path · Owner B + D
`REVIEW` must not look like a block. On REVIEW, surface a **"needs manager approval"** state with a one-tap **Approve / Reject** (approving writes a new provenance entry: "human re-consented"). Keep it a quick beat, not a second feature.

**✅ Done:** the over-cap scenario produces a REVIEW card with a working Approve button that appends a provenance entry.

### Step B4 — A "scenario runner" endpoint for the demo · Owner A + D
So the demo isn't fragile, add a way to fire a named scenario on demand:
```python
@app.route("/run/<scenario>", methods=["GET", "POST"])
def run_scenario(scenario):
    from data.scenarios import SCENARIOS
    mandate = get_mandate()
    s = next((x for x in SCENARIOS if x["name"].lower().startswith(scenario.lower())), None)
    action = s["action"] if s else travel_agent(mandate)
    steps = book_with_guard(mandate, action)
    for st in steps:
        log_provenance(mandate["id"], st["action"], st["audit"])
    return jsonify(steps)
```

**✅ Done:** `/run/business` reliably produces the block-then-self-correct sequence every time.

### Step B5 — Deploy + reliability pass · Owner B + D
Re-run the eval after prompt tweaks. Confirm temp 0 gives **stable** verdicts across 5+ runs (run the eval a few times). Redeploy, commit, push.

**✅ Done:** verdicts are identical across repeated runs; live URL shows the self-correction.

### 🎬 Day 3 demo-ready checkpoint
> "The agent, rushing to hit the deadline, books business class on a non-preferred airline. Anvil blocks it — 'intent drift: cabin class + non-preferred vendor' — hands the reason back, and the agent **re-plans by itself**: economy, preferred carrier, refundable, booked. It didn't just say no; it kept the trip moving."

---
---

# PART C — DAY 4 · Multi-agent trip, delegation provenance, and the professional UI

**Day 4 theme:** depth + polish. One signed mandate drives **three** agents; the provenance records the **delegation chain**; and the dashboard becomes something a judge calls "professional."

### Step C1 — Hotel + transport agents (one mandate, many agents) · Owner A
Mirror the flight pattern with two more supplier exchanges.

Add to `agents/run.py`:
```python
HOTEL_INVENTORY = [
    {"vendor": "Taj", "price": 280, "refundable": True, "destination": "Mumbai"},
    {"vendor": "OYO", "price": 180, "refundable": False, "destination": "Mumbai"},
]
TRANSPORT_INVENTORY = [{"vendor": "Uber", "price": 40, "destination": "Mumbai"}]

def hotel_agent(mandate):
    cap = mandate["max_hotel_per_night_usd"]
    opts = [h for h in HOTEL_INVENTORY if h["destination"] == mandate["destination"]
            and h["price"] <= cap and (not mandate.get("refundable_required") or h["refundable"])]
    if not opts: return None
    best = sorted(opts, key=lambda h: h["price"])[0]
    return {"type": "book_hotel", "supplier": "hotel-supplier-1", **best}

def transport_agent(mandate):
    o = TRANSPORT_INVENTORY[0]
    return {"type": "book_transport", "supplier": "transport-supplier-1", **o}

def plan_trip(mandate):
    """One mandate dispatches three sub-agents (A2A)."""
    return [a for a in (travel_agent(mandate), hotel_agent(mandate), transport_agent(mandate)) if a]
```

**✅ Done:** `plan_trip(DEMO_MANDATE)` returns flight + hotel + transport actions; each goes through `audit` + `book_with_guard`.

### Step C2 — Record the delegation chain · Owner C
Every sub-agent acts **under the one signed mandate**. Record who delegated to whom so every booking traces back to the single human approval.
```python
def delegation_for(action):
    return [
        {"from": "manager@example.com", "to": "trip-orchestrator", "mandate": "mandate-001"},
        {"from": "trip-orchestrator", "to": action["type"].replace("book_", "") + "-agent", "mandate": "mandate-001"},
        {"from": action["type"].replace("book_", "") + "-agent", "to": action["supplier"], "mandate": "mandate-001"},
    ]
```
Pass it into `log_provenance(..., delegation=delegation_for(action))` (the field is already in the A2 schema).

**✅ Done:** each provenance entry carries a 3-hop delegation chain tied to `mandate-001`.

### Step C3 — The professional dashboard (the thing judges see) · Owner D
This is the **UX 10%** and the whole feel of the product. Rebuild `dashboard/public/index.html` to this spec. Keep the live Firestore `onSnapshot` you already have — just make it look like a product.

**Design tokens (match the brief):**
- Palette: cobalt `#2E57D6` (primary), gold `#B06A08` (review/accent), green `#1C7A4D` (match), red `#B23A3A` (drift); neutrals for surfaces/lines.
- **Light + dark** via `@media (prefers-color-scheme)`, colors as CSS variables on `:root`.
- **System font stack** only (no webfont CDN): `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- Generous spacing, one max-width column (~960px), rounded cards, subtle borders — no heavy shadows.
- Fully responsive at phone width (single column, 16px gutters).

**Layout, top to bottom:**
1. **Header** — wordmark **ANVIL**, one-line tagline ("Governance for autonomous spending agents"), and a small live status dot ("connected · N entries").
2. **The mandate card** — render the signed mandate as a human-readable "authorization": traveler, destination, class, caps, preferred airlines, "book by". A green **✓ Signature verified** badge (calls an endpoint that runs `verify_mandate`). This frames everything.
3. **Trip board** — three columns or rows (Flight / Hotel / Transport), each showing the proposed action and a colored verdict chip (MATCH green / REVIEW gold / DRIFT red). The REVIEW card has **Approve / Reject** buttons.
4. **The drift → self-correction strip** — when a DRIFT happens, show the blocked action (red) with the plain-language reason, an arrow, then the corrected action (green). This is the hero moment; make it visually unmissable.
5. **Scoreboard** — read `/api/eval` and render the **Anvil vs rules-only baseline** table with ✓/✗ and the headline "caught 3/3 the baseline missed · 0 false blocks."
6. **Provenance trail** — the append-only list (newest first) with verdict color, timestamp, delegation chain (manager → orchestrator → agent → supplier), and a small **🔗 chain-verified** indicator (green if `verify_chain()` passes). A **Replay** button that steps through entries.
7. **Footer** — the Google stack line: "Gemini · A2A · AP2 · Cloud Run · Firebase."

**Control bar** — buttons to fire the demo scenarios deterministically: *Clean trip*, *Borderline (REVIEW)*, *Drift → self-correct*. These call the `/run/<scenario>` endpoint from B4. **Rehearse against these buttons, not live typing.**

> I can generate this full polished `index.html` for you as the next step — a drop-in replacement that keeps your Firestore config and endpoints. Just say the word.

**✅ Done:** the dashboard looks like a product in both light and dark mode, shows the mandate, the trip board, the drift/self-correct strip, the scoreboard, and the provenance trail — live, deployed, responsive on a phone.

### Step C4 — README + architecture diagram · Owner C + D
Judges open the repo. Make `README.md`: one-paragraph pitch, the architecture diagram (mandate → agents/A2A → Anvil/Gemini → decision+self-correct → signed Firestore log → dashboard), the Google stack, and `how to run`. A simple boxes-and-arrows diagram (even hand-drawn, cleanly) is fine.

**✅ Done:** a stranger can understand Anvil in 60 seconds from the README.

### 🎬 Day 4 demo-ready checkpoint
> The full trip plays on a professional dashboard: signed mandate up top, three agents booking, one blocked-and-corrected, the scoreboard proving it beats the baseline, and a replayable, chain-verified trail — all live on the deployed URL, beautiful in dark mode.

---
---

# PART D — DAY 5 · Package to win: video, deck, rehearse, buffer

**Day 5 theme:** no new features. Turn a working system into a submission that *wins*. **Freeze the code by midday.**

### Step D1 — Freeze & stabilize · Everyone (lead: D)
- Code freeze at noon. Only bug-fixes after.
- Do a clean deploy from `main`. Click through every demo button 5× — it must be boring and reliable.
- Pre-seed Firestore so the dashboard never opens empty.

**✅ Done:** a from-scratch load of the live URL shows a populated, working dashboard every time.

### Step D2 — The 3-minute video (your most important artifact) · Owner D + B
Record screen with clear narration. **Beat sheet (hit these exact times):**
1. **0:00–0:20 — The problem.** "AI agents already book travel and spend money. Nothing checks they stayed inside what a human approved." One sentence, one striking stat from the brief.
2. **0:20–0:45 — The signed mandate.** Show it, show "✓ signature verified," reject a tampered copy.
3. **0:45–1:15 — Happy path.** One mandate → three agents book over A2A → all MATCH → provenance appears live, tied to one approval.
4. **1:15–2:05 — The hero beat.** Drift: business-class on a non-preferred carrier, split charge. Anvil blocks with the reason → **agent self-corrects** → books in policy. Slow down here.
5. **2:05–2:35 — The proof.** The scoreboard: Anvil vs baseline, 3 caught that rules missed, 0 false blocks.
6. **2:35–3:00 — The vision.** Replay the chain-verified trail; "same engine governs cloud, SaaS, procurement — the control plane for agent spending." End on the wordmark.

Record each beat separately and stitch — cleaner than one nervous take. Captions help.

**✅ Done:** a polished ≤3-min video on a public unlisted link, no dead air, hero beat crystal clear.

### Step D3 — The pitch deck (≤10 slides) · Owner A + C
1. Title + one-line. 2. The problem (agents live now, no rail). 3. What Anvil is (the diagram). 4. The twist: intent-drift + self-correction. 5. Live-demo screenshot(s). 6. **The scoreboard** (vs baseline). 7. Google stack (Gemini/A2A/AP2/Cloud Run/Firebase). 8. How it broadens (beachhead → control plane). 9. Why now / impact (brief's sourced numbers). 10. Team + ask. Keep the standards boilerplate off the lead slides.

**✅ Done:** a clean PDF deck that tells the story without you narrating.

### Step D4 — Rubric self-check + submit · Everyone
Walk the rubric and the submission checklist (top of this doc) line by line. Submit with **buffer before the deadline** — uploads and links fail at the last minute.
- Technical & Gen AI (40%): intent-drift reasoning + multi-agent A2A + the measured scoreboard. ✓
- Impact (25%): agents are live today (Navan/Visa); real T&E leakage. ✓
- Innovation (25%): the guard + self-correction angle. ✓
- UX (10%): the professional dashboard + the replayable trail. ✓

**✅ Done:** submitted, every link opens in an incognito window, video plays, repo is public, URL is up.

---
---

# PART E — Judgment day & live Q&A
- Have the **live URL open and pre-warmed** (Cloud Run cold starts — hit it once right before).
- Keep a **local fallback** running in case Wi-Fi dies; and the video as the ultimate fallback.
- Expect the killer question: *"How do you know the AI doesn't over-block?"* → answer with the scoreboard: **0 false blocks** on legit actions, measured.
- Second question: *"Isn't this just a rules engine?"* → "Rules caught 1 of 4; Anvil caught 4 of 4 — because it reasons about intent, not just numbers. Here's the refundability swap a rule can't express."
- Keep answers to the **scenario**, not the protocol acronyms.

---

## Risk & fallback (decide these now, not at 2am)
| Risk | Fallback |
|---|---|
| Gemini flaky / rate-limited on stage | Cache the last good verdicts per scenario; serve cached on error (temp 0 means they're stable anyway). |
| Cloud Run cold start / down | Local `flask run` mirror + the recorded video. |
| Multi-agent too shaky | Demo flight-only self-correction — it's the hero beat; hotel/transport are bonus. |
| Self-correction unreliable | Keep the **deterministic** `replan` (B1), not a Gemini planner, for the live demo. |
| Firestore empty on load | Pre-seed entries in D1. |
| Running out of time | Priority order: self-correction (B) > scoreboard (A4) > professional UI (C3) > multi-agent (C1). Ship in that order. |

## Daily end-of-day ritual (every day)
1. Deploy to the live URL. 2. Click the demo path end-to-end. 3. `git commit && git push`. 4. One-line standup in the group chat: what's demo-ready now.

---

**The one thing that wins this:** on screen, an agent tries a plausible but unauthorized action, Anvil stops it, explains why, the agent fixes itself — and a scoreboard proves it beats the obvious alternative, with zero false alarms. Everything in this doc serves that 50 seconds. Build toward it.
