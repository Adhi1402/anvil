# Demo video: a complete guide for a first-timer

**Challenge rule:** a 3 to 4 minute video that clearly shows the working product. Over 4:00 may be penalised. **Do not exceed 4:00.**

## The recordings (all silent: you add the voice)
| Folder | What it is | Length |
|---|---|---|
| `demo_recording_v2/` | **The video to use.** Opens with the problem and the engine, then the full story, including the block in the employee's own flow, the second domain and the tech stack | 3:30 |
| `demo_recording_v1/` | The earlier cut you liked, rebuilt with the original script (the first copy was lost when a re-record command ran before it was stopped) | 3:42 |

In each folder: `anvil-demo.mp4` (the video), `anvil-demo-full.webm` (no time-lapse), `timeline.md` (what is on screen at each second), `screenshots/` (used in the deck). Both were recorded from the live site with real Gemini and AP2. Long Gemini waits are a labelled **time-lapse** so the length never depends on model speed.

Re-record v2 any time: `python scripts/record_demo_v2.py https://dazzling-lodge-511607-m0.web.app/ --out my_new_take` (about 6 minutes). It writes demo entries to the live system and changes the hotel limit to $350 during the policy scene: afterwards put it back to $300 on the Policy page.

## What v2 covers (nothing missing)
| Idea the judges must get | Where |
|---|---|
| The problem (caps and allowlists miss class swaps, split charges, hidden add-ons, fake approvals) | 0:00 |
| **Anvil is a domain-neutral engine** (mandate, intent audit, enforce, prove); travel is the example | 0:11 |
| Enterprise fit: three roles, separation of duties, finance-owned policy | 0:25, 1:30, 1:56 |
| Employee **tempts the agent**; Anvil **blocks**; agent **self-corrects**; the late trip is **escalated** | 0:35 to 1:14 |
| Day-by-day itinerary and what the agent considered | 1:14 to 1:30 |
| Finance approves a whole trip; signed booking refs | 1:30 to 1:56 |
| Editable, signed, versioned policy | 1:56 to 2:12 |
| AI traces: exact Gemini input and output; tamper-evident chain | 2:12 to 2:36 |
| Unprotected vs protected (money leaks vs blocked) | 2:36 to 3:12 |
| **Second domain** on the same engine (software, 8 of 8) | 3:12 |
| **Tech stack** on Google Cloud | 3:20 |

Not shown on screen (covered by the tests; judges can try them live): a finance manager **rejecting** a request, an employee **withdrawing** one, being refused for approving your own request. Say so in the voice-over if you like.

## Step 1: Practise (10 minutes)
Play `demo_recording_v2/anvil-demo.mp4` and read the narration below out loud at each time. Each line is sized to the seconds shown (about 2.3 words per second). Do it twice, slowly.

## Step 2: Record your voice (Windows 11, free)
1. Quiet room; phone or laptop microphone a hand-width from your mouth; close other apps.
2. Open **Clipchamp** (built into Windows 11: Start key, type "Clipchamp").
3. **Create a new video** > **Import media** > choose `anvil-demo.mp4` > drag it to the timeline.
4. **Record & create** > **Audio recording** > choose your microphone. Press record, play the video, read the narration. You may record in pieces and drag each clip under its second. Re-record any piece you dislike.
5. Optional: switch on **Noise suppression** and **Auto-adjust volume**.
6. Check the total is **under 4:00** (it is 3:30). If a line runs long, speak a little faster rather than adding time.
7. **Export** at **1080p** (MP4).

(A computer-generated voice is possible with Google Cloud Text-to-Speech, but your own voice is more convincing, and Google's "use my voice" cloning is a restricted feature that needs Google's approval and a recorded consent, so it is not an option here.)

## Step 3: Upload and get the link
1. YouTube > **Create** > **Upload video**. Title: `Anvil: the policy-enforcement engine for AI agents that spend money (AI Builder Cup)`.
2. Visibility **Unlisted** (anyone with the link can watch). Not Private: the judges could not open it.
3. Paste the link on **slide 13** of the deck (red text) and into the submission form. Open it in a private window to check it plays.

## Narration for demo_recording_v2 (read at the times shown)
| Time | Say |
|---|---|
| 0:00 | "AI agents are starting to spend company money. But nothing proves an agent stayed inside what a person approved. Budget caps only see numbers: they miss a class swap, a split charge, a hidden add-on, or a note that says the CFO pre-approved it." |
| 0:11 | "Anvil is the engine that fixes this. A person signs a mandate. Gemini judges every action against the intent of that mandate. Code enforces the verdict, with Google's AP2 limits as a second gate. And everything is provable. It is domain-neutral: travel is live today, software purchases are proven, and procurement, cloud spend and payments plug into the same engine." |
| 0:25 | "Our enterprise example is business trip booking, with three roles: an employee, a finance manager, and the platform operator who runs the AI agents." |
| 0:35 | "Rahul plans a trip to Goa. Real dates, round trip, purpose, cost centre. He also asks the booking agent for business class on Emirates. And the form already warns him: leaving in three days breaks the seven-day notice rule." |
| 0:45 | "He sends it. Anvil Guard compares every offer from the supplier agents, which the booking agent reaches over the A2A protocol. Gemini picks one per leg, and Anvil audits every booking before any money moves. This takes a while, so it is sped up." |
| 1:07 | "The agent went for business class. Anvil blocked it, told the agent exactly why, and the agent chose a compliant flight. And since the trip is late, everything now waits for finance." |
| 1:14 | "Here is the itinerary, day by day: flights with times, cabs with pickup and where from and to, and the hotel. Nothing is booked until finance approves." |
| 1:19 | "Anvil shows its work: every offer the agent considered, whether the policy allows it, and the agent's own reasoning." |
| 1:30 | "Adhish is the finance manager. One card for the whole trip, with dates, purpose, cost centre, and exactly why it needs him." |
| 1:37 | "One click approves it. He cannot approve his own requests, and the people who run the agents cannot approve at all." |
| 1:48 | "Back with Rahul: approved, with a signed booking reference on every item, and who approved it." |
| 1:56 | "Finance owns the policy: limits, approved cities and trip rules are editable." |
| 2:05 | "He reviews exactly what will change, signs it, and it is live for the next request, with who, when and why on record." |
| 2:12 | "Swathy is the platform operator. Anvil Guard shows every decision checked, the money kept from being spent, and what went to a person." |
| 2:18 | "AI traces: every call to Gemini, with the exact input it was given and the exact output it returned, plus time, tokens and cost." |
| 2:30 | "Every decision is chained to the one before it by a hash. Edit history and the chain breaks, and the break shows." |
| 2:36 | "Why this matters: the same tempted agent, with Anvil switched off." |
| 2:42 | "It books business class with no check, and the money leaks. Now Anvil is on, same request. This part is sped up." |
| 3:04 | "Blocked, with the reason. The agent corrects itself, and the new booking is audited again before it is allowed." |
| 3:12 | "And this is not just travel. The same engine, with a different policy, governs software purchases: eight of eight violations caught." |
| 3:20 | "It runs entirely on Google Cloud: Firebase Hosting, Cloud Run for the API and the supplier agents, Gemini on Vertex AI, Firestore for the tamper-evident log, and the A2A and AP2 SDKs. Anvil: a signed policy, Gemini judging intent, code enforcing it, and proof of every decision." |

## Before you submit
- [ ] Repository is **public** (GitHub > Settings > Danger zone > Change visibility) and up to date.
- [ ] Video is **3 to 4 minutes**, Unlisted, and plays in a private window.
- [ ] Deck is `submission/Anvil - AI Builder Cup Submission v2.pptx` with the video link pasted on slide 13; team name and leader on slide 1 are correct.
- [ ] Open https://dazzling-lodge-511607-m0.web.app in a private window and click **Continue as a guest judge**; the first request after a quiet period can take 10 to 20 seconds.
- [ ] Leave the deployment alone until judging ends (Cloud Run keeps one warm instance); set `min-instances` to 0 afterwards.
