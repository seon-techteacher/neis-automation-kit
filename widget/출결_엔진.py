# -*- coding: utf-8 -*-
"""출결판 엔진 — 내 구글 캘린더(읽기만)의 출결을 나이스 일일출결관리(담임용)에 넣는다.

★ 이 프로그램은 AI(클로드 등)에 연결하지 않는다. 접속하는 곳은 구글(로그인·캘린더 읽기)과 나이스뿐이다.
★ 학생 정보는 이 PC 밖으로 나가지 않는다. 기록 파일(출결\\기록.log)에는 «번호»만 남는다.
★ 일정의 «설명(메모)» 칸은 읽지 않는다 — 제목(번호 이름 (교시))과 캘린더 이름(분류)만 쓴다.
★ 일마감·월마감은 하지 않는다 — 마감은 선생님이 나이스에서 직접 한다.

위젯(바로가기위젯_출결.pyw)이 이 파일을 부른다. 줄 머리로 위젯과 이야기한다:
  STEP <지금 하는 일>   READY <끝 — 요약>   FAIL <안 됨 — 이유>
  PLAN <json>  미리보기 목록 (이름 포함 — 화면에만 쓰고 파일에 남기지 않는다)
  RESULT <json> 입력 결과
  ★ STEP/READY/FAIL 줄에는 학생 이름을 넣지 않는다 (위젯이 widget.log 에 남기는 줄이다).

  python 출결_엔진.py auth --client <내려받은 OAuth json>   구글 연결 (브라우저에서 «허용» 한 번)
  python 출결_엔진.py check                                구글 연결이 살아 있는지
  python 출결_엔진.py run --start 2026-11-01 --end 2026-11-20 [--dry-run]
      --dry-run : 미리보기(PLAN)까지 하고 끝낸다. 나이스에 아무것도 넣지 않는다.
      없으면   : PLAN 을 내보낸 뒤 표준입력에서 GO / CANCEL 한 줄을 기다린다.
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import teacher_config  # noqa: E402  (stdout 을 UTF-8 로)

DATA = Path(os.environ.get("CHULGYEOL_DATA") or (teacher_config.CONFIG_DIR / "출결"))
CLIENT = DATA / "client.json"
TOKEN = DATA / "token.json"
RECORD = DATA / "기록.log"
PROFILE = DATA / ("chrome_tmp_%d" % os.getpid())   # 한 번 쓰고 지우는 크롬 프로필 (캐시·쿠키가 남지 않게)
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
KST = timezone(timedelta(hours=9))

# 캘린더 이름 = 분류 (출결관리 배포판과 같은 9개)
CALENDARS = ["질병결석", "질병지각", "질병조퇴", "미인정결석", "미인정지각", "미인정조퇴",
             "출석인정결석", "출석인정지각", "출석인정조퇴"]
KIND = {n: (n[:-2], n[-2:]) for n in CALENDARS}       # "질병조퇴" → ("질병", "조퇴")

RELOGIN = ("구글 연결이 끊겼어요 (보통 7일마다 끊긴다면 구글 클라우드의 앱이 «테스트» 상태라서예요 — "
           "설명서의 «앱 게시» 단계를 해 주세요). 위젯 오른쪽 클릭 → «출결 구글 연결»을 다시 해 주세요.")


OUT = sys.stdout      # 위젯과 이야기하는 줄은 여기로만. 나머지 print(키트 main.py 의 진행 글 — 이름이 섞임)는 버린다


def say(tag, text=""):
    OUT.write(("%s %s" % (tag, text)).rstrip() + chr(10))
    OUT.flush()


def today():
    return datetime.now(KST).date()


def debug(*a):
    if os.environ.get("CHULGYEOL_DEBUG"):
        print(*a, file=sys.stderr, flush=True)


# ─────────────────────────── 접속 기록 (시험용: CHULGYEOL_NETLOG=파일) ───────────────────────────
NETLOG = os.environ.get("CHULGYEOL_NETLOG")
if NETLOG:
    import socket
    _orig = socket.getaddrinfo

    def _logged(host, *a, **k):
        try:
            with open(NETLOG, "a", encoding="utf-8") as f:
                f.write("python\t%s\t%s\n" % (datetime.now().strftime("%H:%M:%S"), host))
        except Exception:
            pass
        return _orig(host, *a, **k)
    socket.getaddrinfo = _logged


# ─────────────────────────── 기록 파일 (번호만) ───────────────────────────
def record(line):
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        old = RECORD.read_text(encoding="utf-8").splitlines()[-2000:] if RECORD.exists() else []
        RECORD.write_text("\n".join(old + ["%s  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), line)]) + "\n",
                          encoding="utf-8")
    except Exception:
        pass


# ─────────────────────────── 구글 ───────────────────────────
def creds(interactive=False):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google.auth.exceptions import RefreshError
    if not TOKEN.exists():
        raise PermissionError("아직 구글에 연결하지 않았어요. 위젯 오른쪽 클릭 → «출결 구글 연결»부터 해 주세요.")
    c = Credentials.from_authorized_user_file(str(TOKEN))   # 토큰에 적힌 권한 그대로 (좁혀서 갱신하면 invalid_scope)
    if not c.valid:
        if not c.refresh_token:
            raise PermissionError(RELOGIN)
        try:
            c.refresh(Request())
        except RefreshError:
            raise PermissionError(RELOGIN)
        TOKEN.write_text(c.to_json(), encoding="utf-8")
    return c


def service():
    from googleapiclient.discovery import build
    return build("calendar", "v3", credentials=creds(), cache_discovery=False)


def find_calendars(svc):
    """«내가 주인인» 캘린더 중 이름이 분류 9개와 같은 것 → {분류: [캘린더 id…]}
    남이 공유해 준 캘린더(다른 선생님 반)는 이름이 같아도 쓰지 않는다. 캘린더 하나 = 이름 하나(내가 붙인 이름 우선)."""
    found, token = {}, None
    while True:
        r = svc.calendarList().list(pageToken=token, minAccessRole="owner").execute()
        for it in r.get("items", []):
            nm = (it.get("summaryOverride") or it.get("summary") or "").strip()
            if nm in KIND and it["id"] not in found.setdefault(nm, []):
                found[nm].append(it["id"])
        token = r.get("nextPageToken")
        if not token:
            return found


TITLE = re.compile(r"^\s*(\d{1,3})\s+(\S+)")
BRACKET = re.compile(r"[(（]([^)）]*)[)）]")


def parse_title(title):
    """«15 홍길동 (4교시~)» → (15, '홍길동', '4교시~'). 형식이 아니면 None.
    괄호는 어디에 있어도 된다(배포판 앱스스크립트와 같게). 이름 뒤에 다른 글자가 붙으면 그 글자는 버린다."""
    m_b = BRACKET.search(title or "")
    detail = m_b.group(1).strip() if m_b else ""
    rest = BRACKET.sub(" ", title or "")
    m = TITLE.match(rest)
    if not m:
        return None
    return int(m.group(1)), m.group(2), detail


def read_events(svc, start, end):
    cals = find_calendars(svc)
    tmin = datetime.combine(start, datetime.min.time(), KST).isoformat()
    tmax = datetime.combine(end + timedelta(days=1), datetime.min.time(), KST).isoformat()
    recs, skipped = [], 0
    for kind, ids in cals.items():
        for cid in ids:
            token = None
            while True:
                # fields 로 «제목·날짜»만 받는다 — 설명(메모)·참석자·위치는 아예 내려받지 않는다
                r = svc.events().list(calendarId=cid, timeMin=tmin, timeMax=tmax, singleEvents=True,
                                      orderBy="startTime", pageToken=token, maxResults=250,
                                      fields="nextPageToken,items(summary,start,end,status)").execute()
                for ev in r.get("items", []):
                    if ev.get("status") == "cancelled":
                        continue
                    p = parse_title(ev.get("summary", ""))
                    if not p:
                        skipped += 1
                        continue
                    s, e = ev["start"], ev["end"]
                    if "date" in s:
                        d0, d1 = date.fromisoformat(s["date"]), date.fromisoformat(e["date"]) - timedelta(days=1)
                    else:
                        d0 = datetime.fromisoformat(s["dateTime"]).astimezone(KST).date()
                        d1 = (datetime.fromisoformat(e["dateTime"]) - timedelta(seconds=1)).astimezone(KST).date()
                        d1 = max(d0, d1)
                    recs.append({"number": str(p[0]), "name": p[1], "note": p[2], "label": kind, "d0": d0, "d1": d1})
                token = r.get("nextPageToken")
                if not token:
                    break
    return cals, recs, skipped


def expand(recs, start, end):
    """날짜별 할 일. 주말·기간 밖·오늘 이후는 뺀다. 같은 날·같은 학생·같은 분류는 하나로."""
    import main as M
    M.parse_gyosi_num = parse_gyosi      # 키트의 중복·정렬 함수도 엄격한 교시 읽기를 쓰게
    out = {}
    for r in recs:
        d = max(r["d0"], start)
        while d <= min(r["d1"], end, today()):
            if d.weekday() < 5:
                g, j = KIND[r["label"]]
                t = {"number": r["number"], "name": r["name"], "gubun": g, "jongryu": j,
                     "note": r["note"], "label": r["label"]}
                day = out.setdefault(d, [])
                dup = next((i for i, x in enumerate(day) if x["number"] == t["number"] and x["label"] == t["label"]), None)
                if dup is None:
                    day.append(t)
                else:
                    day[dup] = M._pick_duplicate(day[dup], t, d)
            d += timedelta(days=1)
    for d, day in out.items():
        # 한 학생이 같은 날 분류 두 개 이상(지각+조퇴 포함)이면 넣지 않고 «확인 필요»로 돌린다.
        # 나이스 «마감» 칸은 하나라 나중 것만 남는다 — 11/4 실제 입력에서 지각+조퇴가 «미인정지각» 하나로 보였다 (사용자 11/20)
        by = {}
        for t in day:
            by.setdefault(t["number"], []).append(t)
        for ts in by.values():
            if len(ts) > 1:
                for t in ts:
                    t["conflict"] = "both"
                    t["both"] = "·".join(x["label"] for x in ts)
        day.sort(key=M._missed_periods)
    return dict(sorted(out.items()))


def school_offdays(start, end):
    """우리 학교 휴업일·공휴일 {date: 이름} — 나이스 학사일정 공개 API(open.neis.go.kr, 키 없이).
    학교를 아직 안 골랐으면 None. 조회가 안 되면 None (휴업일 확인 없이 진행 — 기록엔 오류 종류만)."""
    try:
        cfg = json.loads(teacher_config.CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None
    office, code = cfg.get("school_office"), cfg.get("school_code")
    if not (office and code):
        return None
    import school_calendar as SC
    from concurrent.futures import ThreadPoolExecutor
    last = min(end, today())
    days = [start + timedelta(days=i) for i in range((last - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]

    def one(d):      # 키 없이는 한 번에 5줄까지라 «하루씩» 묻는다 (school_calendar.py 참고)
        rows = SC._get("SchoolSchedule", ATPT_OFCDC_SC_CODE=office, SD_SCHUL_CODE=code, AA_YMD=d.strftime("%Y%m%d"))
        off = [r for r in rows if r.get("SBTR_DD_SC_NM") in ("휴업일", "공휴일")]
        return d, ((off[0].get("EVENT_NM") or "").strip() or "휴업일") if off else None
    try:
        with ThreadPoolExecutor(6) as ex:
            return {d: label for d, label in ex.map(one, days) if label}
    except Exception as e:
        record("학사일정 조회 안 됨 (%s) — 휴업일 확인 없이 진행" % type(e).__name__)
        return None


PERIOD_OK = re.compile(r"^(조회|\d{1,2}|교시|~|-|,|·|부터|까지|\s)+$")


def parse_gyosi(note, jongryu=""):
    """괄호 속 교시 글을 «정해진 모양»일 때만 읽는다. 아니면 None (= 넣지 않음).
    된다: 4교시~ · ~2교시 · 조회 · 2,3교시 · 5~6교시 · 조회~2교시 · 3교시부터 · 2교시까지
    안 된다: 병원 2회 · 오후 · 4시  (예전 키트는 아무 숫자나 집어 «2회»를 2교시로 읽었다 — 코덱스 검토)"""
    note = (note or "").strip()
    if not note or not PERIOD_OK.match(note):
        return None
    toks = [0 if x == "조회" else int(x) for x in re.findall(r"조회|\d{1,2}", note)]
    if not toks or any(x > 10 for x in toks):
        return None
    return toks[-1] if jongryu == "지각" else toks[0]


# ─────────────────────────── 나이스 ───────────────────────────
def setup_neis_globals():
    import keyring
    import main as M
    cfg = teacher_config.load_config() if teacher_config.CONFIG_FILE.exists() else None
    if not cfg or not cfg.get("cert_name"):
        raise PermissionError("인증서 설정이 없어요. 위젯 오른쪽 클릭 → «인증서 설정»부터 해 주세요.")
    pw = keyring.get_password(teacher_config.KEYRING_SERVICE, cfg["cert_name"])
    if not pw:
        raise PermissionError("인증서 암호가 저장돼 있지 않아요. 위젯 오른쪽 클릭 → «인증서 설정»에서 다시 넣어 주세요.")
    M.NEIS_URL, M.CERT_NAME, M.CERT_PASSWORD = cfg["neis_url"], cfg["cert_name"], pw
    M.LAST_PERIOD = int(cfg.get("last_period", 7))
    M.parse_gyosi_num = parse_gyosi
    M.pick_student_row = pick_row
    return M


def gyosi_text(t):
    import main as M
    if t["jongryu"] == "결석":
        return "하루"
    g = parse_gyosi(t["note"], t["jongryu"])
    if g is None:
        return ""
    if g == 0:
        return "조회"
    return "%d교시" % g + ("부터" if t["jongryu"] == "조퇴" else "까지")


def clear_profiles():
    """지난번에 못 지운 크롬 임시 프로필까지 지운다 (전원이 꺼졌거나 강제로 끝난 경우)."""
    for d in DATA.glob("chrome_tmp_*"):
        shutil.rmtree(d, ignore_errors=True)


async def open_neis(p, hold, netlog_file=None):
    """hold["ctx"] 에 크롬을 먼저 담아 둔다 — 로그인 중에 실패해도 run() 이 닫고 지울 수 있게."""
    M = setup_neis_globals()
    clear_profiles()
    (PROFILE / "Default").mkdir(parents=True, exist_ok=True)
    # 새 프로필의 크롬이 처음 켜질 때 구글에 묻는 것들(세이프 브라우징 목록·비밀번호 관리자·검색 추천·로그인)을 미리 끈다
    (PROFILE / "Default" / "Preferences").write_text(json.dumps({
        "safebrowsing": {"enabled": False}, "credentials_enable_service": False,
        "profile": {"password_manager_enabled": False}, "search": {"suggest_enabled": False},
        "signin": {"allowed": False}, "browser": {"has_seen_welcome_page": True},
        "translate": {"enabled": False}, "autofill": {"profile_enabled": False, "credit_card_enabled": False}}),
        encoding="utf-8")
    args = ["--profile-directory=Default", "--disable-blink-features=AutomationControlled",
            # --disable-features 는 마지막 하나만 먹는다 — 한 줄에 모은다. 뒤쪽은 크롬이 저절로 구글에 묻는 기능들
            # (자동완성 서버 질의·최적화 가이드·번역·시간 확인·미디어 라우터 — 2026-11-20 접속 기록에서 확인한 것)
            "--disable-features=PrivateNetworkAccessForNavigations,PrivateNetworkAccessPermissionPrompt,PermissionChip,"
            "AutofillServerCommunication,OptimizationHints,OptimizationHintsFetching,OptimizationGuideModelDownloading,"
            "OptimizationTargetPrediction,Translate,NetworkTimeServiceQuerying,MediaRouter,DialMediaRouteProvider",
            # 이 둘이 없으면 나이스 화면이 127.0.0.1 인증서 보안모듈에 못 붙어 암호 칸이 안 뜬다 (2026-11-20 실측).
            # 이 크롬은 출결판 전용 프로필로 나이스만 연다
            "--disable-web-security", "--allow-running-insecure-content",
            "--test-type", "--noerrdialogs", "--start-maximized",
            # 크롬 자체의 백그라운드 접속(동기화·확장 업데이트·부품 업데이트·지표 보고)을 끈다
            "--disable-background-networking", "--disable-sync", "--disable-component-update",
            "--disable-default-apps", "--no-first-run", "--metrics-recording-only",
            "--disable-domain-reliability", "--disable-client-side-phishing-detection",
            "--disable-extensions", "--no-pings", "--safebrowsing-disable-auto-update", "--no-default-browser-check", "--allow-browser-signin=false",
            # 작업표시줄로 내려 둔 창에서도 느려지지 않게
            "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
            "--disable-background-timer-throttling"]
    if netlog_file:
        args.append("--log-net-log=%s" % netlog_file)
    ctx = await p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), channel="chrome", headless=False, slow_mo=40, args=args,
        ignore_default_args=["--enable-automation", "--no-sandbox"], viewport=None)
    hold["ctx"] = ctx
    from urllib.parse import urlsplit
    neis_host = urlsplit(M.NEIS_URL).hostname or ""
    if not (M.NEIS_URL.startswith("https://") and neis_host.endswith(".neis.go.kr")):
        raise PermissionError("나이스 주소가 이상해요 (https://○○.neis.go.kr 이어야 해요). 위젯 오른쪽 클릭 → «인증서 설정»에서 지역을 다시 골라 주세요.")
    blocked = set()

    async def only_neis(route):
        # 이 크롬은 나이스와 이 PC의 인증서 보안모듈(127.0.0.1)에만 간다. 그 밖의 주소는 막는다
        # (보안 설정 두 개를 풀어 둔 크롬이라 엉뚱한 곳에 가지 않게 — 코덱스 검토 2026-11-20)
        u = urlsplit(route.request.url)
        h = u.hostname or ""
        if u.scheme in ("data", "blob", "about") or h.endswith(".neis.go.kr") or h in ("127.0.0.1", "localhost"):
            await route.continue_()
        else:
            blocked.add(h)
            await route.abort()
    await ctx.route("**/*", only_neis)
    hold["blocked"] = blocked
    await ctx.grant_permissions(["notifications"], origin=M._origin_of(M.NEIS_URL))
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    hold["page"] = page
    await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    if os.environ.get("CHULGYEOL_OFFSCREEN"):
        # 만드는 사람 시험용 — 창을 화면 밖에 둔다 (최소화하면 나이스 그리드가 학생 줄을 안 그린다: 2026-11-20 실측 0줄).
        # 받는 분 PC에서는 창을 그대로 보여 준다 — 무엇을 하는지 눈으로 보이게
        try:
            cdp = await ctx.new_cdp_session(page)
            wid = (await cdp.send("Browser.getWindowForTarget"))["windowId"]
            await cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "normal"}})
            await cdp.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"left": -3000, "top": 0, "width": 1600, "height": 1000}})
        except Exception:
            pass
    if NETLOG:
        def on_req(req):
            try:
                from urllib.parse import urlsplit
                with open(NETLOG, "a", encoding="utf-8") as f:
                    f.write("chrome\t%s\t%s\n" % (datetime.now().strftime("%H:%M:%S"), urlsplit(req.url).hostname or req.url[:40]))
            except Exception:
                pass
        ctx.on("request", on_req)
    say("STEP", "나이스 로그인")
    await page.goto(M.NEIS_URL)
    await M.auto_login(page)
    if os.environ.get("CHULGYEOL_DEBUG"):           # 로그인 화면(학생 정보 없음)만 찍는다
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(DATA / "debug_login.png"))
        debug("DEBUG url", page.url)
    say("STEP", "출결 화면 여는 중")
    await M.wait_for_attendance_page(page)
    return M, ctx, page


ROW_FIND_JS = """([num, name]) => {
  const rows = Array.from(document.querySelectorAll('.cl-grid-row'));
  const hit = [];
  rows.forEach((r, i) => {
    const k = r.children;
    if (k.length > 2 && (k[0].innerText || '').trim() === num && (k[1].innerText || '').trim() === name) hit.push(i);
  });
  return hit;
}"""


async def pick_row(page, name, number):
    """«번호 칸 = 번호» 이고 «성명 칸 = 이름» 인 줄 하나만 고른다 (키트 main.pick_student_row 대신 끼운다).
    키트 것은 이름이 «들어간» 줄을 찾아서, 그 학생 줄이 화면 밖이고 이름이 겹치는 다른 학생(예: 이준·이준호)만
    보이면 엉뚱한 줄을 고를 수 있었다 (코덱스 검토 2026-11-20)."""
    for attempt in range(14):
        hit = await page.evaluate(ROW_FIND_JS, [str(number), name])
        if len(hit) == 1:
            return page.locator(".cl-grid-row").nth(hit[0])
        if len(hit) > 1:
            raise RuntimeError("번호·이름이 같은 줄이 둘 이상이라 고르지 않았어요")
        await page.mouse.wheel(0, 600 if attempt < 7 else -600)   # 가상 스크롤 — 아래로 훑고, 다음엔 위로
        await page.wait_for_timeout(250)
    raise RuntimeError("그 번호·이름의 줄을 화면에서 찾지 못했어요")


DATE_JS = r"""() => Array.from(document.querySelectorAll('input'))
  .filter(i => i.offsetParent !== null && /^[0-9]{4}[.][0-9]{2}[.][0-9]{2}/.test(i.value || ''))
  .map(i => i.value)"""


async def open_day(M, page, d):
    """그날 화면으로 가서, 날짜 칸이 정말 그날인지 확인한다. 아니면 False — 그날은 아무것도 안 한다.
    (키트 set_date_and_search 는 날짜를 못 읽어도 True 를 돌려줄 수 있다 — 코덱스 검토 2026-11-20)"""
    await M.dismiss_alert_popup(page, timeout=1000)
    if not await M.set_date_and_search(page, d):
        return False
    want = d.strftime("%Y.%m.%d")
    for _ in range(10):
        vals = await page.evaluate(DATE_JS)
        if vals and all(v.startswith(want) for v in vals):
            await page.wait_for_timeout(600)       # 그리드가 그날 것으로 다시 그려질 틈
            return True
        await page.wait_for_timeout(300)
    debug("DEBUG date mismatch", d, len(await page.evaluate(DATE_JS)))
    return False


async def read_roster(page):
    """지금 화면 날짜의 명렬 {번호: 이름}, 그 학생 줄 «마감» 칸의 출결 표시 {번호: 글자}"""
    import verify_attendance as V
    rows = await V.read_grid(page)
    names = {n: r.get("성명", "").strip() for n, r in rows.items()}
    # 출결 표시는 «마감» 칸에 뜬다. 교시 칸에는 평소에도 과목 이름이 들어 있어 표시로 보면 안 된다 (2026-11-20 실측)
    marks = {n: r.get("마감", "").strip() for n, r in rows.items()}
    return names, marks


# 못 넣는 이유 — 선생님이 바로 고칠 수 있게 «무엇을 하면 되는지»까지 쓴다 (사용자 11/20)
MSG_DAY = "그날 나이스 화면으로 넘어가지 못했어요 — 휴업일이면 넣을 필요 없어요. 아니면 잠시 뒤 다시 해 주세요"
MSG_ROSTER = "그날 나이스 명렬을 읽지 못했어요 — 잠시 뒤 다시 해 주세요"


def check_task(M, t, names, marks, day_cols):
    """넣어도 되는지. 된다 → None, 안 된다 → (갈래, 이유). 갈래: check(확인 필요) · already(이미 있음) · bad(못 넣음)"""
    n = t["number"]
    if t.get("conflict") == "both":
        return ("check", "확인 필요 — 같은 날 두 분류(%s). 나이스에서 직접 정해 주세요" % t["both"])
    if t.get("conflict"):
        return ("bad", "같은 일정이 두 개인데 교시가 서로 달라요 — 캘린더에서 하나를 지워 주세요")
    if not day_cols:
        return ("bad", "그날 나이스 출결 화면을 제대로 읽지 못했어요 — 잠시 뒤 다시 해 주세요")
    if n not in names:
        return ("bad", "나이스 명렬에 %s번이 없어요 — 캘린더 제목의 번호를 확인해 주세요(전학·번호 바뀜)" % n)
    if names[n] != t["name"]:
        return ("bad", "번호와 이름이 나이스와 달라요 (나이스 %s번 = %s) — 캘린더 제목을 고쳐 주세요" % (n, names[n]))
    if marks.get(n):
        return ("already", "이미 나이스에 들어가 있어요 — 고칠 땐 나이스에서 직접 해 주세요")
    if t["jongryu"] in ("지각", "조퇴"):
        g = parse_gyosi(t["note"], t["jongryu"])
        if g is None:
            return ("bad", "조퇴·지각은 제목 끝에 교시를 적어 주세요 — 예: (5교시~) / (~2교시)")
        if M.gyosi_col_index(g, day_cols) is None:
            return ("bad", "그날 나이스엔 %d교시까지예요 — 날짜가 맞는지 확인해 주세요(동아리 날 등)" % M.day_last_period(day_cols))
    return None


async def run(start, end, dry):
    from playwright.async_api import async_playwright
    say("STEP", "구글 캘린더 읽기")
    svc = service()
    cals, recs, bad_titles = read_events(svc, start, end)
    if not cals:
        raise PermissionError("내 구글 캘린더에 «질병결석»·«질병조퇴» 같은 이름의 출결 캘린더가 하나도 없어요.")
    days = expand(recs, start, end)
    say("STEP", "학사일정 읽기 (휴업일)")
    off = school_offdays(start, end)
    hol_items = []                       # 휴업일에 잡힌 일정 — 나이스를 열지 않고 «휴업일이라 안 넣음»으로
    for d in [d for d in days if off and d in off]:
        for t in days.pop(d):
            hol_items.append({"date": d.isoformat(), "number": t["number"], "name": t["name"], "label": t["label"],
                              "gyosi": gyosi_text(t), "ok": False, "kind": "holiday",
                              "why": "휴업일(%s)이라 넣지 않아요" % off[d]})
            record("휴업일 %s %s번 %s — 넣지 않음" % (d, t["number"], t["label"]))
    extra = {"bad_titles": bad_titles, "calendars": sorted(cals), "school": off is not None,
             "offdays": [{"key": "%d/%d" % (d.month, d.day), "label": v} for d, v in sorted((off or {}).items())]}
    total = sum(len(v) for v in days.values())
    record("미리보기 시작 %s~%s · 캘린더 %d개 · %d건 (형식 안 맞는 제목 %d개 · 휴업일 %d건)" % (
        start, end, len(cals), total, bad_titles, len(hol_items)))
    if not total:
        say("PLAN", json.dumps({"items": hol_items, **extra}, ensure_ascii=False))
        say("READY", "넣을 출결이 없어요 (%s~%s)" % (start, end) + (" — 휴업일 일정 %d건은 넣지 않아요" % len(hol_items) if hol_items else ""))
        return 0

    async with async_playwright() as p:
        hold = {}
        try:
            M, ctx, page = await open_neis(p, hold, os.environ.get("CHULGYEOL_CHROME_NETLOG"))
            items, plan, checks = list(hol_items), {}, []
            for d, tasks in days.items():
                say("STEP", "나이스 명렬 대조 %s" % d.strftime("%m/%d"))
                ok_date = await open_day(M, page, d)
                names, marks, cols = ({}, {}, [])
                if ok_date:
                    names, marks = await read_roster(page)
                    cols = await M.read_day_columns(page)
                for t in tasks:
                    if t.get("conflict") == "both":       # 같은 날 두 분류는 나이스 화면을 못 읽어도 «확인 필요»로 (코덱스 재검토)
                        res = check_task(M, t, {}, {}, [])
                    else:
                        res = ("bad", MSG_DAY) if not ok_date else \
                            (("bad", MSG_ROSTER) if not names else check_task(M, t, names, marks, cols))
                    kind, why = res if res else ("ok", "")
                    items.append({"date": d.isoformat(), "number": t["number"], "name": t["name"], "label": t["label"],
                                  "gyosi": gyosi_text(t), "ok": kind == "ok", "kind": kind, "why": why})
                    if kind == "ok":
                        plan.setdefault(d, []).append(t)
                    else:
                        if kind == "check":
                            checks.append(dict(date=d.isoformat(), number=t["number"], label=t["label"],
                                               result="unsure", why=why))
                        record("%s %s %s번 %s — %s" % ({"check": "확인 필요", "already": "이미 있음"}.get(kind, "넣지 않음"),
                                                      d, t["number"], t["label"], code_of(why)))
            n_ok = sum(len(v) for v in plan.values())
            say("PLAN", json.dumps({"items": items, **extra}, ensure_ascii=False))
            cnt = {k: sum(1 for i in items if i["kind"] == k) for k in ("ok", "check", "already", "bad", "holiday")}
            summary = "넣을 것 %d건 · 확인 필요 %d건 · 이미 있음 %d건 · 못 넣는 것 %d건" % (
                cnt["ok"], cnt["check"], cnt["already"], cnt["bad"]) + (" · 휴업일 %d건" % cnt["holiday"] if cnt["holiday"] else "")
            if dry:
                record("미리보기만 (dry-run) — " + summary)
                say("READY", "미리보기만 했어요 — " + summary)
                return 0
            if not n_ok:
                if checks:      # 넣을 건 없어도 «확인 필요»는 결과 창 ❓ 칸에 보이게 (코덱스 재검토)
                    say("RESULT", json.dumps(checks, ensure_ascii=False))
                say("READY", "넣을 수 있는 건이 없어요 — " + summary)
                return 0
            # 미리보기 창에서 10분 안에 고르지 않으면 넣지 않고 끝낸다.
            # (run_in_executor 로 기다리면 끝낼 때 asyncio 가 그 스레드를 기다리느라 멈춘다 → 데몬 스레드)
            import queue
            import threading
            q = queue.Queue()
            threading.Thread(target=lambda: q.put(sys.stdin.readline()), daemon=True).start()
            answer = "TIMEOUT"
            for _ in range(1200):
                try:
                    answer = (q.get_nowait() or "").strip().upper()
                    break
                except queue.Empty:
                    await asyncio.sleep(0.5)
            if answer != "GO":
                record("취소 — 아무것도 넣지 않음")
                say("READY", "취소했어요 — 아무것도 넣지 않았어요")
                return 0
            return await enter(M, page, plan, checks)
        finally:
            if hold.get("blocked"):
                record("크롬이 나이스 밖 주소로 가려던 것 %d곳을 막음" % len(hold["blocked"]))
                debug("DEBUG blocked", sorted(hold["blocked"]))
            if hold.get("ctx"):
                try:
                    await hold["ctx"].close()
                except Exception:
                    pass
            # 한 번 쓴 크롬 프로필은 통째로 지운다 — 나이스 화면이 남긴 캐시(학생 정보가 든 응답일 수 있다)까지
            await asyncio.sleep(1.0)
            shutil.rmtree(PROFILE, ignore_errors=True)


async def enter(M, page, plan, checks=()):
    results = []      # {date, number, label, result: ok|failed|unsure, why}
    for d, tasks in plan.items():
        say("STEP", "입력 %s (%d건)" % (d.strftime("%m/%d"), len(tasks)))
        if not await open_day(M, page, d):
            results += [dict(date=d.isoformat(), number=t["number"], label=t["label"], result="failed",
                             why=MSG_DAY) for t in tasks]
            continue
        # 미리보기 뒤에 나이스가 바뀌었을 수 있다 — 넣기 직전에 번호·이름·이미 입력 여부·교시를 한 번 더 본다
        names, marks = await read_roster(page)
        cols = await M.read_day_columns(page)
        go = []
        for t in tasks:
            res = ("bad", MSG_ROSTER) if not names else check_task(M, t, names, marks, cols)
            if res:
                results.append(dict(date=d.isoformat(), number=t["number"], label=t["label"],
                                    result="unsure" if res[0] == "check" else "failed",
                                    why="넣기 직전 다시 보니 — " + res[1]))
            else:
                go.append(t)
        if not go:
            continue
        tasks = go
        fails, can_save = await M.enter_day(page, d, tasks, cols)
        bad = {(f["number"], f["label"]): f for f in fails}
        status, reason = (M.SAVE_UNSURE, "그날 저장하지 않았어요") if not can_save else await M.save_page(page)
        for t in tasks:
            f = bad.get((t["number"], t["label"]))
            if f:
                why = f["reason"]
                if "출결마감구분" in why or "Timeout" in why:
                    why = "칸이 안 열렸어요 — 그날이 이미 마감됐으면 나이스에서 마감 취소 후 다시 해 주세요"
                else:
                    why = "나이스에 넣다가 멈췄어요 — 나이스에서 이 학생을 직접 넣어 주세요 (자세히: %s)" % why
                results.append(dict(date=d.isoformat(), number=t["number"], label=t["label"], result="failed", why=why[:160]))
            elif status != M.SAVE_OK:
                results.append(dict(date=d.isoformat(), number=t["number"], label=t["label"], result="unsure",
                                    why="나이스가 «저장했어요»라고 답하지 않았어요 — 나이스에서 들어갔는지 눈으로 확인해 주세요"))
            else:
                results.append(dict(date=d.isoformat(), number=t["number"], label=t["label"], result="ok", why=""))
    results = list(checks) + results     # 미리보기에서 «확인 필요»로 뺀 것도 결과 창 ❓ 칸에 보인다
    results.sort(key=lambda r: (r["date"], int(r["number"])))
    for r in results:   # 기록 파일엔 번호와 «정해진 말»만 — 나이스 창 글·이름이 섞일 수 있는 이유 글은 남기지 않는다
        record("입력 %s %s %s번 %s%s" % ({"ok": "🎉", "failed": "❌", "unsure": "❓"}[r["result"]], r["date"], r["number"],
                                       r["label"], "" if r["result"] == "ok" else " — " + code_of(r["why"])))
    say("RESULT", json.dumps(results, ensure_ascii=False))
    c = {k: sum(1 for r in results if r["result"] == k) for k in ("ok", "failed", "unsure")}
    record("입력 끝 — 들어감 %d · 안 들어감 %d · 확인 필요 %d (일·월마감은 하지 않음)" % (c["ok"], c["failed"], c["unsure"]))
    say("READY", "들어감 %d · 안 들어감 %d · 확인 필요 %d" % (c["ok"], c["failed"], c["unsure"]))
    return 0 if not (c["failed"] or c["unsure"]) else 1


CODES = [("같은 날 두 분류", "같은 날 두 분류"), ("번호와 이름이", "번호·이름 불일치"), ("명렬에", "나이스 명렬에 없음"),
         ("이미 나이스에", "이미 입력돼 있음"), ("제목 끝에 교시", "교시 없음"), ("교시까지예요", "그날 없는 교시"),
         ("같은 일정이 두 개", "같은 일정 둘·교시 다름"), ("제대로 읽지", "화면 모양 못 읽음"),
         ("화면으로 넘어가지", "그날 화면 못 엶"), ("명렬을 읽지", "명렬 못 읽음"), ("칸이 안 열렸", "칸이 안 열림(마감된 날?)"),
         ("넣다가 멈췄", "넣다가 멈춤"), ("저장했어요", "저장 확인 못함")]


def code_of(why):
    """화면에 보여 준 이유 → 기록 파일에 쓸 «정해진 말». 모르는 글이면 «기타» (그 글은 남기지 않는다)."""
    for key, code in CODES:
        if key in (why or ""):
            return code
    return "기타"


# ─────────────────────────── 구글 연결 ───────────────────────────
def auth(client_path):
    src = Path(client_path)
    try:
        j = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        say("FAIL", "고른 파일을 읽지 못했어요 — 구글 클라우드에서 받은 .json 파일을 골라 주세요.")
        return 1
    if "installed" not in j:
        kind = "웹 애플리케이션" if "web" in j else ("서비스 계정" if j.get("type") == "service_account" else "알 수 없는 종류")
        say("FAIL", "이 파일은 «%s» 키예요. OAuth 클라이언트 ID 를 «데스크톱 앱»으로 만들어 받은 파일을 골라 주세요." % kind)
        return 1
    DATA.mkdir(parents=True, exist_ok=True)
    if src.resolve() != CLIENT.resolve():
        shutil.copyfile(src, CLIENT)
    from google_auth_oauthlib.flow import InstalledAppFlow
    say("STEP", "브라우저에서 구글 계정을 고르고 «허용»을 눌러 주세요")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT), SCOPES)
    try:
        c = flow.run_local_server(port=0, open_browser=True, timeout_seconds=300,
                                  authorization_prompt_message="", success_message=
                                  "연결됐어요! 이 창은 닫아도 됩니다. (출결판은 캘린더를 «읽기»만 합니다)")
    except Exception as e:
        say("FAIL", "구글 연결이 끝나지 않았어요 (5분 안에 «허용»을 눌러야 해요 · %s)" % type(e).__name__)
        return 1
    if not c or not c.refresh_token:
        say("FAIL", "구글이 «다시 로그인 열쇠»를 주지 않았어요. 다시 해 주세요.")
        return 1
    TOKEN.write_text(c.to_json(), encoding="utf-8")
    return check()


def check():
    try:
        cals = find_calendars(service())
    except PermissionError as e:
        say("FAIL", str(e))
        return 1
    except Exception as e:
        say("FAIL", "구글 캘린더를 읽지 못했어요 (%s) — 인터넷 연결을 보고 다시 해 주세요" % type(e).__name__)
        return 1
    miss = [c for c in CALENDARS if c not in cals]
    if len(miss) == len(CALENDARS):
        say("FAIL", "구글엔 연결됐는데, 이 계정에 출결 캘린더(질병결석 등)가 하나도 없어요. 캘린더를 만든 계정으로 연결해 주세요.")
        return 1
    say("READY", "출결 캘린더 %d개 찾음%s" % (len(cals), (" (없는 것: %s)" % "·".join(miss)) if miss else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auth")
    a.add_argument("--client", required=True)
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("--start", required=True)
    r.add_argument("--end", required=True)
    r.add_argument("--dry-run", action="store_true")
    o = ap.parse_args()
    if not os.environ.get("CHULGYEOL_DEBUG"):
        sys.stdout = open(os.devnull, "w", encoding="utf-8")   # 키트 main.py 의 진행 글(이름 섞임)은 어디에도 안 남긴다
    if o.cmd == "auth":
        return auth(o.client)
    if o.cmd == "check":
        return check()
    try:
        s, e = date.fromisoformat(o.start), date.fromisoformat(o.end)
    except ValueError:
        say("FAIL", "날짜는 2026-11-01 처럼 적어 주세요")
        return 1
    if s > e:
        say("FAIL", "시작 날짜가 끝 날짜보다 뒤예요")
        return 1
    if e > today():
        e = today()      # 미래 날짜는 넣지 않는다 (한국 시각 기준)
    try:
        return asyncio.run(run(s, e, o.dry_run))
    except PermissionError as ex:
        say("FAIL", str(ex))
        return 1
    except Exception as ex:
        record("오류로 멈춤 — %s" % type(ex).__name__)
        if os.environ.get("CHULGYEOL_DEBUG"):       # 만드는 사람 시험용 — 받는 분 PC에선 꺼져 있다
            import traceback
            traceback.print_exc()
        say("FAIL", "중간에 멈췄어요 (%s). 나이스에 들어간 것이 있는지 나이스에서 한 번 봐 주세요." % type(ex).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
