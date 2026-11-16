#!/usr/bin/env python3
"""나이스 초과근무(초근) 신청 → 승인요청(상신)까지.

복무 > 개인초과근무관리 > [신청] 의 «초과근무신청» 창에 날짜·시작·종료·하여야 할 일을 넣고
[승인요청] → 기안문서상신(개인결재선 지정 → 상신)까지 한다. 상신 과정은 main_bokmu.submit 을 그대로 쓴다
(뜨는 확인창 글자를 하나하나 맞춰 보고, 모르는 창이면 멈추고 사람에게 넘긴다).

    python main_chogun.py --date 2026-11-16 --start 16:30 --end 21:30 --work "생활기록부 작성" --dry-run
    python main_chogun.py --date 2026-11-16 --start 16:30 --end 21:30 --work "생활기록부 작성"
    python main_chogun.py --date 2026-11-16 --start 00:00 --end 00:05 --work - --list     (읽기만: 그 날짜 목록)

- 종별은 나이스 기본값 «시간외 근무» 그대로 둔다. 휴일·대체휴무·방과후수업차감은 건드리지 않는다
- 초과근무시간 합은 나이스가 계산한 값을 읽어 보여 준다 (저녁 시간 등을 나이스가 뺀다)
- 상신 뒤에는 목록을 다시 읽어 그 날짜·시각 줄과 신청 상태를 보여 준다
- 0 으로 끝나면 «상신하겠습니까? [확인]까지 눌렀다». 1 이면 «확인 필요» — 자동으로 다시 돌리지 않는다 (두 번 상신 방지)
마지막 줄: RESULT_JSON={...}
"""
import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date

from playwright.async_api import async_playwright, Page

import teacher_config
import main as neis
import main_bokmu as B

TEMP = os.environ.get("TEMP") or os.environ.get("TMP") or "."      # 화면 사진은 저장소 밖에 둔다

JS_READ_FORM = """(d) => {
  const out = {};
  d.querySelectorAll('input[aria-label], textarea[aria-label], [role=combobox][aria-label]').forEach(e => {
    if (!(e.offsetParent || e.getClientRects().length)) return;
    const k = e.getAttribute('aria-label');
    out[k] = (e.tagName === 'INPUT' || e.tagName === 'TEXTAREA') ? e.value : (e.innerText || '').trim();
  });
  return out;
}"""

JS_LIST_ROWS = """() => [...document.querySelectorAll('[role=row]')]
  .filter(r => r.offsetParent || r.getClientRects().length)
  .map(r => (r.innerText || '').replace(/\\s+/g, ' ').trim())
  .filter(t => /\\d{4}-\\d{2}-\\d{2}/.test(t))"""


def out(obj):
    print("RESULT_JSON=" + json.dumps(obj, ensure_ascii=False), flush=True)


def hm(s):
    if not re.fullmatch(r"\d{1,2}:\d{2}", s or ""):
        raise SystemExit("시각은 16:30 처럼 주세요: %r" % s)
    return B.round_to_step(s)


async def open_menu(page: Page):
    await B.click(page, page.locator("a").filter(has_text="복무 0단계 메뉴항목").first, timeout=8000)
    await page.wait_for_timeout(600)
    await B.click(page, page.locator("a").filter(has_text="개인초과근무관리 1단계").first, timeout=8000)
    await page.wait_for_timeout(1500)
    await B.wait_loading(page, 60)


async def open_apply(page: Page):
    btn = page.locator("[aria-label='신청(새 창 열기)']:visible, [title='신청(새 창 열기)']:visible").first
    await B.click(page, btn, timeout=8000)
    dlg = page.locator('[role="dialog"]').filter(has_text="초과근무신청목록").last
    await dlg.wait_for(state="visible", timeout=15_000)
    await page.wait_for_timeout(1500)
    await B.wait_loading(page, 60)
    return dlg


async def set_field(page: Page, dlg, label: str, value: str):
    """aria-label 이 label 인 칸에 값을 넣는다. 콤보박스면 열어서 고르고, 입력칸이면 지우고 친다."""
    combo = dlg.locator(f'[role="combobox"][aria-label^="{label}"]:visible').first
    if await combo.count():
        await B.select_combo_option(page, combo, value)
        return
    box = dlg.locator(f'input[aria-label="{label}"]:visible, textarea[aria-label="{label}"]:visible').first
    if not await box.count():
        raise RuntimeError(f"초과근무신청 창에서 «{label}» 칸을 못 찾았습니다")
    await B.click(page, box, timeout=5000)
    await box.press("Control+a")
    await box.press("Delete")
    await box.type(value, delay=40)
    await box.press("Tab")
    await page.wait_for_timeout(300)


async def fill(page: Page, dlg, d: str, start: str, end: str, work: str):
    sh, sm = start.split(":")
    eh, em = end.split(":")
    await set_field(page, dlg, "초과근무일자", d)
    await set_field(page, dlg, "신청시작시", sh)
    await set_field(page, dlg, "신청시작분", sm)
    await set_field(page, dlg, "신청종료시", eh)
    await set_field(page, dlg, "신청종료분", em)
    await set_field(page, dlg, "하여야 할 일", work)
    await page.wait_for_timeout(800)
    return await dlg.evaluate(JS_READ_FORM)


def check_form(form: dict, d: str, start: str, end: str, work: str):
    """채운 값을 다시 읽어 맞는지 본다. 하나라도 다르면 승인요청을 누르지 않는다."""
    want = {"초과근무일자": d, "신청시작시": start[:2], "신청시작분": start[3:], "신청종료시": end[:2],
            "신청종료분": end[3:], "하여야 할 일": work}
    bad = []
    for k, v in want.items():
        got = next((form[x] for x in form if x.startswith(k)), None)
        if got is None or str(got).strip().lstrip("0") != str(v).strip().lstrip("0"):
            bad.append(f"{k}: 넣으려던 값 {v!r} / 화면 {got!r}")
    total = "%s:%s" % (next((form[x] for x in form if x.startswith("초과근무시간 합 시")), "?"),
                       next((form[x] for x in form if x.startswith("초과근무시간 합 분")), "?"))
    return bad, total


async def read_list(page: Page, d: str):
    """목록 화면에서 [조회] 를 눌러 그 날짜 줄을 읽는다."""
    q = page.locator("[aria-label='조회']:visible, [title='조회']:visible").first
    if await q.count():
        await B.click(page, q, timeout=8000)
        await page.wait_for_timeout(2000)
        await B.wait_loading(page, 60)
    rows = await page.evaluate(JS_LIST_ROWS)
    return [r for r in rows if d in r]


async def run(a):
    neis.load_teacher_settings()
    cfg = teacher_config.load_config()
    line = a.approval_line or cfg.get("approval_line")
    if not a.dry_run and not line:
        out({"ok": False, "error": "개인결재선 이름이 없습니다 (--approval-line 또는 설정의 approval_line)"})
        return 1
    d = date.fromisoformat(a.date).isoformat()
    start, end = hm(a.start), hm(a.end)
    if start >= end:
        out({"ok": False, "error": "종료 시각이 시작 시각보다 늦어야 합니다"})
        return 1
    if not a.work.strip():
        out({"ok": False, "error": "하여야 할 일을 적어 주세요"})
        return 1

    port = int(os.environ.get("NEIS_CDP_PORT", "9222"))
    async with async_playwright() as p:
        browser = None
        if B._cdp_alive(port):
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            print(f"🔗  이미 떠 있는 나이스 크롬(포트 {port})에 붙습니다")
        ctx = browser.contexts[0] if browser else await p.chromium.launch_persistent_context(
            user_data_dir=str(teacher_config.CONFIG_DIR / "chrome_profile"), channel="chrome", headless=False, slow_mo=50,
            args=["--profile-directory=Default", "--disable-blink-features=AutomationControlled",
                  "--disable-features=PrivateNetworkAccessForNavigations,PrivateNetworkAccessPermissionPrompt,PermissionChip",
                  "--disable-web-security", "--allow-running-insecure-content", "--test-type", "--noerrdialogs",
                  *teacher_config.window_args()],
            ignore_default_args=["--enable-automation", "--no-sandbox"], viewport=None)
        page = await ctx.new_page() if browser else (ctx.pages[0] if ctx.pages else await ctx.new_page())
        code = 0
        try:
            await page.goto(neis.NEIS_URL)
            await neis.auto_login(page)
            await page.wait_for_selector("text=로그아웃", timeout=120_000)
            await page.wait_for_timeout(1000)
            print("✅  로그인 완료")
            await neis.dismiss_notice_popup(page, timeout=2000)

            await open_menu(page)
            if a.list_only:
                rows = await read_list(page, d)
                print("📋  목록에서 %s 줄: %d개" % (d, len(rows)))
                for r in rows[:10]:
                    print("     " + r[:160])
                out({"ok": True, "list": True, "date": d, "rows": rows[:10]})
                return 0
            dlg = await open_apply(page)
            print("✅  초과근무신청 창 열림")
            form = await fill(page, dlg, d, start, end, a.work.strip())
            bad, total = check_form(form, d, start, end, a.work.strip())
            await page.screenshot(path=os.path.join(TEMP, "chogun_form_filled.png"))
            print(f"🧾  채운 값: {d} {start}~{end} / 나이스 계산 시간 합 {total} / 하여야 할 일 «{a.work.strip()}»")
            if bad:
                print("⛔  화면 값이 넣으려던 값과 다릅니다 — 승인요청을 누르지 않습니다:\n   " + "\n   ".join(bad))
                out({"ok": False, "error": "화면 값 불일치: " + " / ".join(bad)[:200], "form": form})
                return 1
            if a.dry_run:
                print("🧪  --dry-run: 승인요청을 누르지 않았습니다 (저장 없이 닫습니다)")
                out({"ok": True, "dry": True, "date": d, "start": start, "end": end, "total": total})
                return 0

            ok = await B.submit(page, dlg, approval_line=line)
            if not ok:
                code = 1
                print("⚠️  자동 상신을 끝내지 못해 사람에게 넘겼습니다. 나이스 개인초과근무관리에서 꼭 확인하세요.")
            await page.wait_for_timeout(1500)
            rows = await read_list(page, d)
            mine = [r for r in rows if start in r and end in r]
            print("📋  목록에서 %s 줄: %d개" % (d, len(rows)))
            for r in rows[:5]:
                print("     " + r[:160])
            out({"ok": ok, "dry": False, "date": d, "start": start, "end": end, "total": total,
                 "rows": rows[:5], "found": bool(mine)})
        except Exception as e:
            head = [ln.strip() for ln in str(e).splitlines() if ln.strip()][:2]
            print("❌  멈춘 곳: " + " / ".join(head)[:300], flush=True)
            try:
                await page.screenshot(path=os.path.join(TEMP, "chogun_error.png"))
            except Exception:
                pass
            out({"ok": False, "error": " / ".join(head)[:300]})
            code = 1
        finally:
            await page.wait_for_timeout(3000)
            if browser:
                await page.close()          # 남의 크롬 — 내 탭만 닫는다 (채우다 만 신청 창도 저장 없이 사라진다)
            elif not a.dry_run:
                await ctx.close()
        return code


def main():
    ap = argparse.ArgumentParser(description="나이스 초과근무 신청·상신")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--start", required=True, help="HH:MM (5분 단위로 맞춘다)")
    ap.add_argument("--end", required=True, help="HH:MM")
    ap.add_argument("--work", required=True, help="하여야 할 일")
    ap.add_argument("--approval-line", default=None, help="개인결재선 이름 (없으면 설정의 approval_line)")
    ap.add_argument("--dry-run", action="store_true", help="채우기만 하고 승인요청은 누르지 않는다")
    ap.add_argument("--list", dest="list_only", action="store_true", help="읽기만: 그 날짜의 초과근무 목록 줄을 보여 준다")
    a = ap.parse_args()
    if a.list_only:
        a.dry_run = True
    sys.exit(asyncio.run(run(a)) or 0)


if __name__ == "__main__":
    main()
