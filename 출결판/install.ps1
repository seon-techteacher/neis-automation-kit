# 출결판 설치 — setup.cmd 가 부른다. ★ 인터넷에서 아무것도 받지 않는다 (필요한 건 전부 이 폴더 안에 있다)
#   1) 프로그램을 %LOCALAPPDATA%\neis-attendance-kit 에 푼다
#   2) 파이썬: 이 PC에 맞는 파이썬(3.10~3.14 · tkinter 포함)이 있으면 그것, 없으면 함께 든 공식 설치 파일로 깐다
#   3) 가상환경(.venv)에 패키지를 이 폴더의 wheel 파일로만 깐다 (pip --no-index)
#   4) 설정 창(지역·인증서)을 띄운다 → 저장하면 출결판 위젯이 뜬다
param([string]$Dest = "", [switch]$NoLaunch)    # 시험용: -Dest 다른폴더 -NoLaunch (설정 창·표시 파일 안 만듦)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$dst = if ($Dest) { $Dest } else { Join-Path $env:LOCALAPPDATA "neis-attendance-kit" }
$data = Join-Path $env:LOCALAPPDATA "neis-automation\출결"

function Fail($msg) {
    Write-Host ""
    Write-Host "  X $msg" -ForegroundColor Red
    Write-Host "    이 창을 사진으로 찍어 두시면 원인을 찾는 데 도움이 돼요."
    Read-Host "닫으려면 Enter"
    exit 1
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  나이스 출결판 설치 (인터넷 없이 설치합니다)" -ForegroundColor Cyan
Write-Host "  (2~10분 걸릴 수 있어요. 이 창을 닫지 마세요)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 0) 크롬 — 출결판은 이 PC의 구글 크롬으로 나이스를 연다
$chrome = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { Fail "구글 크롬이 없어요. 크롬을 먼저 설치한 뒤 setup.cmd 를 다시 실행해 주세요." }

# 1) 프로그램 풀기 (예전 설치가 있으면 코드만 바꾼다 — .venv 와 내 설정은 그대로)
Write-Host "[1/4] 프로그램 넣는 중..."
Get-ChildItem $here -Recurse -File | Unblock-File -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $dst | Out-Null
Expand-Archive (Join-Path $here "app.zip") $dst -Force
Copy-Item (Join-Path $here "requirements.txt") (Join-Path $dst "requirements.txt") -Force
Get-ChildItem $dst -Recurse -File -Exclude *.pyc | Where-Object { $_.FullName -notlike "*\.venv\*" } | Unblock-File -ErrorAction SilentlyContinue
Write-Host "  OK" -ForegroundColor Green

# 2) 파이썬
Write-Host "[2/4] 파이썬 확인 중..."
$check = "import sys, tkinter, venv; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) and sys.maxsize > 2**32 else 1)"
function Test-Py($exe) {
    if (-not $exe) { return $false }
    try { & $exe -c $check 2>$null | Out-Null; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
function Find-Py {
    $cands = @()
    foreach ($v in "313", "312", "311", "314", "310") { $cands += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"; $cands += Join-Path $env:ProgramFiles "Python$v\python.exe" }
    $w = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } | Select-Object -First 1
    if ($w) { $cands += $w.Source }
    foreach ($c in $cands) { if ((Test-Path $c) -and (Test-Py $c)) { return $c } }
    return $null
}
$venvPy = Join-Path $dst ".venv\Scripts\python.exe"
$py = $null
if (-not (Test-Py $venvPy)) {
    $py = Find-Py
    if (-not $py) {
        $inst = Get-ChildItem $here -Filter "python-*-amd64.exe" | Select-Object -First 1
        if (-not $inst) { Fail "함께 든 파이썬 설치 파일이 없어요. 받은 zip 을 다시 풀어 주세요." }
        $sig = Get-AuthenticodeSignature $inst.FullName
        if ($sig.Status -ne "Valid" -or $sig.SignerCertificate.Subject -notmatch "Python Software Foundation") { Fail "파이썬 설치 파일의 서명이 맞지 않아 설치하지 않았어요 ($($sig.Status))." }
        Write-Host "  파이썬이 없어서 함께 든 공식 설치 파일로 깝니다 (1~5분)..." -ForegroundColor Yellow
        Start-Process $inst.FullName -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_test=0", "Include_launcher=0", "Shortcuts=0", "Include_doc=0" -Wait
        $py = Find-Py
        if (-not $py) { Fail "파이썬 설치가 끝나지 않았어요." }
    }
    Write-Host "  OK ($(& $py --version))" -ForegroundColor Green

    # 3) 가상환경 + 패키지 (이 폴더의 wheel 로만)
    Write-Host "[3/4] 필요한 부품 넣는 중 (인터넷 안 씀)..."
    $venv = Join-Path $dst ".venv"
    if (Test-Path $venv) { Remove-Item $venv -Recurse -Force }
    & $py -m venv $venv
    if ($LASTEXITCODE -ne 0) { Fail "가상환경을 만들지 못했어요." }
} else {
    Write-Host "  OK (이미 설치돼 있음)" -ForegroundColor Green
    Write-Host "[3/4] 필요한 부품 확인 중 (인터넷 안 씀)..."
}
$ErrorActionPreference = "Continue"
& $venvPy -m pip install --no-index --find-links (Join-Path $here "wheels") -r (Join-Path $dst "requirements.txt") --disable-pip-version-check --quiet
if ($LASTEXITCODE -ne 0) { Fail "부품 설치에 실패했어요." }
& $venvPy -c "import keyring, psutil, tkinter, playwright, googleapiclient, google_auth_oauthlib, truststore" 2>$null
if ($LASTEXITCODE -ne 0) { Fail "부품이 다 들어오지 않았어요." }
Write-Host "  OK" -ForegroundColor Green

# 4) 출결판 표시 → 설정 창
if ($NoLaunch) { Write-Host "  (시험 모드 — 설정 창은 띄우지 않음)"; exit 0 }
Write-Host "[4/4] 설정 창을 띄웁니다..."
New-Item -ItemType Directory -Force $data | Out-Null
Set-Content (Join-Path $data "enabled") "1"
Write-Host ""
Write-Host "  설치 끝! 설정 창에서 지역을 고르고 인증서 암호를 넣은 뒤 [저장하고 위젯 켜기]를 누르세요." -ForegroundColor Green
Write-Host "  (그다음 위젯 오른쪽 클릭 → «출결 구글 연결»으로 구글 키 파일을 한 번 고르면 끝)" -ForegroundColor Green
$pyw = Join-Path $dst ".venv\Scripts\pythonw.exe"
Start-Process -FilePath $pyw -ArgumentList ('"' + (Join-Path $dst "widget\바로가기_설정창.pyw") + '"') -WorkingDirectory (Join-Path $dst "widget")
Start-Sleep 3
