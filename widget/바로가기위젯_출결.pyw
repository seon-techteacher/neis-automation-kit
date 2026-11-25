# -*- coding: utf-8 -*-
"""바로가기 위젯 «출결판» — 기본 위젯(바로가기위젯.pyw)에 [출결] 단추만 더한 판.

  .\\.venv\\Scripts\\pythonw.exe widget\\바로가기위젯_출결.pyw

[출결]: 기간을 고르면 → 내 구글 캘린더(출결 캘린더 9개)를 «읽기만» 하고 → 나이스 명렬과 번호·이름을 대조해
        미리보기를 보여 준다 → [입력]을 눌러야 나이스 일일출결관리에 넣는다 (출결_엔진.py).
        일마감·월마감은 하지 않는다 — 마감은 선생님이 나이스에서 직접.
처음 한 번: 오른쪽 클릭 «출결 구글 연결» → 구글 클라우드에서 받은 «데스크톱 앱» OAuth 키(.json) 고르기 → 브라우저에서 «허용».

★ AI(클로드 등)에 연결하지 않는다. 학생 이름은 이 PC 화면에만 보이고 파일(기록.log·widget.log)에는 번호만 남는다.
"""
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, ttk

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("바로가기위젯", str(HERE / "바로가기위젯.pyw"),
                                               loader=importlib.machinery.SourceFileLoader("바로가기위젯", str(HERE / "바로가기위젯.pyw")))
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)

ENGINE = HERE / "출결_엔진.py"
DATA = Path(os.environ.get("CHULGYEOL_DATA") or (W.BASE / "출결"))     # 엔진(출결_엔진.py)과 같은 자리
GREEN = "#15803d"
W.BTNS.append(("출결", "attend", "form", GREEN))

NOTICE = ("출결판을 쓰기 전에 꼭 읽어 주세요\n\n"
          "• AI에 연결하지 않아요. 접속하는 곳은\n"
          "   구글 캘린더(읽기만)와 나이스(학사일정 포함)뿐이에요.\n"
          "• 학생 이름은 이 컴퓨터 화면에만 보이고\n"
          "   기록 파일에는 번호만 남아요.\n"
          "• 일정 제목엔 «번호 이름 (교시)»만 적어 주세요.\n"
          "   병명·가정사 같은 사유는 적지 마세요.\n"
          "   (일정의 설명 칸은 읽지 않아요)\n"
          "• 일·월마감은 하지 않아요.\n"
          "   넣은 뒤 나이스에서 확인하고 마감은 직접 해 주세요.\n"
          "• 사용 책임은 쓰시는 선생님께 있어요.\n"
          "   학교 컴퓨터에 설치해도 되는지는\n"
          "   정보부장님께 먼저 여쭤 보세요.")


def has_token():
    return (DATA / "token.json").exists()


def school_set():
    c = W.cfg()
    return bool(c.get("school_office") and c.get("school_code"))


def calendar_data(plan):
    """미리보기 자료 → 달력 화면(출결_달력.html) 자료. 출석인정결석은 주말·휴업일을 뺀 연속 일수를 첫날에 단다."""
    items = plan.get("items", [])
    off = {o["key"] for o in plan.get("offdays", [])}
    key = lambda d: "%d/%d" % (d.month, d.day)
    school_day = lambda d: d.weekday() < 5 and key(d) not in off
    rows = []
    for it in items:
        d = date.fromisoformat(it["date"])
        rows.append({"month": d.month, "day": d.day, "no": it["number"], "name": it["name"], "category": it["label"],
                     "detail": "" if it["gyosi"] in ("하루", "") else it["gyosi"], "dateStr": key(d),
                     "effectiveDays": "", "status": it.get("kind") or ("ok" if it["ok"] else "bad"), "why": it.get("why", "")})
    trip = {}
    for r, it in zip(rows, items):
        if r["category"] == "출석인정결석" and r["status"] != "holiday":
            trip.setdefault(r["no"], []).append((date.fromisoformat(it["date"]), r))
    for runs in trip.values():
        runs.sort(key=lambda x: x[0])
        group = []
        for d, r in runs + [(None, None)]:
            if group and d is not None:
                gap = group[-1][0] + timedelta(days=1)
                while gap < d and not school_day(gap):
                    gap += timedelta(days=1)
            if group and (d is None or gap != d):
                first, last = group[0][0], group[-1][0]
                group[0][1]["effectiveDays"] = "%d일" % len(group)
                group[0][1]["dateStr"] = key(first) + ("~" + key(last) if last != first else "")
                group = []
            if d is not None:
                group.append((d, r))
    last = max((date.fromisoformat(i["date"]) for i in items), default=date.today())
    return {"year": last.year, "month": last.month, "rows": rows, "schoolOffDays": plan.get("offdays", []),
            "clubDays": [], "school": bool(plan.get("school"))}


class CalendarServer:
    """달력 화면을 이 PC 안(127.0.0.1)에서만 잠깐 띄운다. 학생 이름이 든 파일을 디스크에 만들지 않는다.
    주소에 한 번 쓰는 열쇠(token)가 있어야 열리고, 미리보기 창을 닫으면 서버도 닫는다."""
    def __init__(self, page):
        import secrets
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        body, token = page.encode("utf-8"), secrets.token_urlsafe(16)

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                ok = self.path == "/" + token
                self.send_response(200 if ok else 404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if ok:
                    self.wfile.write(body)

            def log_message(self, *a):
                pass
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d/%s" % (self.srv.server_address[1], token)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        try:
            self.srv.shutdown()
            self.srv.server_close()
        except Exception:
            pass


def chrome_path():
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe"
            if p.exists():
                return str(p)
    return None


def fmt(iso):
    d = date.fromisoformat(iso)
    return "%d/%d(%s)" % (d.month, d.day, "월화수목금토일"[d.weekday()])


class AttendWidget(W.Widget):
    def __init__(self):
        super().__init__()
        self.locks["attend"] = threading.Lock()
        self.m.insert_separator(3)
        self.m.insert_command(4, label="출결 구글 연결", command=self.google_setup)
        self.m.insert_command(5, label="출결 기록 보기 (번호만)", command=self.open_record)
        self.m.insert_command(6, label="우리 학교 설정 (휴업일)", command=self.school_setup)
        self.m.insert_command(7, label="출결판 안내 다시 보기", command=lambda: self.info(NOTICE))
        self.cal = None

    # ── 우리 학교 (휴업일은 나이스 학사일정에서 키 없이) ──
    def school_setup(self):
        tip, fr = self.popup("우리 학교를 한 번만 골라 주세요.\n"
                             "나이스 학사일정에서 휴업일·공휴일을 찾아\n"
                             "그날 일정은 넣지 않고, 달력에 회색으로 보여 드려요.\n"
                             "(학교 이름의 일부만 써도 돼요. 예: 한빛중)")
        f = ("Malgun Gothic", 9)
        row = tk.Frame(fr, bg=W.BG)
        row.pack(padx=12, pady=(0, 6), anchor="w")
        ent = tk.Entry(row, font=f, width=22)
        ent.pack(side="left")
        cur = W.cfg().get("school_name")
        if cur:
            ent.insert(0, cur)
        res = tk.Frame(fr, bg=W.BG)
        res.pack(padx=12, anchor="w")

        def pick(s):
            c = W.cfg()
            c.update(school_office=s["office"], school_code=s["code"], school_name=s["name"])
            tmp = W.CONFIG.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, W.CONFIG)
            tip.destroy()
            self.info("우리 학교: %s (%s)\n\n이제 휴업일 일정은 넣지 않고 달력에 회색으로 보여요." % (s["name"], s["office_name"]))

        def show(found, err):
            if not tip.winfo_exists():
                return
            for w_ in res.winfo_children():
                w_.destroy()
            if err:
                tk.Label(res, text="앗, 학교를 찾지 못했어요 — " + err, bg=W.BG, fg="#c0392b", font=f, wraplength=400,
                         justify="left").pack(anchor="w")
            elif not found:
                tk.Label(res, text="그런 이름의 학교가 없어요. 다르게 써 보세요.", bg=W.BG, fg="#c0392b", font=f).pack(anchor="w")
            for s in found[:8]:
                tk.Button(res, text="%s · %s" % (s["name"], s["addr"][:28] or s["office_name"]), font=f, relief="flat",
                          bg="#eef5ee", anchor="w", command=lambda s=s: pick(s)).pack(fill="x", pady=1)
            self.place_tip(tip)

        def search():
            name = ent.get().strip()
            if not name:
                return
            for w_ in res.winfo_children():
                w_.destroy()
            tk.Label(res, text="찾는 중…", bg=W.BG, font=f).pack(anchor="w")

            def fn():
                try:
                    if str(HERE.parent) not in sys.path:
                        sys.path.insert(0, str(HERE.parent))
                    import school_calendar as SC
                    found, err = SC.find_school(name, SC.office_from_neis_url(W.cfg().get("neis_url", ""))), ""
                except Exception as e:
                    found, err = [], (SC.why(e) if "SC" in locals() else type(e).__name__)
                self.root.after(0, show, found, err)
            threading.Thread(target=fn, daemon=True).start()
        tk.Button(row, text="찾기", font=("Malgun Gothic", 9, "bold"), bg=GREEN, fg="white", relief="flat", padx=10,
                  command=search).pack(side="left", padx=4)
        tk.Button(fr, text="닫기", font=f, relief="flat", padx=10, command=tip.destroy).pack(pady=(4, 10))
        ent.bind("<Return>", lambda e: search())
        tip.bind("<Escape>", lambda e: tip.destroy())
        tip.after(50, lambda: (tip.focus_force(), ent.focus_set()))

    # ── 달력으로 보기 ──
    def show_calendar(self, plan):
        page = (HERE / "출결_달력.html").read_text(encoding="utf-8")
        data = json.dumps(calendar_data(plan), ensure_ascii=False).replace("</", "<\\/")
        self.close_calendar()
        self.cal = CalendarServer(page.replace("/*__DATA__*/null", data, 1))
        exe = chrome_path()
        if exe:
            subprocess.Popen([exe, "--app=" + self.cal.url, "--window-size=1360,900"])
        else:
            import webbrowser
            webbrowser.open(self.cal.url)

    def close_calendar(self):
        if self.cal:
            cal, self.cal = self.cal, None
            self.root.after(3000, cal.close)     # 창이 막 열리는 중이면 다 받아 갈 시간을 준다

    # ── 엔진 ──
    def engine(self, args, on_step=None, on_line=None, stdin=False):
        """엔진을 돌린다. stdin=True 면 Popen 을 돌려주고(미리보기 뒤 GO/CANCEL 을 써야 해서) 읽기는 on_line 이 한다."""
        t0 = time.time()
        seen, last = [], ""
        with self.locks["attend"]:
            p = subprocess.Popen([str(W.PY), "-X", "utf8", str(ENGINE), *args], stdout=subprocess.PIPE,
                                 stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                 stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                 env=W.ENV, cwd=str(HERE), creationflags=W.NO_WINDOW)
            self.proc = p
            for line in p.stdout:
                line = line.rstrip("\n")
                if line.startswith(("PLAN ", "RESULT ")):
                    on_line and on_line(line)        # 이름이 든 줄 — 로그에 넣지 않는다
                    continue
                if line.startswith(("STEP ", "READY", "FAIL")):
                    seen.append(line)                # 이 줄들엔 이름이 없다 (엔진 약속)
                if line.startswith("STEP ") and on_step:
                    on_step(line[5:])
                elif line.startswith(("READY", "FAIL")):
                    last = line
            p.wait()
            self.proc = None
        W.log("attend " + args[0], seen, t0)
        return last

    def click(self, site, cmd, text):
        if site != "attend":
            return super().click(site, cmd, text)
        if self.busy:
            return
        if not W.configured():
            return self.say("먼저 오른쪽 클릭 → 인증서 설정", "#c0392b", 6000)
        if not has_token():
            return self.google_setup()
        self.period_form()

    # ── 구글 연결 (처음 한 번) ──
    def google_setup(self):
        tip, fr = self.popup("출결 구글 연결 — 처음 한 번만 합니다.\n\n"
                             "① 구글 클라우드에서 만든 «데스크톱 앱» 키 파일(.json)을\n"
                             "    아래 [키 파일 고르기]로 고르세요.\n"
                             "② 브라우저가 열리면 출결 캘린더가 있는 계정을 고르고\n"
                             "    «허용»을 누르세요.\n\n"
                             "권한은 «캘린더 읽기» 하나뿐이에요.\n"
                             "키와 연결 정보는 이 컴퓨터에만 저장돼요.")
        btns = tk.Frame(fr, bg=W.BG)
        btns.pack(pady=(0, 10))
        f = ("Malgun Gothic", 9)

        def pick():
            path = filedialog.askopenfilename(parent=tip, title="구글 클라우드에서 받은 키 파일(.json) 고르기",
                                              filetypes=[("구글 키 파일", "*.json"), ("모든 파일", "*.*")],
                                              initialdir=str(Path.home() / "Downloads"))
            if not path:
                return
            tip.destroy()
            self.google_connect(path)
        tk.Button(btns, text="키 파일 고르기", font=("Malgun Gothic", 9, "bold"), bg=GREEN, fg="white", relief="flat",
                  padx=12, command=pick).pack(side="left", padx=4)
        tk.Button(btns, text="닫기", font=f, relief="flat", padx=10, command=tip.destroy).pack(side="left", padx=4)
        tip.bind("<Escape>", lambda e: tip.destroy())

    def google_connect(self, path):
        self.busy = "구글 연결 — 브라우저에서 «허용»을 눌러 주세요"

        def fn():
            try:
                last = self.engine(["auth", "--client", path], on_step=lambda s: setattr(self, "busy", s))
            finally:
                self.busy = None
            if last.startswith("READY"):
                self.root.after(0, self.info, "구글 연결 끝! %s\n\n이제 [출결]을 누르면 돼요." % last[6:])
            else:
                self.root.after(0, self.info, "앗, 구글 연결이 안 됐어요.\n\n" + (last[5:] or "알 수 없는 오류"))
        threading.Thread(target=fn, daemon=True).start()

    def open_record(self):
        rec = DATA / "기록.log"
        if not rec.exists():
            return self.say("아직 기록이 없어요", W.INK, 4000)
        subprocess.Popen(["notepad.exe", str(rec)])

    # ── 기간 고르기 ──
    def period_form(self):
        today = date.today()
        v_s, v_e = tk.StringVar(value=today.replace(day=1).isoformat()), tk.StringVar(value=today.isoformat())
        f = ("Malgun Gothic", 9)
        tip, fr = self.popup("출결 — 넣을 기간을 고르고 [미리보기]를 누르세요.\n"
                             "나이스 명렬과 번호·이름을 대조해 보여 드리고, [입력]을 눌러야 들어가요.")
        g = tk.Frame(fr, bg=W.BG)
        g.pack(padx=12, pady=(0, 4), anchor="w")
        quick = tk.Frame(g, bg=W.BG)
        quick.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))
        mon = today - timedelta(days=today.weekday())
        for label, s in (("오늘", today), ("이번 주", mon), ("이번 달", today.replace(day=1))):
            tk.Button(quick, text=label, font=f, relief="flat", bg="#eef5ee", padx=8,
                      command=lambda s=s: (v_s.set(s.isoformat()), v_e.set(today.isoformat()), redraw())).pack(side="left", padx=(0, 4))
        b_s = tk.Button(g, font=f, relief="flat", bg="white", cursor="hand2")
        b_e = tk.Button(g, font=f, relief="flat", bg="white", cursor="hand2")
        tk.Label(g, text="부터", bg=W.BG, font=f).grid(row=1, column=1, padx=4)
        b_s.grid(row=1, column=0, sticky="w")
        b_e.grid(row=1, column=2, sticky="w")
        tk.Label(g, text="까지", bg=W.BG, font=f).grid(row=1, column=3, padx=4)
        cal_box = tk.Frame(fr, bg=W.BG)
        cal_box.pack(padx=12)
        which = {"v": None}

        def redraw():
            b_s.config(text=W.date_label(v_s.get()))
            b_e.config(text=W.date_label(v_e.get()))
            self.place_tip(tip)

        def open_cal(var):
            for w in cal_box.winfo_children():
                w.destroy()
            if which["v"] is var:
                which["v"] = None
            else:
                which["v"] = var
                W.date_picker(cal_box, var, W.BG, on_pick=lambda iso: (redraw(), close_cal())).pack(pady=(2, 4))
            redraw()

        def close_cal():
            for w in cal_box.winfo_children():
                w.destroy()
            which["v"] = None
            self.place_tip(tip)
        b_s.config(command=lambda: open_cal(v_s))
        b_e.config(command=lambda: open_cal(v_e))
        redraw()
        tk.Label(fr, text="※ 오늘 이후 날짜는 넣지 않아요 · 일·월마감은 나이스에서 직접", bg=W.BG, fg="#8a7a68",
                 font=("Malgun Gothic", 8)).pack(padx=12, anchor="w")
        btns = tk.Frame(fr, bg=W.BG)
        btns.pack(pady=(4, 10))

        def go():
            s, e = v_s.get(), v_e.get()
            if s > e:
                return self.say("시작 날짜가 끝 날짜보다 뒤예요", "#c0392b", 5000)
            tip.destroy()
            self.attend_run(s, min(e, today.isoformat()))
        tk.Button(btns, text="미리보기", font=("Malgun Gothic", 9, "bold"), bg=GREEN, fg="white", relief="flat", padx=12,
                  command=go).pack(side="left", padx=4)
        tk.Button(btns, text="닫기", font=f, relief="flat", padx=10, command=tip.destroy).pack(side="left", padx=4)
        tip.bind("<Escape>", lambda e: tip.destroy())
        tip.bind("<Return>", lambda e: go())
        tip.after(50, tip.focus_force)

    # ── 실행: 미리보기 → [입력]/[취소] → 결과 ──
    def attend_run(self, s, e):
        self.busy = "출결 준비 중"
        box = {"plan": None, "result": None}

        def on_line(line):
            tag, _, body = line.partition(" ")
            try:
                data = json.loads(body)
            except ValueError:
                return
            if tag == "PLAN":
                box["plan"] = data
                self.root.after(0, self.preview, data)
            else:
                box["result"] = data

        def fn():
            try:
                last = self.engine(["run", "--start", s, "--end", e], stdin=True, on_line=on_line,
                                   on_step=lambda t: setattr(self, "busy", t + " (크롬이 저절로 움직여요 — 건드리지 마세요)"
                                                             if t.startswith(("나이스", "입력")) else t))
            finally:
                self.busy = None
            if box["result"] is not None:
                self.root.after(0, self.show_result, box["result"], last)
            elif last.startswith("FAIL"):
                self.root.after(0, self.info, "앗, 출결을 못 했어요.\n\n" + last[5:])
            elif last.startswith("READY") and not (box["plan"] and box["plan"].get("items")):
                self.root.after(0, self.info, last[6:])
            elif last.startswith("READY"):
                self.root.after(0, self.say, last[6:][:60], W.INK, 8000)
        threading.Thread(target=fn, daemon=True).start()

    def answer(self, word):
        p = getattr(self, "proc", None)
        try:
            if p and p.stdin:
                p.stdin.write(word + "\n")
                p.stdin.flush()
        except Exception:
            pass

    def preview(self, plan):
        items = plan.get("items", [])
        if not items:
            return            # 넣을 게 없음 — 엔진의 READY 문구로 안내한다
        ok = [it for it in items if it["ok"]]
        win = tk.Toplevel(self.root)
        win.title("출결 미리보기")
        win.attributes("-topmost", True)
        win.configure(bg=W.BG)
        f = ("Malgun Gothic", 9)
        kind = lambda it: it.get("kind") or ("ok" if it["ok"] else "bad")
        n = {k: sum(1 for it in items if kind(it) == k) for k in ("ok", "check", "already", "bad", "holiday")}
        parts = ["넣을 것 %d건" % n["ok"]]
        if n["check"]:
            parts.append("❓ 확인 필요 %d건 (파란 줄)" % n["check"])
        if n["already"]:
            parts.append("이미 있음 %d건 (회색 줄)" % n["already"])
        if n["bad"]:
            parts.append("⚠️ 못 넣는 것 %d건 (노란 줄)" % n["bad"])
        if n["holiday"]:
            parts.append("휴업일 %d건 (회색 줄)" % n["holiday"])
        tk.Label(win, text=" · ".join(parts), bg=W.BG, fg=W.INK, font=("Malgun Gothic", 11, "bold")).pack(padx=14, pady=(12, 2), anchor="w")
        if plan.get("bad_titles"):
            tk.Label(win, text="※ «번호 이름» 모양이 아닌 일정 %d개는 건너뛰었어요" % plan["bad_titles"], bg=W.BG,
                     fg="#8a7a68", font=f).pack(padx=14, anchor="w")
        cols = ("날짜", "번호", "이름", "분류", "교시", "상태")
        frame = tk.Frame(win, bg=W.BG)
        frame.pack(padx=14, pady=6, fill="both", expand=True)
        tv = ttk.Treeview(frame, columns=cols, show="headings", height=min(18, max(4, len(items))))
        for c, w in zip(cols, (90, 50, 80, 100, 90, 620)):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w" if c in ("상태", "이름", "분류") else "center")
        tv.tag_configure("bad", background="#fff4c2")
        tv.tag_configure("check", background="#e3eefc")
        tv.tag_configure("already", background="#eeeeee", foreground="#777777")
        tv.tag_configure("holiday", background="#eeeeee", foreground="#777777")
        mark = {"ok": "넣음", "check": "❓ ", "already": "이미 있음 — ", "bad": "⚠️ ", "holiday": "📅 "}
        for it in items:
            k = kind(it)
            status = "넣음" if k == "ok" else ("이미 있음" if k == "already" else mark[k] + it["why"])
            tv.insert("", "end", values=(fmt(it["date"]), it["number"], it["name"], it["label"], it["gyosi"], status),
                      tags=() if k == "ok" else (k,))
        sb = ttk.Scrollbar(frame, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        tk.Label(win, text="※ 일·월마감은 하지 않아요 — 넣은 뒤 나이스에서 확인하고 마감은 직접 해 주세요.",
                 bg=W.BG, fg="#8a7a68", font=f).pack(padx=14, anchor="w")
        if not plan.get("school"):
            tk.Label(win, text="※ 휴업일 확인은 아직 꺼져 있어요 — 위젯 오른쪽 클릭 → «우리 학교 설정 (휴업일)»",
                     bg=W.BG, fg="#8a6d3b", font=f).pack(padx=14, anchor="w")
        btns = tk.Frame(win, bg=W.BG)
        btns.pack(pady=(6, 12))
        done = {"v": False}

        def reply(word):
            if done["v"]:
                return
            done["v"] = True
            self.answer(word)
            self.close_calendar()
            win.destroy()
        tk.Button(btns, text="📅 달력으로 보기", font=f, relief="flat", bg="#eef5ee", padx=12,
                  command=lambda: (win.attributes("-topmost", False), win.lower(),     # 달력 창이 미리보기 뒤에 숨지 않게
                                   self.show_calendar(plan))).pack(side="left", padx=6)
        if ok:
            tk.Button(btns, text="입력 %d건" % len(ok), font=("Malgun Gothic", 10, "bold"), bg=GREEN, fg="white",
                      relief="flat", padx=16, command=lambda: reply("GO")).pack(side="left", padx=6)
            tk.Button(btns, text="취소", font=f, relief="flat", padx=12, command=lambda: reply("CANCEL")).pack(side="left", padx=6)
        else:
            tk.Button(btns, text="닫기", font=f, relief="flat", padx=12, command=lambda: reply("CANCEL")).pack(side="left", padx=6)
        win.protocol("WM_DELETE_WINDOW", lambda: reply("CANCEL"))
        win.after(50, win.focus_force)

    def show_result(self, results, last):
        win = tk.Toplevel(self.root)
        win.title("출결 결과")
        win.attributes("-topmost", True)
        win.configure(bg=W.BG)
        f = ("Malgun Gothic", 9)
        c = {k: [r for r in results if r["result"] == k] for k in ("ok", "failed", "unsure")}
        title = "🎉 다 들어갔어요! (%d건)" % len(c["ok"]) if not (c["failed"] or c["unsure"]) else \
            "들어감 %d · ❌ 안 들어감 %d · ❓ 확인 필요 %d" % (len(c["ok"]), len(c["failed"]), len(c["unsure"]))
        tk.Label(win, text=title, bg=W.BG, fg=W.INK, font=("Malgun Gothic", 11, "bold")).pack(padx=14, pady=(12, 4), anchor="w")
        txt = tk.Text(win, width=100, height=min(20, 3 + len(results)), font=f, bg="white", relief="flat", wrap="word")
        for r in results:
            mark = {"ok": "🎉", "failed": "❌", "unsure": "❓"}[r["result"]]
            txt.insert("end", "%s %s %s번 %s%s\n" % (mark, fmt(r["date"]), r["number"], r["label"],
                                                   "" if r["result"] == "ok" else "  — " + r["why"].replace("확인 필요 — ", "", 1)))   # ❓ 가 곧 «확인 필요»
        txt.config(state="disabled")
        txt.pack(padx=14, pady=4, fill="both", expand=True)
        tk.Label(win, text="※ 나이스에서 한 번 확인하고, 일·월마감은 직접 해 주세요. "
                           "❌ 는 나이스에서 직접 넣고, ❓ 는 눈으로 확인해 주세요.",
                 bg=W.BG, fg="#8a7a68", font=f, wraplength=760, justify="left").pack(padx=14, anchor="w")
        tk.Button(win, text="확인", font=f, relief="flat", padx=12, command=win.destroy).pack(pady=(6, 12))
        win.after(50, win.focus_force)

    def mainloop(self):
        st = W.load_state()
        if not st.get("attend_notice"):
            self.root.after(1500, lambda: (self.info(NOTICE), W.save_state(attend_notice=1)))
        elif W.configured() and not has_token():
            self.root.after(2500, self.google_setup)
        super().mainloop()


def breakaway():
    """기본 위젯과 같은 이유(클로드 잡 밖으로). 다시 띄울 때 «이 파일»을 띄워야 해서 따로 둔다."""
    import ctypes
    if "--unjobbed" in sys.argv:
        return False
    try:
        k = ctypes.windll.kernel32
        injob = ctypes.c_int(0)
        if not k.IsProcessInJob(k.GetCurrentProcess(), None, ctypes.byref(injob)) or not injob.value:
            return False
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--unjobbed"], cwd=str(HERE),
                         creationflags=0x01000000 | 0x00000008 | 0x00000200, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if breakaway():
        sys.exit(0)
    if W.single_instance():
        sys.exit(0)
    AttendWidget().mainloop()
