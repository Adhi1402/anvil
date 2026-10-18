"""Demo recording v2: the complete story in under four minutes (silent video with captions; you add the voice).

  python scripts/record_demo_v2.py https://dazzling-lodge-511607-m0.web.app/ [--out demo_recording_v2] [--speed 0.8]

What it shows, in order:
  1 the problem, then the ENGINE and its domains (title cards)       6 finance approves the whole trip, the employee sees it
  2 an employee plans a trip and tempts the agent (business class)   7 the finance manager edits and signs the policy
  3 Anvil Guard: offers compared, BLOCK, self-correction, escalation 8 the operator: Anvil Guard, AI traces (exact Gemini input and
  4 the day-by-day itinerary, and what the agent considered            output), the tamper-evident chain
  5 (the late trip waits for finance)                                 9 unprotected vs protected, the second domain, the tech stack
Writes: anvil-demo.mp4 (the video to use), anvil-demo-full.webm, timeline.md, screenshots/*.png.
Long Gemini waits are compressed into a labelled time-lapse so the length does not depend on model latency.
It writes demo entries to the system it is pointed at and changes the hotel limit to $350 during the policy scene: restore it to $300 afterwards."""
import argparse
import os
import shutil
import subprocess
import time
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("url", nargs="?", default="https://dazzling-lodge-511607-m0.web.app/")
ap.add_argument("api", nargs="?", default="")
ap.add_argument("--out", default="demo_recording_v2")
ap.add_argument("--no-captions", action="store_true")
ap.add_argument("--browser", default=os.environ.get("ANVIL_BROWSER", "msedge"))
ap.add_argument("--speed", type=float, default=0.8, help="pause multiplier (1.0 = relaxed, 0.8 = default, 0.6 = brisk)")
args = ap.parse_args()

W, H = 1366, 768
OUT = os.path.abspath(args.out)
SHOTS = os.path.join(OUT, "screenshots")
os.makedirs(SHOTS, exist_ok=True)
D = lambda n: (date.today() + timedelta(days=n)).isoformat()
base = args.url.split("?")[0].split("#")[0]
q = ("&api=" + args.api) if args.api else ""
timeline, waits = [], []
T0 = None
corrected = False

INIT = r"""
(() => {
  try { localStorage.setItem('anvil-sim', '0'); } catch (e) {}
  const add = () => {
    if (document.getElementById('__cur') || !document.body) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;width:20px;height:20px;border-radius:50%;background:rgba(52,81,209,.30);border:2px solid #3451D1;pointer-events:none;transform:translate(-50%,-50%);left:-60px;top:-60px;transition:transform .08s,background .1s';
    document.documentElement.appendChild(c);
    const cap = document.createElement('div'); cap.id = '__cap';
    cap.style.cssText = 'position:fixed;z-index:2147483646;left:50%;bottom:24px;transform:translateX(-50%);max-width:74%;background:rgba(16,24,40,.92);color:#fff;padding:11px 20px;border-radius:12px;font:600 18px/1.35 system-ui,sans-serif;text-align:center;opacity:0;transition:opacity .3s;pointer-events:none';
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

CARD_CSS = """
*{box-sizing:border-box;margin:0}body{background:#0B1020;color:#F2F4F7;font-family:system-ui,-apple-system,'Segoe UI',sans-serif;overflow:hidden;width:100vw;height:100vh}
.s{position:absolute;inset:0;padding:56px 72px;display:none;flex-direction:column;justify-content:center}.s.on{display:flex;animation:in .6s ease both}
@keyframes in{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.brand{position:absolute;top:30px;left:72px;font-weight:800;letter-spacing:.28em;color:#9BB2FF;font-size:15px}
h1{font-size:44px;line-height:1.15;letter-spacing:-.02em;max-width:1100px}h1 b{color:#7C9BFF}
p.sub{font-size:21px;color:#AEB8CC;margin-top:16px;max-width:980px;line-height:1.45}
.row{display:flex;gap:16px;flex-wrap:wrap;margin-top:34px}
.chip{padding:12px 18px;border-radius:14px;border:1px solid #2E3A50;background:#131A27;font-size:18px;opacity:0;animation:in .5s ease forwards}
.chip.bad{border-color:#F97066;color:#FDA29B}.chip small{display:block;color:#98A2B3;font-size:13px;margin-top:2px}
.pipe{display:flex;align-items:center;gap:14px;margin-top:34px}
.st{flex:1;padding:20px 18px;border-radius:16px;border:1.5px solid #3451D1;background:linear-gradient(160deg,#16204A,#101735);opacity:0;animation:in .6s ease forwards;text-align:center}
.st b{display:block;font-size:22px;color:#fff}.st span{display:block;color:#AEB8CC;font-size:15px;margin-top:6px}
.ar{color:#7C9BFF;font-size:28px;opacity:0;animation:in .5s ease forwards}
.dom{display:flex;gap:14px;margin-top:40px;flex-wrap:wrap}.d{padding:14px 20px;border-radius:14px;font-size:18px;border:1px solid #2E3A50;background:#131A27;opacity:0;animation:in .5s ease forwards}
.d.live{border-color:#47CD89;color:#A6F4C5}.d.proven{border-color:#7C9BFF;color:#C7D7FE}.d.next{color:#98A2B3;border-style:dashed}
.note{margin-top:30px;font-size:22px;color:#fff;font-weight:600;opacity:0;animation:in .6s ease forwards}
svg text{font-family:system-ui,sans-serif}
"""

PROBLEM_ENGINE = f"""<!doctype html><meta charset=utf-8><style>{CARD_CSS}</style>
<div class=brand>ANVIL</div>
<div class="s on" id=a><h1>AI agents are starting to <b>spend company money</b>.<br>Nothing proves they stayed inside what a person approved.</h1>
<p class=sub>Budget caps and allowlists only look at numbers. They miss what a purchase really is.</p>
<div class=row>
<span class="chip bad" style="animation-delay:.8s">Economy swapped for business class<small>at an approved price</small></span>
<span class="chip bad" style="animation-delay:1.4s">One booking split in two<small>to stay under the approval limit</small></span>
<span class="chip bad" style="animation-delay:2s">A lounge membership in the extras<small>nobody asked for</small></span>
<span class="chip bad" style="animation-delay:2.6s">“The CFO pre-approved this”<small>a note an agent wrote itself</small></span></div></div>
<div class=s id=b><h1>Anvil is the <b>engine</b> that makes agent spending safe.</h1>
<div class=pipe><div class=st style="animation-delay:.3s"><b>1 Signed mandate</b><span>what a person approved</span></div><span class=ar style="animation-delay:.6s">→</span>
<div class=st style="animation-delay:.9s"><b>2 Intent audit</b><span>Gemini judges the meaning</span></div><span class=ar style="animation-delay:1.2s">→</span>
<div class=st style="animation-delay:1.5s"><b>3 Enforce in code</b><span>rules + AP2 limits, approve, escalate, block</span></div><span class=ar style="animation-delay:1.8s">→</span>
<div class=st style="animation-delay:2.1s"><b>4 Prove</b><span>receipts, hash chain, AI traces</span></div></div>
<div class=dom><span class="d live" style="animation-delay:2.6s">Enterprise travel and expense: LIVE (this demo)</span><span class="d proven" style="animation-delay:3.0s">Software licences: proven, 8 of 8</span>
<span class="d next" style="animation-delay:3.4s">Procurement</span><span class="d next" style="animation-delay:3.7s">Cloud spend</span><span class="d next" style="animation-delay:4.0s">Payments</span></div>
<div class=note style="animation-delay:4.4s">One engine. Any domain where agents act for the enterprise.</div></div>
<script>window.show=n=>{{document.getElementById('a').classList.toggle('on',n==1);document.getElementById('b').classList.toggle('on',n==2)}}</script>"""

ARCH = f"""<!doctype html><meta charset=utf-8><style>{CARD_CSS}
.box{{fill:#131A27;stroke:#2E3A50;stroke-width:1.5}}.big{{fill:#101735;stroke:#3451D1;stroke-width:2}}.ln{{stroke:#7C9BFF;stroke-width:2;fill:none;marker-end:url(#h)}}
.t{{fill:#fff;font-size:19px;font-weight:700}}.u{{fill:#AEB8CC;font-size:14px}}.g{{stroke:#47CD89}}.y{{stroke:#FDB022}}
</style><div class=brand>ANVIL</div>
<div class="s on" style="padding:70px 40px 20px"><svg viewBox="0 0 1286 600" width="100%" height="100%">
<defs><marker id=h markerWidth=10 markerHeight=10 refX=8 refY=5 orient=auto><path d="M0 0L10 5L0 10z" fill="#7C9BFF"/></marker></defs>
<rect class=box x=10 y=70 width=250 height=120 rx=16 /><text class=t x=30 y=108>Firebase Hosting</text><text class=u x=30 y=136>Web app: employee, finance,</text><text class=u x=30 y=156>operator workspaces</text>
<rect class=big x=360 y=40 width=520 height=220 rx=20 /><text class=t x=385 y=78>Cloud Run: anvil (API)</text>
<rect class=box x=385 y=100 width=225 height=64 rx=12 /><text class=u x=400 y=138>Booking agent (A2A client)</text><rect class=box x=630 y=100 width=225 height=64 rx=12 /><text class=u x=645 y=128>Anvil Guard: audit,</text><text class=u x=645 y=148>trip rules, AP2 gate</text>
<rect class=box x=385 y=180 width=225 height=64 rx=12 /><text class=u x=400 y=208>Policy, approvals,</text><text class=u x=400 y=228>controls</text><rect class=box x=630 y=180 width=225 height=64 rx=12 /><text class=u x=645 y=208>Evidence, AI traces,</text><text class=u x=645 y=228>hash chain</text>
<rect class=box x=980 y=70 width=296 height=120 rx=16 /><text class=t x=1000 y=108>Cloud Run: suppliers</text><text class=u x=1000 y=136>A2A agents with Agent Cards:</text><text class=u x=1000 y=156>flights, hotels, transport</text>
<rect class=box x=60 y=400 width=330 height=130 rx=16 style="stroke:#47CD89"/><text class=t x=80 y=438 style="fill:#A6F4C5">Firestore</text><text class=u x=80 y=466>Hash-chained audit log, policy versions,</text><text class=u x=80 y=486>AI traces, controls. Live feed to the browser.</text>
<rect class=box x=470 y=400 width=330 height=130 rx=16 style="stroke:#FDB022"/><text class=t x=490 y=438 style="fill:#FEDF89">Vertex AI: Gemini 2.5 Flash</text><text class=u x=490 y=466>Plans the trip, audits every booking,</text><text class=u x=490 y=486>corrects after a block. JSON, temp 0.</text>
<rect class=box x=880 y=400 width=380 height=130 rx=16 /><text class=t x=900 y=438>Secret Manager + AP2 SDK</text><text class=u x=900 y=466>Orchestrator key; signed mandate chains</text><text class=u x=900 y=486>verified for every approved booking.</text>
<path class=ln d="M260 130H360"/><path class=ln d="M880 110H980"/><path class=ln d="M980 160H880"/><path class=ln d="M620 260V400"/><path class=ln d="M440 260L300 400" /><path class=ln g d="M135 190V400" style="stroke:#47CD89"/><path class=ln d="M760 260L1000 400"/>
<text class=u x=275 y=118>HTTPS</text><text class=u x=905 y=100>A2A</text><text class=u x=150 y=300 style="fill:#A6F4C5">live feed</text></svg>
<div style="position:absolute;left:0;right:0;bottom:34px;text-align:center;font-size:24px;font-weight:700">Built on Google Cloud: Gemini, Cloud Run, Firestore, Firebase Hosting, A2A and AP2</div></div>"""


def wait(page, ms):
    page.wait_for_timeout(int(ms * args.speed))


def cap(page, text, note=""):
    timeline.append((time.time() - T0, text, note))
    if not args.no_captions:
        page.evaluate("t => window.__cap && window.__cap(t)", text)


def uncap(page):
    if not args.no_captions:
        page.evaluate("window.__cap && window.__cap('')")


def mark(text, note=""):
    """A scene with no caption (title cards carry their own text)."""
    timeline.append((time.time() - T0, text, note))


def shot(page, name):
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


def type_into(page, selector, text, delay=26):
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
    wait(page, 1000)


def scroll_to(page, selector, block="start"):
    page.locator(selector).first.evaluate("(e, b) => e.scrollIntoView({behavior: 'smooth', block: b})", block)
    wait(page, 900)


def lapse(page, fn):
    """Run a long Gemini wait as a labelled time-lapse."""
    w0 = time.time() - T0
    page.evaluate("window.__tl && window.__tl(true)")
    fn()
    page.evaluate("window.__tl && window.__tl(false)")
    waits.append((w0, time.time() - T0))


with sync_playwright() as p:
    browser = p.chromium.launch(channel=args.browser or None, headless=True)
    ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=os.path.join(OUT, "raw"), record_video_size={"width": W, "height": H})
    ctx.add_init_script(INIT)
    T0 = time.time()
    page = ctx.new_page()

    # ============================================================ 1. the problem and the engine (title cards)
    page.set_content(PROBLEM_ENGINE)
    mark("THE PROBLEM: agents spend company money; caps and allowlists miss class swaps, split charges, hidden add-ons, fake approvals", "Title card 1")
    page.screenshot(path=os.path.join(SHOTS, "00_problem.png"))
    wait(page, 11500)
    page.evaluate("show(2)")
    mark("THE ENGINE: signed mandate, Gemini intent audit, enforce in code, prove; domains: travel (live), software (proven), procurement, cloud, payments", "Title card 2: Anvil is an engine; enterprise trip booking is the example")
    wait(page, 4800)
    page.screenshot(path=os.path.join(SHOTS, "00_engine.png"))
    wait(page, 7000)

    # ============================================================ 2. the people (sign-in page)
    page.goto(f"{base}{('?' + q[1:]) if q else ''}")
    page.wait_for_selector("#login", timeout=60000)
    wait(page, 800)
    cap(page, "Our enterprise example: business trip booking, with three roles: an employee, a finance manager and a platform operator", "Sign-in page with the rotating engine cube")
    shot(page, "01_signin")
    wait(page, 5200)
    uncap(page)

    # ============================================================ 3. employee plans a trip and tempts the agent
    go(page, "rahul")
    page.wait_for_selector("#h-list", timeout=30000)
    wait(page, 1200)
    if page.locator("#trip-form:not([hidden])").count() == 0:
        click(page, "[data-act=newtrip]")
    page.wait_for_selector("#trip-form:not([hidden])", timeout=30000)
    cap(page, "Rahul, an employee, plans a trip to Goa: real dates, round trip, purpose and cost centre", "Employee workspace, trip form")
    page.select_option("#t-to", "Goa")
    page.fill("#t-dep", D(3))
    page.fill("#t-ret", D(5))
    wait(page, 400)
    type_into(page, "#t-just", "Customer escalation: on-site support for our Goa client")
    cap(page, "He also tells the booking agent what he would like: business class on Emirates. The agent will try to oblige", "Preferences field: the temptation")
    type_into(page, "#t-note", "I want business class on Emirates for both flights, whatever it costs.", delay=20)
    cap(page, "The form warns him: leaving in 3 days breaks the 7-day notice rule, so finance will have to approve", "Estimate panel warning")
    shot(page, "02_trip_form")
    wait(page, 3200)
    uncap(page)

    cap(page, "Anvil Guard compares every offer, the Gemini agent picks one per leg, and Anvil audits each booking before any money moves", "Live Anvil Guard feed")
    click(page, "#t-go")
    wait(page, 2200)
    shot(page, "03_guard_start")

    def wait_booking():
        page.wait_for_function("/Sent for approval|Approved\\.|blocked/i.test(document.querySelector('#gl-end')?.innerText||'')", timeout=180000)
    lapse(page, wait_booking)
    wait(page, 1200)
    scroll_to(page, "#gl-legs", "start")
    shot(page, "04_guard_done")
    uncap(page)
    corrected = page.locator("#gl-end .final-itin", has_text="Corrected by the agent").count() > 0

    cap(page, "The agent was tempted by business class. Anvil blocked it and told the agent why; the agent chose a compliant flight. The late trip now waits for finance", "BLOCK + self-correction + escalation in the employee flow")
    scroll_to(page, ".final-itin", "start")
    shot(page, "05_itinerary_pending")
    wait(page, 5200)
    cap(page, "Here is the itinerary, day by day: flights with times, cabs with pickup and from/to, the hotel. Nothing is booked until finance approves", "Itinerary card")
    wait(page, 4200)
    uncap(page)

    page.click("[data-act=closeform]")
    wait(page, 700)
    cap(page, "Anvil shows its work: every offer the agent considered, whether the policy allows it, and the agent's reasoning", "'See the options considered'")
    page.wait_for_selector("#h-list .item")
    click(page, "#h-list .item .opt-toggle")
    scroll_to(page, ".optp", "start")
    shot(page, "06_options_considered")
    wait(page, 5500)
    uncap(page)

    # ============================================================ 4. finance approves
    go(page, "adhish")
    page.wait_for_selector("#a-list .item", timeout=30000)
    cap(page, "Adhish, the finance manager, gets one card for the whole trip: dates, purpose, cost centre and exactly why it needs him", "Approvals page")
    shot(page, "07_approval")
    wait(page, 4200)
    type_into(page, "[data-comment]", "Approved: customer escalation")
    cap(page, "One click approves the trip. He cannot approve his own requests, and the people who run the agents cannot approve at all", "Approve all")
    click(page, "#a-list [data-act=approve]")
    page.wait_for_selector(".toast", timeout=30000)
    wait(page, 2000)
    uncap(page)

    go(page, "rahul", "#/home")
    page.wait_for_selector("#h-list .item")
    cap(page, "Back with Rahul: approved, with a signed booking reference on every item and who approved it", "Approved trip card")
    page.wait_for_function("document.querySelector('#h-list')?.innerText.includes('Booking ref')", timeout=20000)
    scroll_to(page, "#h-list .item", "start")
    shot(page, "08_trip_approved")
    wait(page, 5200)
    uncap(page)

    # ============================================================ 5. finance owns the policy
    go(page, "adhish", "#/policy")
    page.wait_for_selector("[data-act=editpolicy]", timeout=20000)
    cap(page, "Finance owns the policy. Limits, approved cities and trip rules are editable, and every change is re-signed", "Policy page")
    click(page, "[data-act=editpolicy]")
    page.wait_for_selector("#pe-hotel")
    page.fill("#pe-hotel", "")
    page.locator("#pe-hotel").press_sequentially("350", delay=90)
    type_into(page, "#pe-why", "Conference week hotel rates in Mumbai are higher")
    shot(page, "09_policy_edit")
    wait(page, 1800)
    click(page, "[data-act=savepolicy]")
    page.wait_for_selector("#cd-ok")
    wait(page, 2000)
    cap(page, "He reviews exactly what will change, signs it, and it is live for the next request, with who, when and why on record", "Confirm, then version history")
    click(page, "#cd-ok")
    page.wait_for_function("document.querySelector('#p-hist')?.innerText.includes('Version 2')", timeout=20000)
    scroll_to(page, "#p-hist", "start")
    shot(page, "10_policy_history")
    wait(page, 3500)
    uncap(page)

    # ============================================================ 6. operator: traces and the chain
    go(page, "swathy")
    cap(page, "Swathy runs the AI agents. Anvil Guard: every decision checked, the money kept from being spent, what went to a person", "Operator overview")
    wait(page, 3800)
    shot(page, "11_overview")
    uncap(page)
    page.evaluate("location.hash='#/traces'")
    page.wait_for_selector("#tr-list .item", timeout=30000)
    wait(page, 900)
    cap(page, "AI traces: every call to Gemini with the exact input it was given and the exact output it returned, plus time, tokens and cost", "AI traces page")
    click(page, "[data-act=trfilter][data-k=audit]")
    page.wait_for_selector("#tr-list .item")
    type_into(page, "#tr-q", "Goa")
    wait(page, 500)
    click(page, "#tr-list .item")
    page.wait_for_selector(".trace-detail pre", timeout=20000)
    scroll_to(page, ".trace-detail", "start")
    shot(page, "12_ai_trace")
    wait(page, 6200)
    uncap(page)
    page.evaluate("location.hash='#/audit'")
    page.wait_for_selector("#trail .entry", timeout=20000)
    wait(page, 700)
    cap(page, "Every decision is chained to the one before by a hash. Edit history and the chain breaks, and the break shows", "Audit trail, simulate tampering")
    shot(page, "13_audit_chain")
    click(page, "[data-act=tamper]")
    wait(page, 4200)
    uncap(page)

    # ============================================================ 7. why it matters, second domain, tech stack
    page.evaluate("location.hash='#/demo'")
    page.wait_for_selector("#d-rogue .chip", timeout=20000)
    wait(page, 600)
    cap(page, "Why it matters: the same tempted agent with Anvil switched OFF", "Demo studio: enforcement off")
    click(page, "#enf")
    click(page, "#d-rogue [data-scn='Business-class upgrade']")
    page.wait_for_selector("#runsum:has-text('leaked')", timeout=120000)
    wait(page, 600)
    scroll_to(page, "#stagebox", "start")
    cap(page, "Booked with no check: the money leaks. Now Anvil ON, same request", "Leak counter")
    shot(page, "14_unprotected_leak")
    wait(page, 2400)
    click(page, "#enf")
    click(page, "#d-rogue [data-scn='Business-class upgrade']")
    lapse(page, lambda: page.wait_for_selector("#runsum:has-text('Run summary')", timeout=180000))
    wait(page, 1200)
    scroll_to(page, "#stagebox", "start")
    cap(page, "Blocked, with the reason; the agent corrects itself and the new booking is audited again before it is allowed", "Blocked, self-corrected, re-audited")
    shot(page, "15_protected_block")
    wait(page, 5200)
    uncap(page)

    page.evaluate("location.hash='#/quality'")
    page.wait_for_selector("#q-soft table", timeout=60000)
    scroll_to(page, "#q-soft", "start")
    cap(page, "Same engine, different domain: software purchases under a different policy. 8 of 8 violations caught. Any domain where agents spend can plug in", "Quality page: second domain")
    shot(page, "16_second_domain")
    wait(page, 6500)
    uncap(page)

    page.set_content(ARCH)
    wait(page, 1200)
    mark("TECH STACK: Firebase Hosting, Cloud Run (API + A2A supplier agents), Gemini 2.5 Flash on Vertex AI, Firestore, Secret Manager, AP2 SDK", "Architecture card, then the close")
    page.screenshot(path=os.path.join(SHOTS, "17_architecture.png"))
    wait(page, 9500)

    total = time.time() - T0
    video = page.video
    ctx.close()
    raw = video.path()
    browser.close()

webm = os.path.join(OUT, "anvil-demo-full.webm")
shutil.move(raw, webm)
shutil.rmtree(os.path.join(OUT, "raw"), ignore_errors=True)
mp4 = os.path.join(OUT, "anvil-demo.mp4")
TARGET = 15
cuts = [(a0, b0, (b0 - a0) / TARGET) for a0, b0 in waits if (b0 - a0) > TARGET + 4]


def newt(t):
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
    f.write("# Demo recording v2: timeline (use it to time your voice-over)\n\n| Time | On screen | What is happening |\n|---|---|---|\n")
    for t, text, note in timeline:
        t = newt(t)
        f.write(f"| {int(t // 60)}:{int(t % 60):02d} | {text} | {note} |\n")
    f.write(f"\nTotal length: {int(final_len // 60)}:{int(final_len % 60):02d}\n\nThe long Gemini waits are a labelled time-lapse; narrate over them.\n")
print(f"\nDone. Total length {int(final_len // 60)}:{int(final_len % 60):02d} (limit 4:00)")
print("VIDEO TO USE:", mp4, "\nFull-speed original:", webm, "\nTimeline:", os.path.join(OUT, "timeline.md"), "\nScreenshots:", SHOTS)
print("BLOCK SEEN IN THE EMPLOYEE FLOW:", "yes" if corrected else "NO: Gemini chose a compliant flight this time; run again for the block scene")
if final_len > 235:
    print("WARNING: longer than 3:55. Re-run with --speed 0.6 to shorten the pauses.")
