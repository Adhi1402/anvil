"""Records the whole Anvil demo as a silent screen video (with on-screen captions and a visible mouse), in the right order,
and takes the screenshots used in the pitch deck in the same run. You add the voice-over afterwards.

  # 1. start the app (pick ONE):
  #    a) against the deployed site (best for the final video): nothing to start, just pass its URL
  #    b) on your laptop with the real Gemini model and NO cloud data:
  #         ANVIL_REAL_GEMINI=1 python scripts/serve_offline.py 8080     (terminal 1)
  #         python scripts/serve_dashboard.py 8100                       (terminal 2)
  # 2. record:
  #    python scripts/record_demo.py http://localhost:8100/index.html http://localhost:8080
  #    python scripts/record_demo.py https://dazzling-lodge-511607-m0.web.app            (deployed: writes demo entries to the live system,
  #                                                                                      so start a "new session" on the Audit page first)
  # Output (folder demo_recording/): anvil-demo.webm / anvil-demo.mp4, timeline.md (what is on screen at what second, for your
  # voice-over), and screenshots/*.png.
Total length is printed at the end; the challenge allows 3 to 4 minutes."""
import argparse
import os
import shutil
import subprocess
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("url", nargs="?", default="http://localhost:8100/index.html")
ap.add_argument("api", nargs="?", default="")
ap.add_argument("--out", default="demo_recording")
ap.add_argument("--no-captions", action="store_true")
ap.add_argument("--browser", default=os.environ.get("ANVIL_BROWSER", "msedge"))
ap.add_argument("--speed", type=float, default=1.0, help="pause multiplier (1.0 = normal, 0.5 = faster)")
args = ap.parse_args()

W, H = 1366, 768
OUT = os.path.abspath(args.out)
SHOTS = os.path.join(OUT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
D = lambda n: (date.today() + timedelta(days=n)).isoformat()
base = args.url.split("?")[0].split("#")[0]
q = ("&api=" + args.api) if args.api else ""
timeline = []
waits = []                       # (start, end) seconds of long Gemini waits: shown as a labelled time-lapse so the video length does not depend on model latency
T0 = None

INIT = r"""
(() => {
  try { localStorage.setItem('anvil-sim', '0'); } catch (e) {}          // no simulated traffic on screen: the story is Rahul, Adhish and Swathy
  const add = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;width:20px;height:20px;border-radius:50%;background:rgba(52,81,209,.30);border:2px solid #3451D1;pointer-events:none;transform:translate(-50%,-50%);left:-60px;top:-60px;transition:transform .08s,background .1s';
    document.documentElement.appendChild(c);
    const cap = document.createElement('div'); cap.id = '__cap';
    cap.style.cssText = 'position:fixed;z-index:2147483646;left:50%;bottom:24px;transform:translateX(-50%);max-width:72%;background:rgba(16,24,40,.9);color:#fff;padding:11px 20px;border-radius:12px;font:600 18px/1.35 system-ui,sans-serif;text-align:center;opacity:0;transition:opacity .3s;pointer-events:none';
    document.documentElement.appendChild(cap);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.style.transform = 'translate(-50%,-50%) scale(.6)'; c.style.background = 'rgba(52,81,209,.7)'; }, true);
    addEventListener('mouseup', () => { c.style.transform = 'translate(-50%,-50%) scale(1)'; c.style.background = 'rgba(52,81,209,.30)'; }, true);
  };
  if (document.readyState !== 'loading') add(); else document.addEventListener('DOMContentLoaded', add);
  window.__tl = on => { let b = document.getElementById('__tl'); if (!b) { b = document.createElement('div'); b.id = '__tl'; b.style.cssText = 'position:fixed;z-index:2147483646;top:16px;right:18px;background:rgba(181,71,8,.95);color:#fff;padding:6px 14px;border-radius:999px;font:700 14px system-ui,sans-serif;letter-spacing:.04em'; b.textContent = 'TIME-LAPSE: Gemini is working'; document.documentElement.appendChild(b); } b.style.display = on ? 'block' : 'none'; };
  window.__cap = t => { const e = document.getElementById('__cap'); if (!e) return; if (!t) { e.style.opacity = 0; return; } e.textContent = t; e.style.opacity = 1; };
})();
"""


def wait(page, ms):
    page.wait_for_timeout(int(ms * args.speed))


def cap(page, text, note=""):
    """Show a caption on the video and log it to the timeline."""
    timeline.append((time.time() - T0, text, note))
    if not args.no_captions:
        page.evaluate("t => window.__cap && window.__cap(t)", text)


def uncap(page):
    if not args.no_captions:
        page.evaluate("window.__cap && window.__cap('')")


def shot(page, name):
    """Screenshots for the deck are taken without the video caption on top."""
    page.evaluate("(() => { const e = document.getElementById('__cap'); if (e) { e.dataset.o = e.style.opacity; e.style.opacity = 0; } const c = document.getElementById('__cur'); if (c) c.style.visibility = 'hidden'; })()")
    wait(page, 350)
    page.screenshot(path=os.path.join(SHOTS, name + ".png"))
    page.evaluate("(() => { const e = document.getElementById('__cap'); if (e && e.dataset.o !== undefined) e.style.opacity = e.dataset.o; const c = document.getElementById('__cur'); if (c) c.style.visibility = 'visible'; })()")


def click(page, selector, pause=450, **kw):
    loc = page.locator(selector).first
    loc.scroll_into_view_if_needed()
    box = loc.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=22)
        wait(page, 250)
    loc.click(**kw)
    wait(page, pause)


def type_into(page, selector, text, delay=28):
    loc = page.locator(selector).first
    box = loc.bounding_box()
    if box:
        page.mouse.move(box["x"] + 40, box["y"] + box["height"] / 2, steps=18)
    loc.click()
    loc.fill("")
    loc.press_sequentially(text, delay=delay)
    wait(page, 300)


def go(page, who, hash_=""):
    page.goto(f"{base}?as={who}{q}{hash_}")
    page.wait_for_selector("#page-title", timeout=60000)
    wait(page, 1200)


def scroll_to(page, selector, block="start"):
    page.locator(selector).first.evaluate("(e, b) => e.scrollIntoView({behavior: 'smooth', block: b})", block)
    wait(page, 900)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=args.browser or None, headless=True)
    ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=os.path.join(OUT, "raw"), record_video_size={"width": W, "height": H})
    ctx.add_init_script(INIT)
    T0 = time.time()
    page = ctx.new_page()

    # ---------------------------------------------------------------- 1. the idea (sign-in page)
    page.goto(f"{base}{('?' + q[1:]) if q else ''}")
    page.wait_for_selector("#login.on, #login", timeout=60000)
    wait(page, 800)
    cap(page, "Anvil: let AI agents spend company money, and prove every purchase matched what a person approved", "Sign-in page: the rotating cube is the idea: signed mandate, Gemini audit, enforce, prove")
    shot(page, "01_signin")
    wait(page, 6500)
    uncap(page)

    # ---------------------------------------------------------------- 2. employee plans a trip
    go(page, "rahul")
    page.wait_for_selector("#h-list", timeout=30000)
    wait(page, 1500)
    if page.locator("#trip-form:not([hidden])").count() == 0:      # an employee who already has trips opens the form with the button
        click(page, "[data-act=newtrip]")
    page.wait_for_selector("#trip-form:not([hidden])", timeout=30000)
    cap(page, "Rahul, an employee, plans a trip: real dates, round trip, purpose and cost centre", "Employee workspace: the trip form opens by itself the first time")
    click(page, "#t-to")
    page.select_option("#t-to", "Goa")
    wait(page, 400)
    page.fill("#t-dep", D(3))
    page.fill("#t-ret", D(5))
    wait(page, 500)
    type_into(page, "#t-just", "Customer escalation: on-site support for our Goa client")
    cap(page, "The form warns him: leaving in 3 days breaks the 7-day notice rule, so finance will have to approve", "The estimate panel on the right shows the warning")
    shot(page, "02_trip_form")
    wait(page, 4200)
    uncap(page)

    cap(page, "He sends it. Anvil Guard compares every offer, a Gemini agent picks one, and Anvil audits each booking", "Live Anvil Guard feed: offers pop in, the agent's pick lifts out, a scan sweeps, the verdict lands")
    click(page, "#t-go")
    wait(page, 2500)
    shot(page, "03_guard_start")
    w0 = time.time() - T0
    page.evaluate("window.__tl && window.__tl(true)")
    page.wait_for_function("/Sent for approval|Approved\\.|blocked/i.test(document.querySelector('#gl-end')?.innerText||'')", timeout=180000)
    page.evaluate("window.__tl && window.__tl(false)")
    waits.append((w0, time.time() - T0))
    wait(page, 1500)
    scroll_to(page, "#gl-legs", "start")
    shot(page, "04_guard_done")
    uncap(page)

    cap(page, "Here is the final itinerary, day by day: flights with times, the cabs with pickup and drop, the hotel. Nothing is booked until finance approves", "Itinerary card at the end of the booking panel")
    scroll_to(page, ".final-itin", "start")
    shot(page, "05_itinerary_pending")
    wait(page, 6500)
    uncap(page)

    page.click("[data-act=closeform]")
    wait(page, 800)
    cap(page, "Every booking keeps what the agent considered: each offer, whether the policy allows it, and the agent's reasoning", "Open 'See the options considered' on the outbound flight")
    page.wait_for_selector("#h-list .item")
    click(page, "#h-list .item .opt-toggle")
    scroll_to(page, ".optp", "start")
    shot(page, "06_options_considered")
    wait(page, 6500)
    uncap(page)

    # ---------------------------------------------------------------- 3. finance approves the whole trip
    go(page, "adhish")
    page.wait_for_selector("#a-list .item", timeout=30000)
    cap(page, "Adhish, the finance manager, sees one card for the whole trip: dates, purpose, cost centre, why it needs him, and how soon it departs", "Approvals page")
    shot(page, "07_approval")
    wait(page, 5500)
    type_into(page, "[data-comment]", "Approved: customer escalation")
    cap(page, "He approves the whole trip in one click. He cannot approve his own requests, and the people who run the agents cannot approve at all", "Click 'Approve all'")
    click(page, "#a-list [data-act=approve]")
    page.wait_for_selector(".toast", timeout=30000)
    wait(page, 2500)
    uncap(page)

    go(page, "rahul", "#/home")
    page.wait_for_selector("#h-list .item")
    cap(page, "Back with Rahul: the trip is approved, each booking has a signed receipt reference, and he knows who approved it and why", "Rahul's trip card after approval")
    page.wait_for_function("document.querySelector('#h-list')?.innerText.includes('Booking ref')", timeout=20000)
    scroll_to(page, "#h-list .item", "start")
    shot(page, "08_trip_approved")
    wait(page, 6500)
    uncap(page)

    # ---------------------------------------------------------------- 4. finance edits the policy
    go(page, "adhish", "#/policy")
    page.wait_for_selector("[data-act=editpolicy]", timeout=20000)
    cap(page, "Finance owns the policy. Limits, approved cities and trip rules are editable, and every change is re-signed", "Policy page")
    click(page, "[data-act=editpolicy]")
    page.wait_for_selector("#pe-hotel")
    page.fill("#pe-hotel", "")
    page.locator("#pe-hotel").press_sequentially("350", delay=90)
    type_into(page, "#pe-why", "Conference week hotel rates in Mumbai are higher")
    shot(page, "09_policy_edit")
    wait(page, 2500)
    click(page, "[data-act=savepolicy]")
    page.wait_for_selector("#cd-ok")
    wait(page, 2500)
    cap(page, "He sees exactly what will change, signs it, and it is live for the next request, with who, when and why on record", "Confirm dialog, then the new version in the history")
    click(page, "#cd-ok")
    page.wait_for_function("document.querySelector('#p-hist')?.innerText.includes('Version 2')", timeout=20000)
    scroll_to(page, "#p-hist", "start")
    shot(page, "10_policy_history")
    wait(page, 4500)
    uncap(page)

    # ---------------------------------------------------------------- 5. operator: overview, AI traces, audit chain
    go(page, "swathy")
    cap(page, "Swathy runs the AI agents. This is Anvil Guard: every decision checked, the money kept from being spent, and what went to a person", "Operator overview")
    wait(page, 4500)
    shot(page, "11_overview")
    uncap(page)

    page.evaluate("location.hash='#/traces'")
    page.wait_for_selector("#tr-list .item", timeout=30000)
    wait(page, 1200)
    cap(page, "AI traces: every call to Gemini with the exact input it was given and the exact output it returned, with time, tokens and cost", "AI traces page")
    click(page, "[data-act=trfilter][data-k=audit]")
    page.wait_for_selector("#tr-list .item")
    type_into(page, "#tr-q", "Goa")
    wait(page, 600)
    click(page, "#tr-list .item")
    page.wait_for_selector(".trace-detail pre", timeout=20000)
    scroll_to(page, ".trace-detail", "start")
    shot(page, "12_ai_trace")
    wait(page, 7500)
    uncap(page)

    page.evaluate("location.hash='#/audit'")
    page.wait_for_selector("#trail .entry", timeout=20000)
    wait(page, 800)
    cap(page, "Every decision is linked to the one before it by a hash. Edit history and the chain breaks, and the break shows", "Audit trail: click 'Simulate tampering'")
    shot(page, "13_audit_chain")
    click(page, "[data-act=tamper]")
    wait(page, 5500)
    uncap(page)

    # ---------------------------------------------------------------- 6. why it matters: unprotected vs protected
    page.evaluate("location.hash='#/demo'")
    page.wait_for_selector("#d-rogue .chip", timeout=20000)
    wait(page, 800)
    cap(page, "Why it matters. The same agent, tempted by business class, with Anvil switched off", "Demo studio: enforcement OFF, business-class swap")
    click(page, "#enf")
    click(page, "#d-rogue [data-scn='Business-class upgrade']")
    page.wait_for_selector("#runsum:has-text('leaked')", timeout=120000)
    wait(page, 800)
    scroll_to(page, "#stagebox", "start")
    cap(page, "Booked with no check: the money leaks. Now switch Anvil on", "Leak counter")
    shot(page, "14_unprotected_leak")
    wait(page, 3500)
    wait(page, 2500)
    click(page, "#enf")
    click(page, "#d-rogue [data-scn='Business-class upgrade']")
    w0 = time.time() - T0
    page.evaluate("window.__tl && window.__tl(true)")
    page.wait_for_selector("#runsum:has-text('Run summary')", timeout=180000)
    page.evaluate("window.__tl && window.__tl(false)")
    waits.append((w0, time.time() - T0))
    wait(page, 1500)
    scroll_to(page, "#stagebox", "start")
    cap(page, "With Anvil: blocked, with the reason, the agent corrects itself, and the new booking is audited again before it is allowed", "Blocked, self-corrected, re-audited")
    shot(page, "15_protected_block")
    wait(page, 6500)
    uncap(page)

    cap(page, "Anvil: a signed policy, Gemini judging intent, code enforcing it, and proof of every decision", "Closing")
    page.evaluate("window.scrollTo(0,0)")
    wait(page, 5500)
    uncap(page)
    total = time.time() - T0
    video = page.video
    ctx.close()
    raw = video.path()
    browser.close()

webm = os.path.join(OUT, "anvil-demo-full.webm")
shutil.move(raw, webm)
shutil.rmtree(os.path.join(OUT, "raw"), ignore_errors=True)
mp4 = os.path.join(OUT, "anvil-demo.mp4")
TARGET = 20                      # seconds a long Gemini wait is compressed to
cuts = []                        # (start, end, factor)
for a0, b0 in waits:
    d = b0 - a0
    if d > TARGET + 4:
        cuts.append((a0, b0, d / TARGET))


def newt(t):
    """Time in the final video of an instant in the raw recording."""
    out = t
    for a0, b0, f in cuts:
        if t >= b0:
            out -= (b0 - a0) * (1 - 1 / f)
        elif t > a0:
            out -= (t - a0) * (1 - 1 / f)
    return out


try:
    pts = [0.0] + [x for a0, b0, f in cuts for x in (a0, b0)] + [total + 5]
    segs = [(pts[i], pts[i + 1], next((f for a0, b0, f in cuts if a0 == pts[i] and b0 == pts[i + 1]), 1.0)) for i in range(len(pts) - 1)]
    live = [(a0, b0, f) for a0, b0, f in segs if b0 > a0]
    filt = "".join(f"[0:v]trim=start={a0:.3f}:end={b0:.3f},setpts=(PTS-STARTPTS)/{f:.4f}[v{i}];" for i, (a0, b0, f) in enumerate(live)) + "".join(f"[v{i}]" for i in range(len(live))) + f"concat=n={len(live)}:v=1:a=0[out]"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-filter_complex", filt, "-map", "[out]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", mp4], check=True)
except Exception as e:
    mp4 = f"(not made: {e}; use anvil-demo-full.webm)"
final_len = newt(total)

with open(os.path.join(OUT, "timeline.md"), "w", encoding="utf-8") as f:
    f.write("# Demo recording timeline (use it to time your voice-over)\n\n| Time | On screen (caption) | What is happening |\n|---|---|---|\n")
    for t, text, note in timeline:
        t = newt(t)
        f.write(f"| {int(t // 60)}:{int(t % 60):02d} | {text} | {note} |\n")
    f.write(f"\nTotal length: {int(final_len // 60)}:{int(final_len % 60):02d}\n")
    f.write("\nThe long Gemini waits are shown as a labelled time-lapse so the video stays short; narrate over them.\n")
print(f"\nDone. Total length {int(final_len // 60)}:{int(final_len % 60):02d} (limit 4:00)")
print("VIDEO TO USE:", mp4, "\nFull-speed original:", webm, "\nTimeline:", os.path.join(OUT, "timeline.md"), "\nScreenshots:", SHOTS)
if final_len > 235:
    print("WARNING: longer than 3:55. Re-run with --speed 0.8 to shorten the pauses.")
