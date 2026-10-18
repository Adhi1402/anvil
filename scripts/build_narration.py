"""Builds the voice-over script from the measured video timeline.
  python scripts/build_narration.py demo_recording_v2
Needs <folder>/timeline.json (python scripts/align_timeline.py <folder>). Writes submission/voiceover/:
  NARRATION-SCRIPT.md   the script with start time, window, word budget
  clips/NN.txt          one text file per clip, ready to paste into a text-to-speech tool
  narration.json        the same data for scripts/assemble_voiceover.py"""
import json
import os
import sys

folder = sys.argv[1] if len(sys.argv) > 1 else "demo_recording_v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tl = json.load(open(os.path.join(folder, "timeline.json"), encoding="utf-8"))
starts = [r["start"] for r in tl["rows"]]
VIDEO_END = tl["duration"]
EXTEND = 6.0                    # the last clip may run past the end of the video: the closing frame is held
WPS = 2.4                       # words per second a calm narrator manages

# (first timeline row of the segment, text exactly as it should be spoken; numbers and acronyms are spelled the way a voice reads them)
SEGMENTS = [
    (0, "AI agents are starting to spend company money, but nothing proves they stayed inside what a person approved. Budget caps only see numbers."),
    (1, "Anvil is the engine that fixes this: a signed mandate, Gemini judging intent, code enforcing it, proof of every decision. Travel is live, software is proven, more plug in."),
    (2, "Our example is enterprise trip booking, with three roles: employee, finance manager, and platform operator."),
    (3, "Rahul plans a Goa trip and asks the agent for business class. The form warns him: three days' notice breaks the seven-day rule."),
    (6, "He sends it. Anvil Guard compares every offer the supplier agents return over the A to A protocol. Gemini picks one per leg, and Anvil audits every booking before any money moves. This takes a while, so it is sped up."),
    (7, "The agent went for business class. Anvil blocked it; the agent corrected itself."),
    (8, "The itinerary. Nothing is booked until finance approves."),
    (9, "Anvil shows its work: every offer the agent considered, whether the policy allows it, and the agent's own reasoning."),
    (10, "Adhish, the finance manager, gets one card for the whole trip."),
    (11, "He sees exactly why it needs him, and approves in one click. He cannot approve his own requests, and operators cannot approve at all."),
    (12, "Back with Rahul: approved, with a signed booking reference on every item, and who approved it."),
    (13, "Finance owns the policy. Limits, approved cities and trip rules are all editable."),
    (14, "He reviews the change, signs it, and it is live, with who and why recorded."),
    (15, "Swathy runs the AI agents. Anvil Guard shows every decision."),
    (16, "AI traces: every call to Gemini, with the exact input it was given and the exact output it returned, plus time, tokens and cost."),
    (17, "Decisions are hash-chained. Edit history, and the break shows."),
    (18, "Why it matters: the same tempted agent, with Anvil switched off."),
    (19, "It books business class with no check, and the money leaks. Now Anvil is on, same request. This part is sped up too. Watch Anvil audit the booking, and send the agent back with the reason."),
    (20, "Blocked, with the reason. The agent corrects itself, and the new booking is audited again."),
    (21, "Not just travel: the same engine governs software. Eight of eight caught."),
    (22, "Built on Google Cloud: Firebase Hosting, Cloud Run, Gemini, Firestore, A to A and A P 2. Anvil: signed policy, intent judged by Gemini, code enforcing it, every decision proven."),
]

segs = []
for i, (row, text) in enumerate(SEGMENTS):
    start = starts[row]
    end = starts[SEGMENTS[i + 1][0]] if i + 1 < len(SEGMENTS) else VIDEO_END + EXTEND
    words = len(text.replace(";", " ").split())
    window = end - start - 0.6
    segs.append({"n": i + 1, "start": start, "end": end, "play_at": round(start + 0.3, 1), "window": round(window, 1), "words": words, "budget": int(window * WPS), "text": text})
    assert words <= window * WPS + 1, f"clip {i + 1} has {words} words but the window only fits about {int(window * WPS)}"

out = os.path.join(ROOT, "submission", "voiceover")
os.makedirs(os.path.join(out, "clips"), exist_ok=True)
json.dump({"video": os.path.abspath(os.path.join(folder, "anvil-demo.mp4")), "video_end": VIDEO_END, "extend": EXTEND, "segments": segs}, open(os.path.join(out, "narration.json"), "w", encoding="utf-8"), indent=1)
for s in segs:
    open(os.path.join(out, "clips", f"{s['n']:02d}.txt"), "w", encoding="utf-8").write(s["text"] + "\n")


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


with open(os.path.join(out, "NARRATION-SCRIPT.md"), "w", encoding="utf-8") as f:
    f.write("# Anvil demo: voice-over script, cut to the video\n\n")
    f.write(f"Video: `demo_recording_v2/anvil-demo.mp4` ({mmss(VIDEO_END)}). Each clip below starts at the time shown, 0.3 s after the on-screen change, and fits its window at a calm pace (about {WPS} words a second).\n")
    f.write("Spellings are written the way a voice should read them (for example \"A to A\" and \"A P 2\").\n\n")
    f.write("| Clip | Starts at | Window | Words | What is on screen | Say |\n|---|---|---|---|---|---|\n")
    rows = tl["rows"]
    for i, s in enumerate(segs):
        row = SEGMENTS[i][0]
        nxt = SEGMENTS[i + 1][0] if i + 1 < len(SEGMENTS) else len(rows)
        screen = "; ".join(r["note"] for r in rows[row:nxt])
        f.write(f"| {s['n']:02d} | {mmss(s['play_at'])} | {s['window']:.1f} s | {s['words']}/{s['budget']} | {screen[:90]} | {s['text']} |\n")
    f.write("\n## Plain text, one clip per block (paste each into your text-to-speech tool)\n\n")
    for s in segs:
        f.write(f"**Clip {s['n']:02d}**  (starts {mmss(s['play_at'])}, up to {s['window']:.1f} s)\n\n{s['text']}\n\n")
print(f"{len(segs)} clips written to {out}")
for s in segs:
    print(f"{s['n']:02d} {mmss(s['play_at'])} window {s['window']:4.1f}s  {s['words']:2d}/{s['budget']:2d} words")
