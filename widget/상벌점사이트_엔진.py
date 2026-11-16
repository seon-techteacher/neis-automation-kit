# -*- coding: utf-8 -*-
"""위젯 [상벌점] 단추 — 학교 상벌점 사이트(아이디·비밀번호 로그인)를 전용 크롬으로 열고 로그인해 맨 앞에 띄운다.
(e알리미용 상벌점_엔진.py 와는 다른 것 — 그건 바로가기위젯_상벌점.pyw 가 쓴다)

  .\\.venv\\Scripts\\python.exe -X utf8 widget\\상벌점사이트_엔진.py

주소·아이디는 설정 파일(green_url · green_id), 비밀번호는 자격 증명 관리자(neis-automation-green)에서 읽는다.
크롬 띄우기·붙기·앞으로 꺼내기는 바로가기_엔진.py 의 것을 그대로 쓴다.
위젯이 읽는 줄: STEP … / READY / FAIL 이유 (비밀번호는 어디에도 찍지 않는다)
"""
import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("widget_engine", HERE / "바로가기_엔진.py")
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)

SERVICE = "neis-automation-green"
PORT = 9326
LOGIN_CLICK = "input[type=button][onclick*='check_submit'], input[type=submit], button[type=submit]"


def cfg():
    try:
        data = json.loads(W.teacher_config.CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    url, uid = data.get("green_url"), data.get("green_id")
    if not url or not uid:
        raise RuntimeError("상벌점 설정이 없어요 — 오른쪽 클릭 → «상벌점 설정»")
    import keyring
    pw = keyring.get_password(SERVICE, uid)
    if not pw:
        raise RuntimeError("상벌점 비밀번호가 저장돼 있지 않아요 — 오른쪽 클릭 → «상벌점 설정»")
    return url, uid, pw


def has_password_box(page):
    try:
        loc = page.locator("input[type=password]")
        return loc.count() > 0 and loc.first.is_visible()
    except Exception:
        return False           # 페이지를 옮기는 중


def run():
    url, uid, pw = cfg()
    host = urlsplit(url).netloc
    W.SITES["green"] = {"port": PORT, "profile": W.BASE / "chrome_profile_widget_green", "match": (host,)}
    W.ensure_chrome("green")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = W.connect_sync(p, PORT)
        ctx = b.contexts[0]
        page = W.pick_page(ctx, "green") or ctx.new_page()
        alerts = []

        def on_dialog(d):
            alerts.append(d.message)
            try:
                d.accept()
            except Exception:
                pass
        page.on("dialog", on_dialog)

        if host not in page.url:
            W.step("상벌점 여는 중")
            page.goto(url, wait_until="domcontentloaded", timeout=20_000)
            page.wait_for_timeout(500)

        if has_password_box(page):
            W.step("로그인 중")
            try:
                page.locator("input[name=id]").first.fill(uid)
                page.locator("input[type=password]").first.fill(pw)
            except Exception:
                # playwright 의 fill 오류 메시지에는 넣으려던 값이 들어간다 — 원문을 찍지 않는다
                raise RuntimeError("아이디·비밀번호 칸에 글자를 넣지 못했어요") from None
            page.locator(LOGIN_CLICK).first.click()
            for _ in range(40):              # 최대 12초
                page.wait_for_timeout(300)
                if not has_password_box(page):
                    break
            page.wait_for_timeout(500)
            if has_password_box(page):
                why = ("사이트 안내: " + alerts[-1].strip()[:60]) if alerts else "로그인 화면 그대로예요"
                raise RuntimeError(why + " — 아이디·비밀번호가 맞는지 «상벌점 설정»에서 다시 넣어 주세요")
        else:
            W.step("이미 로그인돼 있음")
        W.to_front_sync(page)
    print("READY", flush=True)


def main():
    W.watchdog(120)
    try:
        run()
    except BaseException as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:140]
        print("FAIL " + msg, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
