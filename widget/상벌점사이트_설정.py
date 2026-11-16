# -*- coding: utf-8 -*-
"""위젯 [상벌점] 단추용 — 상벌점 사이트 주소·아이디·비밀번호를 한 번만 넣어 둔다 (검은 창).

  .\\.venv\\Scripts\\python.exe -X utf8 widget\\상벌점사이트_설정.py [사이트 주소]

- 주소·아이디는 설정 파일(teacher_config.json)의 green_url · green_id 에 둔다 (학교마다 달라 코드에 박지 않는다)
- 비밀번호는 Windows 자격 증명 관리자(keyring, 서비스 이름 neis-automation-green)에만 둔다. 화면·파일에 찍지 않는다
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import keyring  # noqa: E402

import teacher_config  # noqa: E402

SERVICE = "neis-automation-green"


def read_raw():
    try:
        return json.loads(teacher_config.CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    teacher_config.prepare_console_window()
    data = read_raw()
    given = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    cur_url = given or data.get("green_url", "")
    cur_id = data.get("green_id", "")

    print("=" * 50)
    print("  위젯 [상벌점] 단추 설정 (딱 한 번)")
    print("=" * 50)
    print("[ ] 안에 보이는 값이 맞으면 그냥 Enter 를 누르세요.\n")

    url = input("1) 상벌점 사이트 주소 [%s]: " % cur_url).strip() or cur_url
    uid = input("2) 아이디 [%s]: " % cur_id).strip() or cur_id
    pw = teacher_config.secret_input("3) 비밀번호 (치는 동안 아무것도 안 보이는 게 정상입니다): ")

    if not url or not uid or not pw:
        print("\n주소·아이디·비밀번호 중 빈 것이 있어 저장하지 않았습니다. 창을 닫고 다시 해 주세요.")
        input("\nEnter 를 누르면 창이 닫힙니다")
        return

    data = read_raw()                 # 그 사이 바뀐 다른 설정을 덮지 않게 다시 읽는다
    data["green_url"] = url
    data["green_id"] = uid
    teacher_config.save_config(data)
    keyring.set_password(SERVICE, uid, pw)
    print("\n저장했습니다. 위젯의 [상벌점] 단추를 누르면 자동으로 로그인합니다.")
    input("\nEnter 를 누르면 창이 닫힙니다")


if __name__ == "__main__":
    main()
