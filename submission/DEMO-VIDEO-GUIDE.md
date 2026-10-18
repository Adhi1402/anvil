# Demo video: a complete guide for a first-timer

**What the challenge requires:** a 3 to 4 minute video that clearly shows the working product. Longer than 4:00 may be penalised. **Do not exceed 4:00.**

## What is already done for you
The screen recording is finished and captured from the real, deployed product (live Gemini, live AP2). It has a visible mouse pointer and short on-screen captions, and it is **3 minutes 33 seconds** long. It has no sound: you add your voice.

| File | What it is |
|---|---|
| `demo_recording/anvil-demo.mp4` | **The video to use** (1366 x 768, H.264, 3:33) |
| `demo_recording/anvil-demo-full.webm` | The same recording at full speed with no time-lapse (backup) |
| `demo_recording/timeline.md` | What is on screen at each second, to time your voice |
| `demo_recording/screenshots/` | The screenshots used in the deck |

If you want to re-record (for example after changing the app): `python scripts/record_demo.py https://dazzling-lodge-511607-m0.web.app/` (about 5 minutes; it writes demo entries to the live system and changes the hotel limit to $350 during the policy scene, so afterwards restore it on the Policy page to $300).

## Step 1: Read the script while watching the video (10 minutes)
Play `anvil-demo.mp4` and read the narration below out loud at each time. Each line is sized to fit the seconds shown (about 2.3 words per second). Do it twice, slowly.

## Step 2: Record your voice (Windows 11, free)
1. Quiet room, phone or laptop microphone about a hand-width from your mouth. Close other apps.
2. Open **Clipchamp** (it is built into Windows 11: press the Start key, type "Clipchamp").
3. **Create a new video** > **Import media** > choose `anvil-demo.mp4` > drag it onto the timeline.
4. **Record & create** > **Audio recording** > choose your microphone. Press record, play the video, and read the narration. You can record in pieces and drag each clip under the matching second. Re-record any piece that does not sound right.
5. Optional: in the audio panel switch on **Noise suppression** and **Auto-adjust volume**.
6. Check that the total is **under 4:00** (it should be 3:33). If your voice runs longer than a scene, speak a little faster rather than adding time.
7. **Export** at **1080p** (an MP4 file).

## Step 3: Upload and get the link
1. YouTube > **Create** > **Upload video**. Title: `Anvil: spend control for AI agents (AI Builder Cup)`.
2. Visibility **Unlisted** (anyone with the link can watch; it is not searchable). Do not choose Private: the judges could not open it.
3. Copy the link. Paste it into slide 13 of the deck where it says PASTE YOUR VIDEO LINK HERE, and into the submission form.
4. Open the link in a private window to confirm it plays.

## Narration (read at the times shown)
| Time | Say |
|---|---|
| 0:01 | "AI agents are starting to spend company money. Anvil is the control layer between those agents and the money: it checks every purchase against what a person actually approved, and proves it." |
| 0:14 | "Rahul is an employee. He plans a trip to Goa: real dates, round trip, a purpose and a cost centre." |
| 0:19 | "The form already warns him: leaving in three days breaks the seven-day notice rule, so finance will need to approve." |
| 0:25 | "He sends it. Anvil Guard compares every offer from the supplier agents. A Gemini booking agent picks one per leg, and then Anvil audits each booking against the signed policy. The agent can propose; Anvil decides. This part takes a while, so it is sped up." |
| 0:55 | "Here is the itinerary, day by day: flight with times and numbers, the cabs with pickup time and where from and to, and the hotel. Nothing is booked until finance approves." |
| 1:06 | "Anvil keeps what the agent considered: every offer, whether the policy allows it, and the agent's own reasoning." |
| 1:19 | "Adhish is the finance manager. One card for the whole trip: dates, purpose, cost centre, and exactly why it needs him." |
| 1:28 | "He approves the whole trip in one click. He cannot approve his own requests, and the people who run the agents cannot approve at all." |
| 1:37 | "Back with Rahul: approved, with a signed booking reference for every item, and who approved it." |
| 1:49 | "Finance owns the policy. Limits, approved cities and trip rules can be edited." |
| 2:00 | "He reviews exactly what will change, signs it, and it is live for the next request, with who, when and why on record." |
| 2:10 | "Swathy runs the AI agents. This is Anvil Guard: every decision checked, money kept from being spent, and what went to a person." |
| 2:18 | "AI traces. Every call to Gemini, with the exact input it was given and the exact output it returned, plus time, tokens and cost." |
| 2:33 | "Every decision is chained to the one before it. Edit history and the chain breaks, and the break shows." |
| 2:43 | "Why this matters. The same agent, tempted by business class, with Anvil switched off." |
| 2:49 | "It books it with no check, and the money leaks. Now we switch Anvil on and run the same request. This part is sped up." |
| 3:18 | "Blocked, with the reason. The agent corrects itself, and the new booking is audited again before it is allowed." |
| 3:26 | "Anvil: a signed policy, Gemini judging intent, code enforcing it, and proof of every decision." |

## What the video shows, and what it does not
- **Shown:** approve (a compliant booking with a signed receipt), escalate to a person (the late trip) and approve it, **block with a reason and self-correction** (the business-class scenario in the Demo studio), the unprotected contrast, policy editing, AI traces, the tamper-evident chain.
- **Not shown on screen (covered by tests and available to try live):** a finance manager **rejecting** a request, an employee **withdrawing** a request, being **refused** for approving their own request, an operator being refused approval, an unapproved city or a past date being refused. Say in your narration that judges can try these on the live site.

## Before you submit: checklist
- [ ] The repository is **public** (GitHub > Settings > Danger zone > Change visibility).
- [ ] The video is **3 to 4 minutes**, Unlisted, and plays in a private window.
- [ ] The deck is `submission/Anvil - AI Builder Cup Submission.pptx` with the video link pasted on slide 13.
- [ ] Open https://dazzling-lodge-511607-m0.web.app in a private window and click **Continue as a guest judge**; the first request after a quiet period can take 10 to 20 seconds.
- [ ] Leave the deployment alone until judging ends: Cloud Run keeps one warm instance (`min-instances 1`); reset it to 0 afterwards to stop the small cost.
