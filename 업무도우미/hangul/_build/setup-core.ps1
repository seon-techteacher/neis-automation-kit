# 시험지 편집 도우미 설치·지우기 · © 2026 Kang SeongHo (비영리 공유 허락, 출처 표시)
# 이 파일은 설치 파일(exam-helper-setup.cmd) 안에 넣어져 실행된다. 직접 실행하지 않는다.
# 하는 일: 프로그램을 %LOCALAPPDATA%\udesk\exam-helper에 풀고, 패널 버튼(udesk-hangul:) 연결, 바탕화면 바로가기.
# 관리자 권한 없이 지금 사용자에게만 설치한다. 밖으로 아무것도 보내지 않는다.
param([string]$Self, [string]$Mode = '')
Add-Type -AssemblyName System.Windows.Forms, System.IO.Compression
$Title = '시험지 편집 도우미 설치'
$Dest = Join-Path $env:LOCALAPPDATA 'udesk\exam-helper'
$Key = 'HKCU:\Software\Classes\udesk-hangul'
$Lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) '시험지 편집 도우미.lnk'
$Silent = [bool]$Mode
function Say([string]$m, [string]$icon = 'Information') { if (-not $Silent) { [void][Windows.Forms.MessageBox]::Show($m, $Title, 'OK', $icon) } else { Write-Output $m } }

function Stop-Helper {
  Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'exam-helper\.ps1' -and $_.ProcessId -ne $PID } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Uninstall {
  Stop-Helper
  if (Test-Path $Key) { Remove-Item $Key -Recurse -Force }
  if (Test-Path $Lnk) { Remove-Item $Lnk -Force }
  if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
  $parent = Split-Path $Dest; if ((Test-Path $parent) -and -not (Get-ChildItem $parent -Force)) { Remove-Item $parent -Force }
  Say '시험지 편집 도우미를 지웠어요. 바탕화면 바로가기와 패널 버튼 연결도 지웠어요.'
}

function Install {
  # 설치 파일 끝의 '::ZIP ' 줄에 프로그램 파일 묶음이 들어 있다.
  $line = Get-Content -LiteralPath $Self | Where-Object { $_.StartsWith('::ZIP ') } | Select-Object -First 1
  if (-not $line) { Say '설치 파일이 망가졌어요. 다시 받아 주세요.' 'Error'; return }
  $bytes = [Convert]::FromBase64String($line.Substring(6).Trim())
  Stop-Helper
  New-Item -ItemType Directory -Force $Dest | Out-Null
  $zip = New-Object IO.Compression.ZipArchive((New-Object IO.MemoryStream(, $bytes)), [IO.Compression.ZipArchiveMode]::Read)
  foreach ($e in $zip.Entries) {
    if (-not $e.Name) { continue }
    $out = Join-Path $Dest $e.Name
    $src = $e.Open(); $fs = [IO.File]::Create($out); $src.CopyTo($fs); $fs.Dispose(); $src.Dispose()
  }
  $zip.Dispose()
  $ps1 = Join-Path $Dest 'exam-helper.ps1'
  $psexe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $runArgs = "-NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -File `"$ps1`""

  # 패널의 '시험지 편집 도우미' 버튼이 이 프로그램을 열게 한다(지금 사용자만).
  New-Item -Path "$Key\shell\open\command" -Force | Out-Null
  Set-Item -Path $Key -Value 'URL:udesk-hangul'
  New-ItemProperty -Path $Key -Name 'URL Protocol' -Value '' -Force | Out-Null
  Set-Item -Path "$Key\shell\open\command" -Value "`"$psexe`" $runArgs"

  # 바탕화면 바로가기
  $sh = New-Object -ComObject WScript.Shell
  $s = $sh.CreateShortcut($Lnk); $s.TargetPath = $psexe; $s.Arguments = $runArgs; $s.WorkingDirectory = $Dest
  $s.WindowStyle = 7; $s.IconLocation = "$env:SystemRoot\System32\imageres.dll,2"; $s.Description = '한글 옆에 띄우는 시험지 편집 버튼 창'
  $s.Save()

  if (-not $Silent) { Start-Process $psexe -ArgumentList $runArgs }
  Say ("설치했어요.`n`n" +
    "· 바탕화면의 '시험지 편집 도우미'를 누르거나, 업무도우미 패널의 버튼으로 열 수 있어요.`n" +
    "· 한글에서 시험지를 열어 두고 쓰세요.`n" +
    "· 새 판이 나오면 설치 파일을 다시 받아 실행하면 바뀌어요.`n" +
    "· 지우려면 설치 파일을 다시 실행해 '아니요(지우기)'를 누르세요.")
}

if ($Mode -eq 'install') { Install; return }
if ($Mode -eq 'uninstall') { Uninstall; return }
if (Test-Path (Join-Path $Dest 'exam-helper.ps1')) {
  $r = [Windows.Forms.MessageBox]::Show("시험지 편집 도우미가 이미 설치되어 있어요.`n`n예: 새로 설치(새 판으로 바꾸기)`n아니요: 지우기`n취소: 아무것도 안 하기", $Title, 'YesNoCancel', 'Question')
  if ($r -eq 'Yes') { Install } elseif ($r -eq 'No') { Uninstall }
} else {
  $r = [Windows.Forms.MessageBox]::Show("시험지 편집 도우미를 이 PC에 설치할까요?`n`n· 관리자 권한 없이 지금 사용자에게만 설치해요.`n· 바탕화면에 바로가기를 만들고, 업무도우미 패널 버튼과 연결해요.`n· 시험지 내용은 이 PC 밖으로 나가지 않아요.", $Title, 'OKCancel', 'Question')
  if ($r -eq 'OK') { Install }
}
