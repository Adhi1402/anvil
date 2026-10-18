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

## Voice-over with your own cloned voice (MiniMax): exact steps
Everything is cut to the second. The script is `submission/voiceover/NARRATION-SCRIPT.md`, and each of the 21 clips is also a separate text file in `submission/voiceover/clips/` (`01.txt` ... `21.txt`). Each clip starts at a measured moment of `demo_recording_v2/anvil-demo.mp4` and fits its window at a calm pace.

1. **Clone your voice** on minimax.io with a clean sample of your own voice (quiet room, one speaker, no music; follow MiniMax's sample instructions on the site). Only clone your own voice.
2. **Generate the 21 clips.** For each clip, paste the text of `NN.txt` into MiniMax text-to-speech with your cloned voice, language English, speed 1.0, neutral emotion, then download as MP3. Name the files exactly `01.mp3`, `02.mp3` ... `21.mp3` and put them in one folder, for example `C:oice`.
   - Keep the spelling as written ("A to A", "A P 2"): it makes the voice say the acronyms correctly.
   - Generate each clip separately. Do not merge them: the timing depends on each clip starting at its own second.
3. **Put the voice on the video** (one command, no editing skills needed):
   `python scripts/assemble_voiceover.py C:oice`
   It places every clip at its exact time, writes `submission/voiceover/anvil-demo-with-voice.mp4`, and prints a table: if a clip is longer than its window it is sped up slightly (never more than 1.2x) and marked "tight"; if it cannot fit it says PROBLEM and which clip to shorten or regenerate a little faster.
4. **Watch it once.** If a line sounds rushed, regenerate that clip (speed 0.95) or edit its text file to be a few words shorter, then run step 3 again. Final length is about 3:36 (the last line is allowed to run a few seconds past the last frame, which is held).
5. Upload to YouTube as **Unlisted** (below). Title: `Anvil: the policy-enforcement engine for AI agents that spend money (AI Builder Cup)`.

`submission/voiceover/PREVIEW-robot-voice-timing-check.mp4` is the same video with a plain computer voice, only to show the timing; do not submit it.

If you re-record the screen video, run `python scripts/align_timeline.py <folder>` and `python scripts/build_narration.py <folder>` again: the script is re-cut to the new timing automatically (and it refuses to build if a line no longer fits).

## Upload and get the link
1. YouTube > **Create** > **Upload video**.
2. Visibility **Unlisted** (anyone with the link can watch). Not Private: the judges could not open it.
3. Paste the link on **slide 13** of the deck (red text) and into the submission form. Open it in a private window to check it plays.

## Before you submit
- [ ] Repository is **public** (GitHub > Settings > Danger zone > Change visibility) and up to date.
- [ ] Video is **3 to 4 minutes**, Unlisted, and plays in a private window.
- [ ] Deck is `submission/Anvil - AI Builder Cup Submission v2.pptx` with the video link pasted on slide 13; team name and leader on slide 1 are correct.
- [ ] Open https://dazzling-lodge-511607-m0.web.app in a private window and click **Continue as a guest judge**; the first request after a quiet period can take 10 to 20 seconds.
- [ ] Leave the deployment alone until judging ends (Cloud Run keeps one warm instance); set `min-instances` to 0 afterwards.
