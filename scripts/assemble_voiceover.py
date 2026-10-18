"""Puts your voice-over clips onto the demo video at the exact timestamps.
  python scripts/assemble_voiceover.py <clips_folder> [--out final.mp4] [--max-speedup 1.2]
<clips_folder> holds one audio file per clip named 01, 02 ... 21 (mp3, wav, m4a or flac), e.g. exported from MiniMax.
It reads submission/voiceover/narration.json (from scripts/build_narration.py), places each clip at its start time,
speeds a clip up slightly if it is longer than its window (never more than --max-speedup), trims long leading silence,
holds the last frame if the closing line runs past the video, and writes one MP4 with the voice mixed in.
Needs ffmpeg and ffprobe on the PATH."""
import argparse
import glob
import json
import os
import subprocess
import sys

ap = argparse.ArgumentParser()
ap.add_argument("clips")
ap.add_argument("--out", default=None)
ap.add_argument("--max-speedup", type=float, default=1.2)
ap.add_argument("--narration", default=None)
args = ap.parse_args()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
nar = json.load(open(args.narration or os.path.join(ROOT, "submission", "voiceover", "narration.json"), encoding="utf-8"))
video = nar["video"]
out = args.out or os.path.join(ROOT, "submission", "voiceover", "anvil-demo-with-voice.mp4")


def dur(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.strip())


def find(n):
    for ext in ("mp3", "wav", "m4a", "flac", "ogg", "aac"):
        for pat in (f"{n:02d}.{ext}", f"{n}.{ext}", f"clip{n:02d}.{ext}", f"clip_{n:02d}.{ext}"):
            p = os.path.join(args.clips, pat)
            if os.path.exists(p):
                return p
    hits = sorted(glob.glob(os.path.join(args.clips, f"*{n:02d}*")))
    return hits[0] if hits else None


inputs, filters, labels, report, problems = [], [], [], [], []
last_end = 0.0
for s in nar["segments"]:
    path = find(s["n"])
    if not path:
        problems.append(f"clip {s['n']:02d}: no audio file found in {args.clips}")
        continue
    d = dur(path)
    window = s["end"] - s["play_at"] - 0.2
    tempo = 1.0
    if d > window:
        tempo = min(args.max_speedup, d / window)
        if d / tempo > window + 0.05:
            problems.append(f"clip {s['n']:02d} is {d:.1f}s but its window is {window:.1f}s even at {args.max_speedup}x: shorten the text or regenerate it a little faster")
    idx = len(inputs) // 2
    inputs += ["-i", path]
    chain = f"[{idx + 1}:a]aformat=sample_rates=44100:channel_layouts=stereo,silenceremove=start_periods=1:start_silence=0.15:start_threshold=-45dB"
    if tempo > 1.0001:
        chain += f",atempo={tempo:.4f}"
    ms = int(s["play_at"] * 1000)
    chain += f",adelay={ms}|{ms}[a{idx}]"
    filters.append(chain)
    labels.append(f"[a{idx}]")
    end_at = s["play_at"] + d / tempo
    last_end = max(last_end, end_at)
    report.append((s["n"], s["play_at"], d, tempo, window, end_at))

if not labels:
    sys.exit("No clips found. " + "; ".join(problems))

vid_len = nar["video_end"]
pad = max(0.0, last_end + 0.6 - vid_len)
filt = ";".join(filters) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:dropout_transition=0,volume={len(labels)},alimiter=limit=0.95[voice]"   # the clips never overlap, so undo amix's 1/N gain
vfilter = f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.2f}[v]" if pad > 0.05 else "[0:v]null[v]"
cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video] + inputs + ["-filter_complex", vfilter + ";" + filt, "-map", "[v]", "-map", "[voice]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out]
subprocess.run(cmd, check=True)
print(f"{'clip':>4} {'starts':>7} {'length':>7} {'speedup':>8} {'window':>7} {'ends':>7}")
for n, at, d, tempo, window, end_at in report:
    flag = "  <- tight" if tempo > 1.0001 else ""
    print(f"{n:>4} {at:7.1f} {d:7.1f} {tempo:8.2f} {window:7.1f} {end_at:7.1f}{flag}")
total = vid_len + pad
print(f"\nWrote {out}  (length {int(total // 60)}:{total % 60:04.1f})")
for p in problems:
    print("PROBLEM:", p)
if total > 240:
    print("WARNING: over 4:00")
