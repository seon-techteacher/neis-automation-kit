# 시험지 편집 도우미 · © 2026 Kang SeongHo (비영리 공유 허락, 출처 표시)
# 한글 옆에 띄워 두는 버튼 창. 버튼을 누르면 열려 있는 한글 문서의 커서·선택 자리에 바로 적용한다.
# 한글 자동화(HWPFrame.HwpObject)로 이미 열린 한글에 붙는다. 파일을 밖으로 보내지 않는다.
# 이 파일은 'UTF-8 (BOM)'으로 저장해야 한글이 깨지지 않는다.
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing -TypeDefinition @'
using System; using System.Runtime.InteropServices; using System.Runtime.InteropServices.ComTypes; using System.Windows.Forms;
public static class HwpRot {
  [DllImport("ole32.dll")] static extern int GetRunningObjectTable(int r, out IRunningObjectTable t);
  [DllImport("ole32.dll")] static extern int CreateBindCtx(int r, out IBindCtx c);
  public static object Get() {
    IRunningObjectTable t; if (GetRunningObjectTable(0, out t) != 0) return null;
    IEnumMoniker e; t.EnumRunning(out e); var m = new IMoniker[1]; IBindCtx c; CreateBindCtx(0, out c);
    while (e.Next(1, m, IntPtr.Zero) == 0) {
      string n; m[0].GetDisplayName(c, null, out n);
      if (n.StartsWith("!HwpObject")) { object o; t.GetObject(m[0], out o); return o; }
    }
    return null;
  }
}
public static class Win {
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string c, string t);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
}
// 눌러도 한글에서 포커스를 빼앗지 않는 창 (한글의 선택 영역이 그대로 남는다)
public class NoActivateForm : Form {
  protected override bool ShowWithoutActivation { get { return true; } }
  protected override CreateParams CreateParams { get { var p = base.CreateParams; p.ExStyle |= 0x08000000 | 0x00000008; return p; } }
}
'@

$Here = $PSScriptRoot

# 이미 떠 있으면 새로 열지 않고 그 창을 다시 보이게 한다(패널 버튼을 여러 번 눌러도 하나만).
if (-not $env:EXAM_HELPER_SNAPSHOT) {
  $created = $false
  $script:mutex = New-Object Threading.Mutex($true, 'Local\udesk-exam-helper', [ref]$created)
  if (-not $created) {
    $w = [Win]::FindWindow($null, '시험지 편집 도우미')
    if ($w -ne [IntPtr]::Zero) { [void][Win]::ShowWindow($w, 9) }
    return
  }
}
$script:point = 3.5

# ── 한글 연결 ─────────────────────────────────────────────
function Get-Hwp {
  try { $h = [HwpRot]::Get() } catch { $h = $null }
  if (-not $h) { Set-Status '한글을 찾지 못했어요. 한글에서 시험지를 먼저 열어 주세요.' $true; return $null }
  return $h
}
function Ins($h, [string]$t) {
  $p = $h.HParameterSet.HInsertText
  [void]$h.HAction.GetDefault('InsertText', $p.HSet); $p.Text = $t
  [void]$h.HAction.Execute('InsertText', $p.HSet)
}
function Selected($h) { try { return [string]$h.GetTextFile('TEXT', 'saveblock') } catch { return '' } }
function Do-Action([string]$name, [string]$done) {
  $h = Get-Hwp; if (-not $h) { return }
  if ($h.HAction.Run($name)) { Set-Status $done } else { Set-Status "적용하지 못했어요. 글자나 문단을 먼저 고르세요." $true }
}

# ── 배점 ──
function Insert-Point {
  $h = Get-Hwp; if (-not $h) { return }
  [void]$h.HAction.Run('MoveParaEnd')
  Ins $h ('【' + $script:point.ToString('0.0#') + '점】')
  Set-Status ('문단 끝에 【' + $script:point.ToString('0.0#') + '점】을 넣었어요.')
}

# ── 부정어 밑줄: 커서가 있는 문단에서 '않은·않는·아닌·없는·틀린·다른 것은' 찾아 밑줄 ──
function Underline-Negative {
  $h = Get-Hwp; if (-not $h) { return }
  $l = 0; $p = 0; $q = 0; $h.GetPos([ref]$l, [ref]$p, [ref]$q)
  [void]$h.HAction.Run('MoveParaBegin'); [void]$h.HAction.Run('MoveSelParaEnd')
  $t = Selected $h; [void]$h.HAction.Run('Cancel')
  $ms = [regex]::Matches($t, '(않은|않는|아닌|없는|틀린|다른)(?=\s*(것|질문|문장|대화|단어|표현|설명|내용|곳|말))')
  if (-not $ms.Count) { $h.SetPos($l, $p, $q) | Out-Null; Set-Status "이 문단에서 '않은·아닌·없는 것' 같은 부정어를 찾지 못했어요." $true; return }
  # 자동 번호 문단은 읽은 글 앞에 '1. '이 붙는다. 그 길이만큼 위치를 당기고, 고른 글자가 맞는지 확인한다.
  [void]$h.SelectText($p, 0, $p, 1); $pre = (Selected $h).Length - 1; if ($pre -lt 0) { $pre = 0 }
  foreach ($m in $ms) {
    $hit = $false
    foreach ($off in 0, -1, 1, -2, 2, -3, 3) {
      $a = $m.Index - $pre + $off; if ($a -lt 0) { continue }
      [void]$h.SelectText($p, $a, $p, $a + $m.Length)
      if ((Selected $h).EndsWith($m.Value)) { $hit = $true; break }
    }
    if (-not $hit) { continue }
    $c = $h.HParameterSet.HCharShape; [void]$h.HAction.GetDefault('CharShape', $c.HSet); $c.UnderlineType = 1
    [void]$h.HAction.Execute('CharShape', $c.HSet)
  }
  [void]$h.HAction.Run('Cancel'); $h.SetPos($l, $p, $q) | Out-Null
  Set-Status ("밑줄을 그었어요: " + (($ms | ForEach-Object { $_.Value }) -join ', '))
}

# ── 상자 넣기 (기출에서 떼어 온 빈 상자) ──
function Insert-Box([string]$file, [string]$label) {
  $h = Get-Hwp; if (-not $h) { return }
  $path = Join-Path $Here $file
  if (-not (Test-Path $path)) { Set-Status "$file 파일이 프로그램 폴더에 없어요." $true; return }
  # 글자가 있는 문단이면 새 문단을 만들고, 번호가 붙지 않게 바탕글로 바꾼 뒤 넣는다.
  [void]$h.HAction.Run('MoveParaBegin'); [void]$h.HAction.Run('MoveSelParaEnd')
  $t = Selected $h; [void]$h.HAction.Run('Cancel')
  if ($t.Trim()) { [void]$h.HAction.Run('MoveParaEnd'); [void]$h.HAction.Run('BreakPara') }
  [void]$h.HAction.Run('StyleShortcut1')
  $p = $h.HParameterSet.HInsertFile; [void]$h.HAction.GetDefault('InsertFile', $p.HSet)
  $p.FileName = $path; $p.KeepSection = 0; $p.KeepCharshape = 1; $p.KeepParashape = 1; $p.KeepStyle = 1
  if ($h.HAction.Execute('InsertFile', $p.HSet)) { Set-Status "$label 넣었어요. 상자 안을 눌러 내용을 쓰세요." } else { Set-Status "$label 넣지 못했어요." $true }
}

# ── 선택지: 짧은 것부터 ①, 번호 다시 매기기 ──
$Marks = '①②③④⑤⑥⑦⑧⑨⑩'
function Width([string]$s) {
  $w = 0.0
  foreach ($ch in $s.ToCharArray()) { if ([char]::IsWhiteSpace($ch)) { $w += 0.3 } elseif ([int]$ch -ge 0x1100) { $w += 1 } else { $w += 0.55 } }
  return $w
}
function Split-Choices([string]$t) {
  $parts = [regex]::Split($t, '([①-⑩])')
  $items = @()
  for ($i = 1; $i -lt $parts.Count; $i += 2) {
    $seg = $parts[$i + 1]
    $m = [regex]::Match($seg, '^(\s*)([\s\S]*?)(\s*)$')
    $items += [pscustomobject]@{ mark = $parts[$i]; lead = $m.Groups[1].Value; core = $m.Groups[2].Value; tail = $m.Groups[3].Value; idx = $items.Count }
  }
  return @{ prefix = $parts[0]; items = $items }
}
# 출제 요령(전국연합 선택형 평가문항 출제 요령)의 선택지 순서 (2026-11-18)
#  - 'ㄱ, ㄴ'·'Ⓐ, Ⓒ' 같은 기호 묶음: 개수가 적은 것부터, 같으면 가나다(사전식)
#  - 'A는…', 'B와 C는…'처럼 A·B·C로 시작: 기호 하나짜리를 A→B→C 차례로 먼저, 그다음 둘 이상 비교하는 것
#  - 그 밖: 짧은 것 → 긴 것, 길이가 거의 같으면 가나다
#  '➜ 고친 문장' 줄은 길이에 넣지 않는다.
$KoCulture = [Globalization.CultureInfo]'ko-KR'
$ComboRe = '^(?:[㉠-㉭Ⓐ-Ⓩⓐ-ⓩㄱ-ㅎ]|\(\s*[가-하A-Ea-e]\s*\))(?:\s*,\s*(?:[㉠-㉭Ⓐ-Ⓩⓐ-ⓩㄱ-ㅎ]|\(\s*[가-하A-Ea-e]\s*\)))*\.?$'
function Core-Of([string]$s) { return ($s -replace '\s*➜[\s\S]*$', '').Trim() }
function Order-Choices($items) {
  $cores = @($items | ForEach-Object { Core-Of $_.core })
  $list = New-Object System.Collections.ArrayList
  foreach ($it in $items) { [void]$list.Add($it) }
  if (@($cores | Where-Object { $_ -notmatch $ComboRe }).Count -eq 0) {
    $cmp = { param($a, $b) $x = Core-Of $a.core; $y = Core-Of $b.core
      $d = ($x -split ',').Count - ($y -split ',').Count; if ($d) { return $d }
      return [string]::Compare(($x -replace '\s', ''), ($y -replace '\s', ''), $KoCulture, [Globalization.CompareOptions]::None) }
  } elseif (@($cores | Where-Object { $_ -cnotmatch '^[A-E](?![A-Za-z])' }).Count -eq 0) {
    $cmp = { param($a, $b)
      $la = ([regex]::Matches((Core-Of $a.core), '(?<![A-Za-z])[A-E](?![A-Za-z])') | ForEach-Object { $_.Value }) -join ''
      $lb = ([regex]::Matches((Core-Of $b.core), '(?<![A-Za-z])[A-E](?![A-Za-z])') | ForEach-Object { $_.Value }) -join ''
      $d = $la.Length - $lb.Length; if ($d) { return $d }
      $s = [string]::CompareOrdinal($la, $lb); if ($s) { return $s }
      return $a.idx - $b.idx }
  } else {
    $cmp = { param($a, $b) $x = Core-Of $a.core; $y = Core-Of $b.core
      $d = (Width $x) - (Width $y); if ($d -gt 0.6) { return 1 }; if ($d -lt -0.6) { return -1 }
      $s = [string]::Compare($x, $y, $KoCulture, [Globalization.CompareOptions]::None); if ($s) { return $s }
      return $a.idx - $b.idx }
  }
  # 차례가 바뀌지 않는 삽입 정렬
  $out = New-Object System.Collections.ArrayList
  foreach ($it in $list) {
    $pos = $out.Count
    while ($pos -gt 0 -and (& $cmp $out[$pos - 1] $it) -gt 0) { $pos-- }
    $out.Insert($pos, $it)
  }
  return , $out.ToArray()
}
function Sort-Choices {
  $h = Get-Hwp; if (-not $h) { return }
  $t = Selected $h
  $c = Split-Choices $t
  if ($c.items.Count -lt 2) { Set-Status '선택지 줄(①~⑤)을 먼저 드래그해서 고르세요.' $true; return }
  if ($c.prefix.Trim()) { Set-Status '발문 줄은 빼고 ① 줄부터 ⑤ 줄까지만 고르세요.' $true; return }
  $sorted = Order-Choices $c.items
  $out = $c.prefix; $map = @()
  for ($i = 0; $i -lt $c.items.Count; $i++) {
    $slot = $c.items[$i]; $it = $sorted[$i]
    $out += $Marks[$i] + $slot.lead + $it.core + $slot.tail
    $map += ($Marks[$it.idx] + '→' + $Marks[$i])
  }
  if ($out -eq $t) { Set-Status '이미 짧은 것부터 놓여 있어요.'; return }
  Ins $h $out.TrimEnd("`r", "`n")
  Set-Status ("짧은 순으로 바꿨어요. 정답 번호 확인: " + ($map -join '  ') + "`n(글자 모양은 첫 글자 모양으로 맞춰져요. 되돌리려면 '되돌리기')")
}
function Renumber-Choices {
  $h = Get-Hwp; if (-not $h) { return }
  $t = Selected $h
  $c = Split-Choices $t
  if ($c.items.Count -lt 2) { Set-Status '선택지 줄(①~⑤)을 먼저 드래그해서 고르세요.' $true; return }
  if ($c.prefix.Trim()) { Set-Status '발문 줄은 빼고 ① 줄부터 ⑤ 줄까지만 고르세요.' $true; return }
  $out = $c.prefix
  for ($i = 0; $i -lt $c.items.Count; $i++) { $s = $c.items[$i]; $out += $Marks[$i] + $s.lead + $s.core + $s.tail }
  if ($out -eq $t) { Set-Status '번호가 이미 차례대로예요.'; return }
  Ins $h $out.TrimEnd("`r", "`n"); Set-Status '선택지 번호를 ①부터 차례대로 고쳤어요.'
}
function Insert-Symbol([string]$s) { $h = Get-Hwp; if (-not $h) { return }; Ins $h $s; Set-Status "'$s'를 넣었어요." }


# ── 창 (A안: 정돈형) ─────────────────────────────────────────
$font  = New-Object Drawing.Font('맑은 고딕', 9)
$bold  = New-Object Drawing.Font('맑은 고딕', 9, [Drawing.FontStyle]::Bold)
$small = New-Object Drawing.Font('맑은 고딕', 7.5)
$C = @{
  accent = [Drawing.Color]::FromArgb(122, 58, 143); soft = [Drawing.Color]::FromArgb(244, 238, 247); softLine = [Drawing.Color]::FromArgb(214, 194, 224)
  bg = [Drawing.Color]::FromArgb(251, 252, 253); line = [Drawing.Color]::FromArgb(214, 220, 227); ink = [Drawing.Color]::FromArgb(20, 29, 39)
  muted = [Drawing.Color]::FromArgb(110, 118, 128); sunk = [Drawing.Color]::FromArgb(238, 241, 245)
  bad = [Drawing.Color]::FromArgb(179, 53, 43); badSoft = [Drawing.Color]::FromArgb(251, 227, 224)
  warn = [Drawing.Color]::FromArgb(138, 80, 6); warnSoft = [Drawing.Color]::FromArgb(255, 236, 196)
}
$f = New-Object NoActivateForm
$f.Text = '시험지 편집 도우미'; $f.TopMost = $true; $f.Font = $font
$f.FormBorderStyle = 'SizableToolWindow'; $f.BackColor = $C.bg
$wa = [Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$f.StartPosition = 'Manual'; $f.Width = 324; $f.Height = [Math]::Min(860, $wa.Height); $f.Left = $wa.Right - $f.Width; $f.Top = $wa.Top

# ── 아래 알림 줄: 결과 안내 + 늘 보이는 되돌리기 ──
$bottom = New-Object Windows.Forms.Panel; $bottom.Dock = 'Bottom'; $bottom.Height = 92; $bottom.BackColor = $C.sunk; $bottom.Padding = '8,8,8,8'
$status = New-Object Windows.Forms.Label; $status.Dock = 'Fill'; $status.Font = New-Object Drawing.Font('맑은 고딕', 9.5); $status.Padding = '8,4,6,4'
$status.Text = '한글에서 글자나 문단을 고르고 버튼을 누르세요.'
$undo = New-Object Windows.Forms.Button; $undo.Dock = 'Right'; $undo.Width = 70; $undo.Text = "되돌리기`nCtrl+Z"; $undo.FlatStyle = 'Flat'
$undo.FlatAppearance.BorderColor = $C.line; $undo.BackColor = [Drawing.Color]::White
$undo.Add_Click({ Do-Action 'Undo' '한 단계 되돌렸어요.' })
$gap = New-Object Windows.Forms.Panel; $gap.Dock = 'Right'; $gap.Width = 8; $gap.BackColor = $C.sunk
$bottom.Controls.Add($status); $bottom.Controls.Add($gap); $bottom.Controls.Add($undo)
# 보통 안내는 회색 바탕, 문제는 빨강, 정답 번호가 바뀌는 안내는 노랑으로 크게
function Set-Status([string]$msg, [bool]$bad = $false) {
  $status.Text = $msg
  if ($bad) { $status.BackColor = $C.badSoft; $status.ForeColor = $C.bad; $status.Font = $bold }
  elseif ($msg -match '[①-⑩]→[①-⑩]') { $status.BackColor = $C.warnSoft; $status.ForeColor = $C.warn; $status.Font = New-Object Drawing.Font('맑은 고딕', 9.5, [Drawing.FontStyle]::Bold) }
  else { $status.BackColor = $C.sunk; $status.ForeColor = $C.ink; $status.Font = New-Object Drawing.Font('맑은 고딕', 9.5) }
}

$flow = New-Object Windows.Forms.FlowLayoutPanel
$flow.Dock = 'Fill'; $flow.AutoScroll = $true; $flow.FlowDirection = 'LeftToRight'; $flow.WrapContents = $true; $flow.Padding = '8,2,6,4'
$f.Controls.Add($flow); $f.Controls.Add($bottom)
$inner = 272; $half = 134
$tt = New-Object Windows.Forms.ToolTip

function Head([string]$t, [string]$hint = '') {
  $l = New-Object Windows.Forms.Label; $l.Width = $inner; $l.Height = 26; $l.Margin = '2,6,2,0'; $l.TextAlign = 'BottomLeft'
  $l.Text = $t; $l.Font = $bold; $l.ForeColor = $C.accent
  $flow.Controls.Add($l)
  if ($hint) { $tt.SetToolTip($l, $hint) }
}
# kind: main(자주 쓰는 것, 연보라) / plain(흰색) ; key: 버튼 오른쪽에 작게 적는 단축키
function Btn([string]$t, [scriptblock]$on, [int]$w = $half, [string]$tip = '', [string]$kind = 'plain', [string]$key = '', [int]$h = 30) {
  $b = New-Object Windows.Forms.Button; $b.Text = $t; $b.Width = $w; $b.Height = $h; $b.Margin = '2,2,2,2'; $b.Tag = $t
  $b.FlatStyle = 'Flat'
  if ($kind -eq 'main') { $b.BackColor = $C.soft; $b.FlatAppearance.BorderColor = $C.softLine; $b.Font = $bold }
  else { $b.BackColor = [Drawing.Color]::White; $b.FlatAppearance.BorderColor = $C.line }
  if ($key) {
    $b.TextAlign = 'MiddleLeft'; $b.Padding = '6,0,0,0'
    $k = New-Object Windows.Forms.Label; $k.Text = $key; $k.Font = $small; $k.ForeColor = $C.muted; $k.BackColor = [Drawing.Color]::Transparent
    $k.AutoSize = $false; $k.Width = 44; $k.Height = $h - 4; $k.TextAlign = 'MiddleRight'; $k.Left = $w - 48; $k.Top = 1
    $k.Add_Click({ $this.Parent.PerformClick() }); $b.Controls.Add($k)
  }
  $b.Add_Click($on)
  if ($tip) { $tt.SetToolTip($b, $tip) }
  $flow.Controls.Add($b); return $b
}
# '자간 [−][+]' 한 묶음 (반 줄 폭)
function Pair([string]$name, [string]$down, [string]$up, [string]$tip = '') {
  $l = New-Object Windows.Forms.Label; $l.Text = $name; $l.Width = 50; $l.Height = 30; $l.Margin = '2,2,2,2'; $l.TextAlign = 'MiddleLeft'
  $flow.Controls.Add($l); if ($tip) { $tt.SetToolTip($l, $tip) }
  $d = Btn '−' ([scriptblock]::Create("Do-Action '$down' '$name을(를) 줄였어요.'")) 36 "$name 줄이기"
  $u = Btn '+' ([scriptblock]::Create("Do-Action '$up' '$name을(를) 늘렸어요.'")) 36 "$name 늘리기"
  $d.Font = $bold; $u.Font = $bold
}

Head '문항 서식' '커서가 있는 문단에 적용해요.'
Btn '발문 (번호)' { Do-Action 'StyleShortcut2' "'문제' 스타일: 번호가 자동으로 붙어요." } $half '양식의 문제 스타일' 'main' 'Ctrl+2' | Out-Null
Btn '선택지' { Do-Action 'StyleShortcut3' "'선택지' 스타일을 입혔어요." } $half '양식의 선택지 스타일' 'main' 'Ctrl+3' | Out-Null
Btn '<보기> 안 글' { Do-Action 'StyleShortcut5' "'<보기> 안 내용' 스타일을 입혔어요." } $half '' 'main' 'Ctrl+5' | Out-Null
Btn '바탕글' { Do-Action 'StyleShortcut1' '바탕글로 바꿨어요.' } $half '' 'main' 'Ctrl+1' | Out-Null
Btn '여기서 줄 맞추기' { Do-Action 'ParagraphShapeIndentAtCaret' '커서 자리에 맞춰 다음 줄을 맞췄어요.' } $half 'Shift+Tab과 같아요. 두 줄 넘는 발문·선택지를 위아래로 맞출 때 커서를 맞출 글자 앞에 두고 누르세요.' | Out-Null
Btn '부정어 밑줄' { Underline-Negative } $half "커서가 있는 발문에서 '않은·아닌·없는·틀린 것' 같은 말을 찾아 밑줄을 그어요." | Out-Null

# 배점: 자주 쓰는 값은 한 번에, 0.1점은 −/+
function Show-Point { $pv.Text = '【' + $script:point.ToString('0.0') + '점】' }
Btn '−' { $script:point = [Math]::Max(0.1, [Math]::Round($script:point - 0.1, 1)); Show-Point } 30 '0.1점 내리기' | Out-Null
$pv = New-Object Windows.Forms.Label; $pv.Width = 66; $pv.Height = 30; $pv.TextAlign = 'MiddleCenter'; $pv.Font = $bold; $pv.Margin = '2,2,2,2'; $flow.Controls.Add($pv); Show-Point
Btn '+' { $script:point = [Math]::Round($script:point + 0.1, 1); Show-Point } 30 '0.1점 올리기' | Out-Null
Btn '배점 넣기' { Insert-Point } 134 '커서가 있는 문단 끝에 넣어요.' 'main' | Out-Null
foreach ($v in 2.5, 3, 3.5, 4, 4.5, 5) { Btn ($v.ToString('0.0')) { param($s) $script:point = [double]$s.Tag; Show-Point } 42 '' 'plain' '' 24 | Out-Null }

Head '선택지' '①~⑤ 줄을 드래그해서 고른 뒤 누르세요. 발문 줄은 빼고 고릅니다.'
Btn '짧은 것부터 ①' { Sort-Choices } $half '정답 번호가 바뀌면 아래에 노란 안내가 떠요.' 'main' | Out-Null
Btn '번호 다시 매기기' { Renumber-Choices } $half '①②③④⑤가 빠지거나 겹쳤을 때 차례대로 고쳐요.' | Out-Null

Head '글자 · 줄' '고른 글자나 문단에 적용해요.'
Pair '자간' 'CharShapeSpacingDecrease' 'CharShapeSpacingIncrease' 'Shift+Alt+N / W'
Pair '줄 간격' 'ParagraphShapeDecreaseLineSpacing' 'ParagraphShapeIncreaseLineSpacing'
Pair '장평' 'CharShapeWidthDecrease' 'CharShapeWidthIncrease'
Pair '크기' 'CharShapeHeightDecrease' 'CharShapeHeightIncrease'
Btn '밑줄' { Do-Action 'CharShapeUnderline' '밑줄을 바꿨어요.' } $half | Out-Null
Btn '진하게' { Do-Action 'CharShapeBold' '진하게를 바꿨어요.' } $half | Out-Null

Head '상자 · 자주 쓰는 글' '기출에서 떼어 온 상자 모양 그대로 넣어요.'
Btn '<보기> 상자' { Insert-Box 'box_bogi.hwpx' '<보기> 상자를' } $half | Out-Null
Btn '지문 상자' { Insert-Box 'box_passage.hwpx' '지문 상자를' } $half | Out-Null
Btn '빈칸 (      )' { Insert-Symbol '(          )' } 88 | Out-Null
Btn '묶음 [ ~ ]' { Insert-Symbol '[  ~  ] 다음 글을 읽고 물음에 답하시오.' } 88 '세트 문항 지시문. 번호는 넣은 뒤 고치세요.' | Out-Null
Btn '출처 -「」-' { Insert-Symbol '- 「」 -' } 88 '지문 아래 오른쪽에 넣어요.' | Out-Null
Btn '☞ 다음 쪽에 계속' { Insert-Symbol '☞ 다음 쪽에 계속' } $inner | Out-Null

# 기호: 위 줄에서 종류를 고르면 아래 줄 다섯 칸이 바뀐다(9줄 → 2줄)
Head '기호 넣기' '커서 자리에 넣어요.'
$setNames = @('A', 'a', '가', 'Ⓐ', 'ⓐ', '㉮', '①', 'ㄱ', '『』')
$sets = @(
  @('( A )', '( B )', '( C )', '( D )', '( E )'), @('( a )', '( b )', '( c )', '( d )', '( e )'),
  @('( 가 )', '( 나 )', '( 다 )', '( 라 )', '( 마 )'), @('Ⓐ', 'Ⓑ', 'Ⓒ', 'Ⓓ', 'Ⓔ'), @('ⓐ', 'ⓑ', 'ⓒ', 'ⓓ', 'ⓔ'),
  @('㉮', '㉯', '㉰', '㉱', '㉲'), @('①', '②', '③', '④', '⑤'), @('ㄱ.', 'ㄴ.', 'ㄷ.', 'ㄹ.', 'ㅁ.'), @('○', '『』', '「」', '“”', '‘’')
)
$kindBtns = @(); $symBtns = @()
function Pick-Set([int]$n) {
  for ($j = 0; $j -lt $script:kindBtns.Count; $j++) { $b = $script:kindBtns[$j]; $on = ($j -eq $n)
    $b.BackColor = $(if ($on) { $C.accent } else { [Drawing.Color]::White }); $b.ForeColor = $(if ($on) { [Drawing.Color]::White } else { $C.ink }) }
  $vals = $sets[$n]; for ($i = 0; $i -lt 5; $i++) { $script:symBtns[$i].Text = $vals[$i]; $script:symBtns[$i].Tag = $vals[$i] }
}
for ($j = 0; $j -lt $setNames.Count; $j++) { $kb = Btn $setNames[$j] { param($s) Pick-Set ([int]$s.Name) } 28 '' 'plain' '' 26; $kb.Name = [string]$j; $kb.Margin = '1,2,1,2'; $kindBtns += $kb }
for ($i = 0; $i -lt 5; $i++) { $symBtns += (Btn '' { param($s) Insert-Symbol ([string]$s.Tag) } 50 '' 'plain' '' 34) }
Pick-Set 0

$foot = New-Object Windows.Forms.Label; $foot.Text = '© 2026 Kang SeongHo · 비영리 공유 허락'; $foot.ForeColor = [Drawing.Color]::Gray
$foot.Width = $inner; $foot.Height = 28; $foot.TextAlign = 'BottomLeft'; $flow.Controls.Add($foot)

if ($env:EXAM_HELPER_SNAPSHOT) {
  if ($env:EXAM_HELPER_DEMO) { Set-Status $env:EXAM_HELPER_DEMO }
  $f.Show(); [Windows.Forms.Application]::DoEvents()
  $bmp = New-Object Drawing.Bitmap($f.Width, $f.Height); $f.DrawToBitmap($bmp, (New-Object Drawing.Rectangle(0, 0, $f.Width, $f.Height)))
  $bmp.Save($env:EXAM_HELPER_SNAPSHOT); $f.Close(); return
}
[void]$f.ShowDialog()
