# 설치 파일(exam-helper-setup.cmd) 만들기. hangul 폴더를 고친 뒤 이 스크립트를 실행한다.
# 결과: 업무도우미\exam-helper-setup.cmd (파일 하나에 프로그램·상자 파일·설치 코드가 모두 들어 있다)
Add-Type -AssemblyName System.IO.Compression
$hangul = Split-Path $PSScriptRoot
$root = Split-Path $hangul
$files = 'exam-helper.ps1', 'box_bogi.hwpx', 'box_passage.hwpx', 'README.txt'

$ms = New-Object IO.MemoryStream
$zip = New-Object IO.Compression.ZipArchive($ms, [IO.Compression.ZipArchiveMode]::Create, $true)
foreach ($n in $files) {
  $e = $zip.CreateEntry($n, [IO.Compression.CompressionLevel]::Optimal)
  $w = $e.Open(); $b = [IO.File]::ReadAllBytes((Join-Path $hangul $n)); $w.Write($b, 0, $b.Length); $w.Dispose()
}
$zip.Dispose()
$zipB64 = [Convert]::ToBase64String($ms.ToArray())
$core = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'setup-core.ps1'), [Text.Encoding]::UTF8)
$coreB64 = [Convert]::ToBase64String((New-Object Text.UTF8Encoding $false).GetBytes($core))

# cmd 부분은 영문(ASCII)만 쓴다. 한글은 base64 안에만 있다.
$cmd = @(
  '@echo off'
  'rem Exam editing helper (Hangul) installer. (c) 2026 Kang SeongHo. Non-commercial sharing allowed with attribution.'
  'rem Installs for the current user only, no admin rights. Run again to update or remove.'
  'set "UDESK_SELF=%~f0"'
  'powershell -NoProfile -ExecutionPolicy Bypass -STA -Command "$l = Get-Content -LiteralPath $env:UDESK_SELF | Where-Object { $_.StartsWith(''::PS '') } | Select-Object -First 1; $c = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($l.Substring(5))); & ([scriptblock]::Create($c)) -Self $env:UDESK_SELF -Mode ([string]$env:UDESK_SETUP_MODE)"'
  'exit /b'
  ('::PS ' + $coreB64)
  ('::ZIP ' + $zipB64)
) -join "`r`n"
$out = Join-Path $root 'exam-helper-setup.cmd'
[IO.File]::WriteAllText($out, $cmd + "`r`n", [Text.Encoding]::ASCII)
"만듦: $out ($([Math]::Round((Get-Item $out).Length / 1KB)) KB)"
