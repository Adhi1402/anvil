"""Measures, from the finished video itself, the exact second each on-screen caption (or title card) appears.
  python scripts/align_timeline.py demo_recording_v2
Reads <folder>/anvil-demo.mp4 and <folder>/timeline.md; writes <folder>/timeline.json (start seconds to 0.1 s)."""
import json
import os
import re
import subprocess
import sys

import numpy as np

folder = sys.argv[1] if len(sys.argv) > 1 else "demo_recording_v2"
mp4 = os.path.join(folder, "anvil-demo.mp4")
rows = []
for line in open(os.path.join(folder, "timeline.md"), encoding="utf-8"):
    m = re.match(r"\| (\d+):(\d+) \| (.*?) \| (.*?) \|$", line.rstrip())
    if m:
        rows.append({"approx": int(m.group(1)) * 60 + int(m.group(2)), "caption": m.group(3), "note": m.group(4)})
FPS = 10
W, H = 96, 12
# the caption box sits bottom-centre: crop it (1366x768 video), shrink, grey
cmd = ["ffmpeg", "-loglevel", "error", "-i", mp4, "-vf", f"fps={FPS},crop=760:120:303:632,scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
raw = subprocess.run(cmd, capture_output=True, check=True).stdout
frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, H * W).astype(np.float32)
# full-frame stats too, to find title-card switches
cmd2 = ["ffmpeg", "-loglevel", "error", "-i", mp4, "-vf", f"fps={FPS},scale=48:27,format=gray", "-f", "rawvideo", "-"]
full = np.frombuffer(subprocess.run(cmd2, capture_output=True, check=True).stdout, dtype=np.uint8).reshape(-1, 48 * 27).astype(np.float32)
dark = frames.mean(axis=1) < 200                      # a caption box (dark) over the light app; title cards are dark everywhere
d_cap = np.abs(np.diff(frames, axis=0)).mean(axis=1)    # change inside the caption area
d_all = np.abs(np.diff(full, axis=0)).mean(axis=1)      # change anywhere
events = []
for i in range(1, len(frames)):
    t = i / FPS
    rise = dark[i] and not dark[i - 1]
    text_change = dark[i] and dark[i - 1] and d_cap[i - 1] > 0.12
    card_cut = d_all[i - 1] > 6
    if rise or text_change or card_cut:
        events.append(round(t, 1))
# merge events closer than 0.6 s
merged = []
for t in events:
    if not merged or t - merged[-1] > 0.6:
        merged.append(t)
out, used = [], set()
for r in rows:
    cands = [t for t in merged if r["approx"] - 0.9 <= t <= r["approx"] + 2.4 and t not in used]
    t = min(cands, key=lambda x: abs(x - (r["approx"] + 0.5))) if cands else float(r["approx"])
    used.add(t)
    out.append({**r, "start": t, "measured": bool(cands)})
dur = len(frames) / FPS
json.dump({"duration": dur, "rows": out}, open(os.path.join(folder, "timeline.json"), "w"), indent=1)
for r in out:
    print(f"{r['start']:6.1f}s {'ok ' if r['measured'] else 'est'} {r['caption'][:70]}")
print("duration", dur)
