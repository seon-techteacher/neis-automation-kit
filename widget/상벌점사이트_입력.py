# -*- coding: utf-8 -*-
"""학교 상벌점 사이트(그린마일리지형)에 학생 한 명의 상점·벌점을 넣는다.

  .\\.venv\\Scripts\\python.exe -X utf8 widget\\상벌점사이트_입력.py 항목 --type 벌점
        → 발급기준 항목 번호·점수·내용 목록 (사이트에서 그때그때 읽는다 — 학교마다 다르다)
  .\\.venv\\Scripts\\python.exe -X utf8 widget\\상벌점사이트_입력.py 학생 --student 10203
        → 학번·이름으로 학생 찾기 (5명 넘게 걸리면 수만 알려 준다)
  .\\.venv\\Scripts\\python.exe -X utf8 widget\\상벌점사이트_입력.py 넣기 --student 10203 --type 벌점 --item 9 [--memo "상세 내용"] [--point 3] [--date 2026-11-16]
        → 미리보기만 (아무것도 안 넣는다)
  … 넣기 … --go
        → 실제로 넣는다. 사이트는 넣는 즉시 그 학생 담임선생님께 문자를 보낸다

- 화면은 사이트의 «학생 개인별 입력»(벌점 card.php / 상점 scard.php) 첫 줄과 같다:
  학번 · 이름 · 항목번호 · (점수: 항목에 범위가 있을 때만) · 지도내용(상세) · 날짜 · 지도교사(로그인한 선생님)
- 이유·점수 칸이 따로 없다 — «항목 번호»가 이유와 점수를 정한다. 그래서 항목은 번호로만 받는다
- 로그인은 상벌점사이트_엔진.py(위젯 [상벌점] 단추)와 같은 전용 크롬(9326)을 쓴다
- 학생 명렬을 파일로 저장하지 않는다. 찾을 때마다 사이트에 묻는다
결과 마지막 줄: RESULT_JSON={...}
"""
import argparse
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("green_login", HERE / "상벌점사이트_엔진.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

PAGES = {"벌점": "card.php", "상점": "scard.php"}
LISTS = {"벌점": "card_list.php", "상점": "scard_list.php"}     # «입력 오류자료 정정» 목록 — 넣은 줄이 여기 보인다

JS_ROWS = """(k) => [...document.querySelectorAll('tr')]
  .filter(tr => !tr.querySelector('tr') && k.every(w => tr.innerText.includes(w)))
  .map(tr => tr.innerText.replace(/\\s+/g, ' ').trim())"""
MANY = 5

JS_ITEMS = """() => (typeof parray_no === 'undefined') ? null :
  parray_no.map((n, i) => ({no: n, point: +parray_point[i], max: +parray_point_max[i], text: parray_text[i].trim()}))"""

# 사이트의 학생 찾기(search_ajax.php)를 페이지 안에서 그대로 부른다 — 페이지가 EUC-KR 이라 한글 인코딩을 브라우저에 맡긴다
JS_SEARCH = """(w) => new Promise((res, rej) => {
  const x = new XMLHttpRequest();
  x.onreadystatechange = () => {
    if (x.readyState != 4) return;
    try {
      // 응답 끝의 view_table() 은 화면에 고르기 상자를 그린다 → 안에서만 빈 함수로 가린다
      const f = new Function('var array_name, array1, array2, array3, array4;' +
                             'var view_table = function(){}, down = function(){}, clearResult = function(){};' + x.responseText +
                             '; return {name: array_name || [], info: array2 || [], hakbun: array3 || []};');
      const r = f();
      res(r.hakbun.map((h, i) => ({hakbun: String(h), name: String(r.name[i] || ''), info: String(r.info[i] || '')})));
    } catch (e) { rej(String(e)); }
  };
  x.open('GET', 'search_ajax.php?w=' + w + '&t=1', true); x.send(null);
})"""

JS_FILL = """(a) => {
  const f = document.form;
  f.hakbun1.value = a.hakbun; f.name1.value = a.name; f.pno1.value = a.item;
  search_txt(f.pno1, 'msg1', 'pp1');                 // 사이트가 하는 대로: 항목 내용·상세 칸·점수 칸을 만든다
  if (f.etc1) f.etc1.value = a.memo || '';
  if (f.point1) f.point1.value = String(a.point);
  f.pdate1.value = a.date;
  return {msg: (document.getElementById('msg1') || {}).innerText || '',
          point: f.point1 ? f.point1.value : ((document.getElementById('pp1') || {}).innerText || ''),
          teacher: f.teacher1.options[f.teacher1.selectedIndex] ? f.teacher1.options[f.teacher1.selectedIndex].text : ''};
}"""


def out(obj):
    print("RESULT_JSON=" + json.dumps(obj, ensure_ascii=False), flush=True)


def base_url():
    url, _, _ = G.cfg()
    return url


def open_tab(p):
    """G.run()(로그인 확인)을 먼저 부른 뒤에 쓴다. 새 탭을 돌려준다."""
    b = G.W.connect_sync(p, G.PORT)
    return b.contexts[0].new_page()


def goto(tab, kind):
    tab.goto(urljoin(base_url(), PAGES[kind]), wait_until="domcontentloaded", timeout=20_000)
    tab.wait_for_timeout(500)
    if G.has_password_box(tab):
        raise RuntimeError("상벌점 사이트 로그인이 풀려 있어요 — 위젯 [상벌점]을 한 번 눌러 주세요")


def items(tab, kind):
    goto(tab, kind)
    got = tab.evaluate(JS_ITEMS)
    if not got:
        raise RuntimeError("%s 항목 목록을 못 읽었어요" % kind)
    return got


def find_student(tab, word):
    goto(tab, "벌점")
    return tab.evaluate(JS_SEARCH, word.strip())


def count_rows(tab, kind, keys):
    """입력 목록에서 학번·날짜·항목 내용이 모두 든 줄 수. 목록을 못 읽으면 None."""
    try:
        tab.goto(urljoin(base_url(), LISTS[kind]), wait_until="domcontentloaded", timeout=20_000)
        tab.wait_for_timeout(800)
        return len(tab.evaluate(JS_ROWS, keys))
    except Exception:
        return None


def cmd_items(tab, a):
    its = items(tab, a.type)
    for it in its:
        rng = ("%d~%d" % (it["point"], it["max"])) if it["max"] else str(it["point"])
        print("%4s  %6s점  %s" % (it["no"], rng, it["text"]))
    out({"ok": True, "type": a.type, "count": len(its)})


def cmd_student(tab, a):
    hits = find_student(tab, a.student)
    if len(hits) > MANY:
        print("%d명이 걸립니다 — 학번이나 이름을 더 정확히 주세요" % len(hits))
        out({"ok": False, "count": len(hits)})
        return
    for h in hits:
        print("%s  %s  %s" % (h["hakbun"], h["info"], h["name"]))
    out({"ok": bool(hits), "count": len(hits), "students": hits})


def resolve(tab, a):
    hits = find_student(tab, a.student)
    exact = [h for h in hits if h["hakbun"] == a.student.strip() or h["name"] == a.student.strip()]
    if len(exact) != 1:
        if not exact:
            raise RuntimeError("'%s' 학생을 못 찾았어요 (%d명 비슷)" % (a.student, len(hits)))
        raise RuntimeError("'%s' 이(가) %d명이에요 — 학번으로 주세요: %s"
                           % (a.student, len(exact), ", ".join("%s(%s)" % (h["hakbun"], h["info"]) for h in exact)))
    st = exact[0]
    its = {it["no"]: it for it in items(tab, a.type)}
    it = its.get(str(a.item))
    if not it:
        raise RuntimeError("%s 항목 %s 번이 없어요 — «항목»으로 목록을 보세요" % (a.type, a.item))
    if it["max"]:
        point = a.point if a.point is not None else it["point"]
        if not it["point"] <= point <= it["max"]:
            raise RuntimeError("항목 %s 번은 %d~%d점만 돼요" % (it["no"], it["point"], it["max"]))
    else:
        if a.point is not None and a.point != it["point"]:
            raise RuntimeError("항목 %s 번은 %d점으로 정해져 있어요 (%s)" % (it["no"], it["point"], it["text"][:30]))
        point = it["point"]
    if len((a.memo or "").encode("cp949", "replace")) > 250:
        raise RuntimeError("지도내용(상세)은 250바이트(한글 약 125자)까지예요")
    return st, it, point


def cmd_put(tab, a):
    st, it, point = resolve(tab, a)
    when = a.date or date.today().isoformat()
    plan = {"학번": st["hakbun"], "학생": "%s %s" % (st["info"], st["name"]), "종류": a.type,
            "항목": "%s %s" % (it["no"], it["text"]), "점수": point, "지도내용": a.memo or "", "날짜": when}
    print("📝  " + " / ".join("%s: %s" % (k, v) for k, v in plan.items()))
    if not a.go and not a.fill_only:
        print("👀  미리보기만 했습니다 (넣지 않음). 넣으려면 --go")
        out({"ok": True, "dry": True, "plan": plan})
        return

    keys = [st["hakbun"], when, it["text"][:15]]
    before = count_rows(tab, a.type, keys)
    goto(tab, a.type)
    alerts = []

    def on_dialog(d):
        alerts.append(d.message)
        try:
            d.accept()
        except Exception:
            pass
    tab.on("dialog", on_dialog)
    shown = tab.evaluate(JS_FILL, {"hakbun": st["hakbun"], "name": st["name"], "item": it["no"],
                                   "memo": a.memo or "", "point": point, "date": when})
    if "없습니다" in shown["msg"] or not shown["msg"].strip():
        raise RuntimeError("사이트가 항목 %s 번을 못 알아봤어요 — 넣지 않았습니다" % it["no"])
    print("🧾  화면에 채운 값 — 항목: %s / 점수: %s / 지도교사: %s"
          % (shown["msg"].split("\n")[0][:40], shown["point"], shown["teacher"]))
    if a.fill_only:
        print("🧪  칸만 채워 보고 [입력]은 누르지 않았습니다")
        out({"ok": True, "dry": True, "filled": True, "plan": plan})
        return
    with tab.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
        tab.evaluate("() => document.form.submit()")    # 사이트의 [입력] 단추가 하는 일 그대로
    tab.wait_for_timeout(1500)
    body = tab.locator("body").inner_text(timeout=5000)
    tail = re.sub(r"\s+", " ", body)[:200]
    print("📨  넣은 뒤 화면 안내: %s" % ((" / ".join(alerts))[:200] or "(알림창 없음)"))
    after = count_rows(tab, a.type, keys)
    if before is None or after is None:
        verified = None
        print("❔  입력 목록을 못 읽어 들어갔는지 확인하지 못했습니다 — 사이트 «입력 오류자료 정정»에서 봐 주세요")
    elif after == before + 1:
        verified = True
        print("✅  입력 목록에서 확인: 이 학생·날짜·항목 줄이 %d → %d 줄" % (before, after))
    else:
        verified = False
        print("⚠️  입력 목록 줄 수가 %s → %s 입니다 (1줄 늘어야 정상) — 사이트에서 직접 봐 주세요" % (before, after))
    out({"ok": verified is not False, "dry": False, "verified": verified, "rows_before": before, "rows_after": after,
         "plan": plan, "alerts": alerts, "after_url": tab.url, "after_text": tail})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["항목", "학생", "넣기"])
    ap.add_argument("--type", choices=list(PAGES), default="벌점")
    ap.add_argument("--student")
    ap.add_argument("--item")
    ap.add_argument("--point", type=int)
    ap.add_argument("--memo", default="")
    ap.add_argument("--date")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--fill-only", action="store_true", help="시험용: 칸만 채우고 [입력]은 안 누른다")
    a = ap.parse_args()
    if a.cmd in ("학생", "넣기") and not a.student:
        ap.error("--student 가 필요합니다")
    if a.cmd == "넣기" and not a.item:
        ap.error("--item 이 필요합니다 (항목 번호)")
    if a.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        ap.error("--date 는 2026-11-16 모양으로")
    G.W.watchdog(180)
    from playwright.sync_api import sync_playwright
    try:
        G.run()     # 전용 크롬이 없거나 로그인이 풀렸으면 로그인부터 (위젯 [상벌점]과 같은 일, READY 한 줄을 찍는다)
        with sync_playwright() as p:
            tab = open_tab(p)
            try:
                {"항목": cmd_items, "학생": cmd_student, "넣기": cmd_put}[a.cmd](tab, a)
            finally:
                tab.close()
    except Exception as e:
        msg = (str(e).splitlines() or [type(e).__name__])[0][:200]
        print("❌  " + msg, flush=True)
        out({"ok": False, "error": msg})
        sys.exit(1)


if __name__ == "__main__":
    main()
