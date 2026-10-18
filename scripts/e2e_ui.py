"""Browser test for the role-based web app (real browser, real API, real Firestore).

  pip install playwright            # uses the Edge or Chrome you already have; no browser download
  python scripts/serve_dashboard.py 8100                       # serves dashboard/public with correct MIME types
  python scripts/e2e_ui.py http://localhost:8100/index.html    # or the deployed / preview URL

It signs in as each role and checks: who sees which pages, an over-cap request is escalated, the manager approves it
with a comment, the employee sees the decision, the guest can switch roles, every operator page opens, and that no
page logs a console error or overflows a 390 px phone screen.
WARNING: it writes real entries to the connected backend (one escalated request that it then approves, plus one
Demo-studio scenario that it leaves waiting in the approval queue). Use "Start a new session" on the Audit page afterwards."""
import json
import os
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8100/index.html"
SHOTS = os.environ.get("ANVIL_SHOTS")                    # optional folder for screenshots
BROWSER = os.environ.get("ANVIL_BROWSER", "msedge")      # "msedge", "chrome", or "" for Playwright's own chromium
fails, errors = [], []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond:
        fails.append(name)


def shot(page, name, **kw):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, name + ".png"), **kw)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=BROWSER or None, headless=True)

    def open_as(who, theme="light", w=1400, h=950, mobile=False):
        ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
        page = ctx.new_page()
        page.on("console", lambda m: errors.append((who, m.text)) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append((who, str(e))))
        page.goto(f"{URL}?as={who}&theme={theme}")
        return page

    # ---- employee
    r = open_as("rahul")
    r.wait_for_selector("#h-list .item, #h-list .empty", timeout=30000)
    nav = r.inner_text("#nav")
    check("employee menu is only My requests and Policy", "My requests" in nav and "Policy" in nav and not any(x in nav for x in ("Approvals", "Agents", "Demo")), nav)
    r.goto(f"{URL}?as=rahul#/agents")
    r.wait_for_selector("#page-title")
    check("employee opening an operator page by URL lands on My requests", r.inner_text("#page-title") == "My requests", r.inner_text("#page-title"))
    r.click("[data-rq=buy]")
    r.select_option("#f-example", "over")
    r.fill("#f-note", "QA: automated UI test")
    r.click("#f-submit")
    r.wait_for_selector("#f-result .res", timeout=60000)
    check("an over-cap purchase is escalated to a manager", "Sent to a finance manager" in r.inner_text("#f-result"), r.inner_text("#f-result"))
    r.wait_for_function("document.querySelector('#h-list')?.innerText.includes('Awaiting approval')", timeout=20000)
    check("the request shows as Awaiting approval", True)
    shot(r, "employee_result")

    # ---- finance manager
    a = open_as("adhish")
    a.wait_for_selector("#a-list .item", timeout=30000)
    nav = a.inner_text("#nav")
    check("manager menu has Approvals, Activity and Spend but no Agents, Audit or Demo", all(x in nav for x in ("Approvals", "Activity", "Spend")) and not any(x in nav for x in ("Agents", "Audit", "Demo")), nav)
    mine = a.locator("#a-list .item", has_text="Rahul")
    check("manager sees the employee's request in the queue", mine.count() >= 1)
    mine.first.locator("input[data-comment]").fill("QA approved")
    mine.first.get_by_role("button", name="Approve and issue receipt").click()
    a.wait_for_selector(".toast", timeout=30000)
    check("approving confirms with a toast", "Approved" in a.inner_text("#toasts"), a.inner_text("#toasts"))
    a.click("[data-tab=done]")
    a.wait_for_selector("#a-list .item", timeout=15000)
    check("the Decided tab lists the decision", "approved" in a.inner_text("#a-list").lower())
    shot(a, "manager_decided")

    # ---- the employee sees it live
    r.goto(f"{URL}?as=rahul&theme=light#/home")
    r.wait_for_selector("#h-list .item", timeout=30000)
    check("the employee sees the decision on their own request", "Approved" in r.inner_text("#h-list .item >> nth=0"), r.inner_text("#h-list .item >> nth=0"))

    # ---- guest can switch roles
    g = open_as("guest")
    g.wait_for_selector("#page-title", timeout=30000)
    check("guest starts on the operator Overview with the guest banner", g.inner_text("#page-title") == "Overview" and "guest judge" in g.inner_text("#banners"))
    g.click("[data-viewas=employee]")
    g.wait_for_function("document.querySelector('#page-title').innerText==='My requests'", timeout=10000)
    check("View as employee hides the operator pages", "Agents" not in g.inner_text("#nav"))
    g.click("[data-viewas=manager]")
    g.wait_for_function("document.querySelector('#page-title').innerText==='Approvals'", timeout=10000)
    g.click("[data-viewas=operator]")
    g.wait_for_selector("text=Demo studio")

    # ---- operator: every page, filters, details, demo studio
    s = open_as("swathy")
    s.wait_for_selector("#page-title")
    for pid, title in [("overview", "Overview"), ("approvals", "Approvals"), ("home", "My requests"), ("activity", "Activity"), ("policy", "Policy"),
                       ("agents", "Agents"), ("audit", "Audit trail"), ("quality", "Quality"), ("demo", "Demo studio")]:
        s.evaluate(f"location.hash='#/{pid}'")
        s.wait_for_function(f"document.querySelector('#page-title').innerText==='{title}'", timeout=10000)
        s.wait_for_timeout(1500)
    check("the operator can open all nine pages", True)
    s.evaluate("location.hash='#/activity'")
    s.wait_for_selector("#act-list .item", timeout=20000)
    s.click("#act-filters [data-k=DRIFT]")
    s.wait_for_timeout(300)
    check("the Blocked filter shows only blocked decisions", s.locator("#act-list .item").count() > 0 and all("Blocked" in t for t in s.locator("#act-list .item .aside").all_inner_texts()))
    s.locator("#act-list .item").first.click()
    s.wait_for_timeout(300)
    check("an activity row expands to show its detail", s.locator("#act-list .detail").count() == 1)
    s.evaluate("location.hash='#/demo'")
    s.wait_for_selector("#d-rogue .chip", timeout=10000)
    s.click("#d-rogue [data-scn='Over-cap']")
    s.wait_for_selector("#legs .needs", timeout=90000)
    check("Demo studio: the over-cap scenario produces an approval card", True)
    shot(s, "demo_studio", full_page=True)

    # ---- phone: no horizontal overflow on any page of any role
    for who, pages in {"rahul": ["home", "policy"], "adhish": ["approvals", "activity", "spend"], "swathy": ["overview", "agents", "audit", "quality", "demo"]}.items():
        m = open_as(who, w=390, h=844, mobile=True)
        m.wait_for_selector("#page-title", timeout=30000)
        for pid in pages:
            m.evaluate(f"location.hash='#/{pid}'")
            m.wait_for_timeout(1500)
            sw, iw = m.evaluate("[document.documentElement.scrollWidth, innerWidth]")
            check(f"390 px: {who}/{pid} has no horizontal overflow", sw <= iw, f"{sw} > {iw}")
    browser.close()

bad = [e for e in errors if "favicon" not in e[1] and "net::ERR" not in e[1]]
check("no console errors on any page", not bad, json.dumps(bad)[:600])
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED: {fails}")
sys.exit(1 if fails else 0)
