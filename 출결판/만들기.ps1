# 출결판 배포 zip 만들기 (만드는 사람 PC에서 한 번 — 인터넷 필요)
#   powershell -NoProfile -ExecutionPolicy Bypass -File 출결판\만들기.ps1
# 결과: 출결판\_build\chulgyeol-setup.zip — 받는 선생님 PC는 설치할 때 인터넷에서 아무것도 받지 않는다.
#   들어가는 것: 프로그램 코드(app.zip) · 파이썬 공식 설치 파일(서명 확인) · 패키지 wheel 파일(파이썬 3.10~3.14용)
#   빼는 것: 클로드용 파일(CLAUDE.md · mcp_server.py · .claude) · 출결과 상관없는 키트 파일
# 받는 분이 탐색기로 압축을 풀므로 바깥 zip 은 영어 이름 파일만 넣는다 (한글 이름 코드는 app.zip 안 — 설치 스크립트가 푼다)
$ErrorActionPreference = "Stop"
$kit = Split-Path $PSScriptRoot -Parent
$out = Join-Path $PSScriptRoot "_build"
$pkg = Join-Path $out "chulgyeol-setup"
$app = Join-Path $out "app"
foreach ($d in $pkg, $app) { if (Test-Path $d) { Remove-Item $d -Recurse -Force } }
New-Item -ItemType Directory -Force (Join-Path $app "widget"), (Join-Path $pkg "files\wheels") | Out-Null

# 1) 코드 — 목록에 있는 것만 담는다
$root = "main.py", "main_bokmu.py", "teacher_config.py", "verify_attendance.py", "neis_session.py", "neis_cert.py",
        "edufine_common.py", "edufine_inspect.py", "setup_wizard.py", "school_calendar.py", "LICENSE"
$widget = "바로가기위젯.pyw", "바로가기위젯_출결.pyw", "바로가기_엔진.py", "바로가기_설정.py", "바로가기_설정창.pyw", "출결_엔진.py", "출결_달력.html"
foreach ($f in $root)   { Copy-Item (Join-Path $kit $f) (Join-Path $app $f) }
foreach ($f in $widget) { Copy-Item (Join-Path $kit "widget\$f") (Join-Path $app "widget\$f") }
Compress-Archive -Path (Join-Path $app "*") -DestinationPath (Join-Path $pkg "files\app.zip")
Copy-Item (Join-Path $PSScriptRoot "requirements.txt") (Join-Path $pkg "files\requirements.txt")
Copy-Item (Join-Path $PSScriptRoot "install.ps1") (Join-Path $pkg "files\install.ps1")
Copy-Item (Join-Path $PSScriptRoot "setup.cmd") (Join-Path $pkg "setup.cmd")

# 2) 파이썬 공식 설치 파일 (파이썬이 없는 PC용) — 서명이 Python Software Foundation 인지 확인
$pyver = "3.13.16"
$inst = Join-Path $pkg "files\python-$pyver-amd64.exe"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
& curl.exe -L --retry 3 -s -o $inst "https://www.python.org/ftp/python/$pyver/python-$pyver-amd64.exe"   # 학교망에서 Invoke-WebRequest 가 EOF 로 끊긴다(실측)
$sig = Get-AuthenticodeSignature $inst
if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Python Software Foundation") { throw "파이썬 설치 파일 서명이 이상합니다: $($sig.Status)" }

# 3) 패키지 wheel — 받는 PC의 파이썬 버전을 모르니 3.10~3.14 것을 다 담는다 (pip 가 맞는 것을 고른다)
$py = Join-Path $kit ".venv\Scripts\python.exe"
foreach ($v in "3.10", "3.11", "3.12", "3.13", "3.14") {
    & $py -m pip download --disable-pip-version-check -q -r (Join-Path $PSScriptRoot "requirements.txt") `
        -d (Join-Path $pkg "files\wheels") --only-binary=:all: --platform win_amd64 --python-version $v --implementation cp
    if ($LASTEXITCODE -ne 0) { throw "wheel 받기 실패 ($v)" }
}

# 4) 들어가면 안 되는 파일이 섞이지 않았는지 마지막으로 본다
$bad = Get-ChildItem $pkg, $app -Recurse -File | Where-Object { $_.Name -match '^(CLAUDE\.md|mcp_server\.py|oauth_client\.json|client\.json|token.*\.json|teacher_config\.json|.*\.log)$' }
if ($bad) { throw "들어가면 안 되는 파일: $($bad.FullName -join ', ')" }

$zip = Join-Path $out "chulgyeol-setup.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $pkg "*") -DestinationPath $zip
$n = (Get-ChildItem (Join-Path $pkg "files\wheels")).Count
"OK  $zip  ($([math]::Round((Get-Item $zip).Length/1MB,1)) MB · wheel $n 개)"
