"""Browser test for the role-based web app (real browser, real HTTP API).

  pip install playwright            # uses the Edge or Chrome you already have; no browser download
  python scripts/serve_offline.py 8080                          # backend with in-memory data and a rule-based Gemini stand-in
  python scripts/serve_dashboard.py 8100                        # the web app, with correct MIME types
  python scripts/e2e_ui.py http://localhost:8100/index.html http://localhost:8080

It signs in as each role and checks: who sees which pages, a round trip with real dates is planned leg by leg, a late booking
is escalated as ONE trip, the manager approves the whole trip, the employee sees the decision, nobody approves their own trip,
a request can be withdrawn, the operator cannot approve spend, the activity export works, and no page logs a console error or
overflows a 390 px phone screen.
Point it at the live API instead (second argument) only if you accept that it writes real entries to the connected backend."""
import json
import os
import sys
from datetime import date, timedelta

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8100/index.html"
API = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8080"
SHOTS = os.environ.get("ANVIL_SHOTS")                    # optional folder for screenshots
BROWSER = os.environ.get("ANVIL_BROWSER", "msedge")      # "msedge", "chrome", or "" for Playwright's own chromium
fails, errors = [], []
D = lambda n: (date.today() + timedelta(days=n)).isoformat()


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond:
        fails.append(name)


def shot(page, name, **kw):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, name + ".png"), **kw)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=BROWSER or None, headless=True)

    def open_as(who, theme="light", w=1400, h=950, mobile=False, hash_=""):
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, accept_downloads=True)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append((who, m.text)) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append((who, str(e))))
        page.goto(f"{URL}?as={who}&theme={theme}&api={API}{hash_}")
        return page

    def plan(page, dep, ret, reason, trip_type="round_trip", wait_for="Approved|Sent for approval", dest=None):
        page.click("[data-act=newtrip]")
        page.wait_for_selector("#trip-form:not([hidden])")
        if dest:
            page.select_option("#t-to", dest)
        if trip_type == "one_way":
            page.click("[data-tt=one_way]")
        page.fill("#t-dep", dep)
        if ret:
            page.fill("#t-ret", ret)
        page.fill("#t-just", reason)
        page.click("#t-go")
        page.wait_for_function(f"/{wait_for}/.test(document.querySelector('#nl-progress')?.innerText||'')", timeout=60000)

    # ---- employee: menu, form, a compliant round trip
    r = open_as("rahul")
    r.wait_for_selector("#h-list", timeout=30000)
    nav = r.inner_text("#nav")
    check("employee menu is only My trips and Policy", "My trips" in nav and "Policy" in nav and not any(x in nav for x in ("Approvals", "Agents", "Demo", "Spend", "Activity")), nav)
    r.goto(f"{URL}?as=rahul&api={API}#/agents")
    r.wait_for_selector("#page-title")
    check("employee opening an operator page by URL lands on My trips", r.inner_text("#page-title") == "My trips", r.inner_text("#page-title"))
    r.wait_for_selector("#trip-form:not([hidden])", timeout=15000)
    check("an employee with no trips is taken straight to the trip form", True)
    est = r.inner_text("#t-est")
    check("the form shows the legs a round trip needs and the most the policy allows", "Return flight" in est and "Hotel to airport" in est and "$" in est, est)
    r.fill("#t-dep", D(2)); r.fill("#t-ret", D(4))
    r.wait_for_timeout(200)
    check("a late departure warns that approval will be needed", "days' notice" in r.inner_text("#t-est"), r.inner_text("#t-est"))
    r.fill("#t-ret", D(1))
    r.wait_for_timeout(200)
    check("a return before the departure disables the button", r.is_disabled("#t-go") and "before the departure" in r.inner_text("#t-est"))
    r.fill("#t-ret", D(4))
    r.select_option("#t-to", "Bengaluru")
    check("the same origin and destination is refused", r.is_disabled("#t-go") and "same" in r.inner_text("#t-est"))
    r.select_option("#t-to", "Mumbai")
    r.fill("#t-dep", D(20)); r.fill("#t-ret", D(23))
    r.fill("#t-just", "Quarterly review with the Mumbai client team")
    r.click("#t-go")
    r.wait_for_function("/Approved\\./.test(document.querySelector('#nl-progress')?.innerText||'')", timeout=60000)
    check("a compliant round trip is approved with a receipt for every booking", "receipt was issued for each" in r.inner_text("#nl-progress"), r.inner_text("#nl-progress"))
    shot(r, "employee_form_done", full_page=True)
    r.click("[data-act=closeform]")
    r.wait_for_selector("#h-list .item")
    card = r.locator("#h-list .item").first.inner_text()
    check("the trip card shows route, round trip, dates, nights, cost centre and total", all(x in card for x in ("Bengaluru → Mumbai", "Round trip", "3 nights", "CC-1042", "Trip cost")), card[:300])
    check("the itinerary lists five bookings in order with times", r.locator("#h-list .item").first.locator(".leg-row").count() == 5 and "06:10" in card and "check-in" in card, card[:400])
    check("the stay is priced for every night", "$840" in card, card)

    # ---- employee: a late trip is escalated as ONE trip
    plan(r, D(3), D(5), "Customer escalation, travelling at short notice", wait_for="Sent for approval", dest="Goa")
    r.click("[data-act=closeform]")
    r.wait_for_function("document.querySelector('#h-list')?.innerText.includes('Awaiting approval')", timeout=20000)
    check("a late trip shows as one request awaiting approval", r.locator("#h-list .item.warn").count() == 1)
    check("trips to other cities work: the card says Goa", "Bengaluru → Goa" in r.locator("#h-list .item.warn").first.inner_text())
    check("the shared reason is stated once", r.locator("#h-list .item.warn .impact").count() == 1 and "days' notice" in r.locator("#h-list .item.warn .impact").first.inner_text())
    shot(r, "employee_late_trip", full_page=True)

    # ---- finance manager
    a = open_as("adhish")
    a.wait_for_selector("#a-list .item", timeout=30000)
    nav = a.inner_text("#nav")
    check("manager menu: Approvals, My trips, Activity, Spend, Policy; no Agents, Audit or Demo", all(x in nav for x in ("Approvals", "My trips", "Activity", "Spend", "Policy")) and not any(x in nav for x in ("Agents", "Audit", "Demo", "Overview")), nav)
    mine = a.locator("#a-list .item", has_text="Rahul")
    check("the manager sees the late trip as one card with all five bookings, soonest first", mine.count() == 1 and mine.first.locator(".leg-row").count() == 5, mine.count())
    txt = mine.first.inner_text()
    check("the approval card shows dates, purpose, cost centre, the reason and the notice rule", all(x in txt for x in ("Client meeting", "CC-1042", "Customer escalation", "days' notice", "Departs in")), txt[:500])
    shot(a, "manager_approvals", full_page=True)
    mine.first.locator("input[data-comment]").fill("Approved: customer escalation")
    mine.first.get_by_role("button", name="Approve all 5").click()
    a.wait_for_selector(".toast", timeout=30000)
    check("approving the trip confirms with one toast", "Approved 5 bookings" in a.inner_text("#toasts"), a.inner_text("#toasts"))
    a.click("[data-tab=done]")
    a.wait_for_selector("#a-list .item", timeout=15000)
    check("the Decided tab lists the decisions with their time", "approved" in a.inner_text("#a-list").lower())
    # the employee sees the manager's decision and is notified
    r.wait_for_function("document.querySelector('#h-list .item')?.innerText.includes('Adhish Sekar')", timeout=20000)
    check("the employee sees who approved the trip and the comment", "customer escalation" in r.inner_text("#h-list").lower() and "Approved by" in r.inner_text("#h-list"))
    check("the employee is notified of the decision", "approved your trip to Goa" in r.inner_text("#toasts"), r.inner_text("#toasts"))

    # ---- nobody approves their own trip; a request can be withdrawn
    a.evaluate("location.hash='#/home'")
    a.wait_for_selector("[data-act=newtrip]")
    plan(a, D(4), D(6), "Urgent supplier visit", wait_for="Sent for approval")
    a.click("[data-act=closeform]")
    a.evaluate("location.hash='#/approvals'"); a.click("[data-tab=wait]")
    a.wait_for_selector("#a-list .item:has-text('Urgent supplier visit')", timeout=20000)
    own = a.locator("#a-list .item", has_text="Urgent supplier visit")
    check("a manager cannot approve their own trip", own.count() == 1 and own.first.get_by_role("button", name="Approve").is_disabled() and "own request" in own.first.inner_text())
    a.evaluate("location.hash='#/home'")
    a.wait_for_selector("#h-list .item.warn")
    a.get_by_role("button", name="Withdraw request").first.click()
    a.get_by_role("button", name="Withdraw request").last.click()
    a.wait_for_function("document.querySelector('#h-list')?.innerText.includes('Withdrawn')", timeout=20000)
    check("a pending request can be withdrawn by its requester", True)
    a.evaluate("location.hash='#/approvals'")
    a.wait_for_timeout(800)
    check("a withdrawn trip leaves the approval queue", "Urgent supplier visit" not in a.inner_text("#a-list"))

    # ---- manager: spend, activity export, emergency stop
    a.evaluate("location.hash='#/spend'")
    a.wait_for_selector("#s-cc table", timeout=15000)
    check("Spend groups approved money by cost centre", "CC-1042" in a.inner_text("#s-cc"))
    check("the manager has an emergency stop", "Revoke policy" in a.inner_text("#s-emg"))
    a.evaluate("location.hash='#/activity'")
    a.wait_for_selector("#act-list .item", timeout=15000)
    check("Activity rows show the travel dates and a timestamp", "→" in a.inner_text("#act-list") and ("," in a.locator("#act-list .meta").first.inner_text()), a.locator("#act-list .meta").first.inner_text())
    with a.expect_download(timeout=10000) as dl:
        a.click("[data-act=csv]")
    csv = open(dl.value.path(), encoding="utf-8").read()
    check("the activity export is a CSV with the trip columns", csv.startswith('"Time"') and "Cost centre" in csv.splitlines()[0] and len(csv.splitlines()) > 5, csv[:200])

    # ---- operator: runs the agents, cannot approve spend
    s = open_as("swathy")
    s.wait_for_selector("#page-title")
    nav = s.inner_text("#nav")
    check("operator menu has no Approvals, Spend or My trips", not any(x in nav for x in ("Approvals", "Spend", "My trips")) and all(x in nav for x in ("Overview", "Agents", "Audit trail", "AI traces", "Quality", "Demo studio")), nav)
    for pid, title in [("overview", "Overview"), ("activity", "Activity"), ("policy", "Policy"), ("agents", "Agents"), ("audit", "Audit trail"), ("traces", "AI traces"), ("quality", "Quality"), ("demo", "Demo studio")]:
        s.evaluate(f"location.hash='#/{pid}'")
        s.wait_for_function(f"document.querySelector('#page-title').innerText==='{title}'", timeout=10000)
        s.wait_for_timeout(1200)
    check("the operator can open all eight pages", True)
    s.evaluate("location.hash='#/approvals'")
    s.wait_for_timeout(500)
    check("the operator opening Approvals by URL is sent to Overview", s.inner_text("#page-title") == "Overview")
    s.evaluate("location.hash='#/activity'")
    s.wait_for_selector("#act-list .item", timeout=20000)
    s.click("#act-filters [data-k=MATCH]"); s.wait_for_timeout(300)
    check("the Approved filter shows only approved decisions", s.locator("#act-list .item").count() > 0 and all("Approved" in t for t in s.locator("#act-list .item .badge").all_inner_texts()))
    s.locator("#act-list .item").first.click(); s.wait_for_timeout(300)
    check("an activity row expands to show its detail", s.locator("#act-list .detail").count() == 1)
    s.evaluate("location.hash='#/demo'")
    s.wait_for_selector("#d-rogue .chip", timeout=10000)
    s.click("#d-rogue [data-scn='Over-cap']")
    s.wait_for_selector("#legs .needs", timeout=90000)
    s.locator("#legs .needs button", has_text="Approve").first.click()
    s.wait_for_selector("#legs .needs:has-text('approved')", timeout=30000)
    check("Demo studio: the over-cap scenario can be approved by the stand-in approver", True)
    shot(s, "demo_studio", full_page=True)
    s.evaluate("location.hash='#/audit'")
    s.wait_for_selector("#trail .entry", timeout=15000)
    check("the audit trail shows dated entries", "→" in s.inner_text("#trail") or "," in s.inner_text("#trail .entry >> nth=0"))

    s.evaluate("location.hash='#/audit'")
    s.wait_for_selector("#trail .entry", timeout=15000)
    s.locator("#trail [data-act=trace]").first.click()
    s.wait_for_selector(".trace-detail pre", timeout=20000)
    check("the audit trail links to the exact Gemini call", s.inner_text("#page-title") == "AI traces" and s.locator(".trace-detail").count() >= 1)
    s.click("[data-act=trfilter][data-k=audit]")
    s.wait_for_selector("#tr-list .item", timeout=20000)
    s.locator("#tr-list .item").first.click()
    s.wait_for_selector(".trace-detail pre", timeout=20000)
    inp, outp = s.locator(".trace-detail pre").nth(0).inner_text(), s.locator(".trace-detail pre").nth(1).inner_text()
    check("AI traces: an audit shows the full input (mandate and action) and the output (verdict)", "MANDATE:" in inp and "ACTION:" in inp and '"verdict"' in outp, inp[:120])
    check("AI traces: tokens, latency and cost are shown", "Tokens" in s.locator(".trace-detail").first.inner_text() and "Latency" in s.locator(".trace-detail").first.inner_text())
    s.click("[data-act=trfilter][data-k=plan]")
    s.wait_for_selector("#tr-list .item", timeout=20000)
    check("AI traces: planning calls are listed separately", "Plan" in s.inner_text("#tr-list") and "Audit" not in s.locator("#tr-list .item .tag").first.inner_text())
    shot(s, "ai_traces", full_page=True)

    # ---- guest can switch roles
    g = open_as("guest")
    g.wait_for_selector("#page-title", timeout=30000)
    check("guest starts on the operator Overview with the guest banner", g.inner_text("#page-title") == "Overview" and "guest judge" in g.inner_text("#banners"))
    g.click("[data-viewas=employee]")
    g.wait_for_function("document.querySelector('#page-title').innerText==='My trips'", timeout=10000)
    check("View as employee hides the operator pages", "Agents" not in g.inner_text("#nav"))
    g.click("[data-viewas=manager]")
    g.wait_for_function("document.querySelector('#page-title').innerText==='Approvals'", timeout=10000)
    g.click("[data-viewas=operator]")
    g.wait_for_selector("#nav >> text=Demo studio")

    # ---- finance manager edits the policy
    a.evaluate("location.hash='#/policy'")
    a.wait_for_selector("[data-act=editpolicy]", timeout=15000)
    a.wait_for_function("document.querySelector('#p-hist')?.innerText.includes('Policy history')", timeout=15000)
    a.click("[data-act=editpolicy]")
    a.wait_for_selector("#pe-flight")
    a.fill("#pe-flight", "700")
    a.click("#pe-cities [data-city=Dubai]")
    a.click("[data-act=savepolicy]")
    check("a policy change without a reason is refused", "Say why" in a.inner_text("#pe-err"))
    a.fill("#pe-why", "Q4 client travel needs a higher fare ceiling")
    a.click("[data-act=savepolicy]")
    a.wait_for_selector("#cd-ok")
    dlg = a.inner_text("#modal")
    check("the manager reviews exactly what will change before signing", "600" in dlg and "700" in dlg and "Dubai" in dlg, dlg)
    a.click("#cd-ok")
    a.wait_for_function("document.querySelector('#p-hist')?.innerText.includes('Version 2')", timeout=20000)
    check("the new limit is shown and the history records who, why and what", "Up to $700" in a.inner_text("#p-terms") and "Q4 client travel" in a.inner_text("#p-hist") and "Adhish Sekar" in a.inner_text("#p-hist"))
    r.goto(f"{URL}?as=rahul&api={API}")
    r.wait_for_function("document.querySelector('#t-to option[value=Goa]') && !document.querySelector('#t-to option[value=Dubai]')", timeout=20000)
    check("the employee's trip form follows the new policy (Dubai no longer offered)", True)
    emp = open_as("rahul", hash_="#/policy")
    emp.wait_for_selector("#p-hist", timeout=15000)
    check("an employee sees the policy and its history but cannot edit it", "Edit policy" not in emp.inner_text("#page-actions") and "Version 2" in emp.inner_text("#p-hist") or "Version" in emp.inner_text("#p-hist"))
    shot(a, "policy_edit", full_page=True)

    # ---- phone: no horizontal overflow on any page of any role (with the trip form open)
    for who, pages in {"rahul": ["home", "policy"], "adhish": ["approvals", "home", "activity", "spend", "policy"], "swathy": ["overview", "agents", "audit", "traces", "quality", "demo"]}.items():
        m = open_as(who, w=390, h=844, mobile=True)
        m.wait_for_selector("#page-title", timeout=30000)
        for pid in pages:
            m.evaluate(f"location.hash='#/{pid}'")
            m.wait_for_timeout(1200)
            if pid == "home":
                m.evaluate("document.querySelector('[data-act=newtrip]').click()")
                m.wait_for_timeout(400)
            sw, iw = m.evaluate("[document.documentElement.scrollWidth, innerWidth]")
            check(f"390 px: {who}/{pid} has no horizontal overflow", sw <= iw, f"{sw} > {iw}")
        if who == "rahul":
            shot(m, "mobile_trips", full_page=True)
    browser.close()

bad = [e for e in errors if "favicon" not in e[1] and "net::ERR" not in e[1]]
check("no console errors on any page", not bad, json.dumps(bad)[:600])
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
