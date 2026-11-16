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
function Sort-Choices {
  $h = Get-Hwp; if (-not $h) { return }
  $t = Selected $h
  $c = Split-Choices $t
  if ($c.items.Count -lt 2) { Set-Status '선택지 줄(①~⑤)을 먼저 드래그해서 고르세요.' $true; return }
  if ($c.prefix.Trim()) { Set-Status '발문 줄은 빼고 ① 줄부터 ⑤ 줄까지만 고르세요.' $true; return }
  $sorted = $c.items | Sort-Object @{ e = { Width $_.core } }, @{ e = { $_.idx } }
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

# ── 창 ────────────────────────────────────────────────────
$font = New-Object Drawing.Font('맑은 고딕', 9)
$bold = New-Object Drawing.Font('맑은 고딕', 9, [Drawing.FontStyle]::Bold)
$accent = [Drawing.Color]::FromArgb(122, 58, 143)
$f = New-Object NoActivateForm
$f.Text = '시험지 편집 도우미'; $f.TopMost = $true; $f.Font = $font
$f.FormBorderStyle = 'SizableToolWindow'; $f.BackColor = [Drawing.Color]::FromArgb(251, 252, 253)
$wa = [Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$f.StartPosition = 'Manual'; $f.Width = 324; $f.Height = [Math]::Min(900, $wa.Height); $f.Left = $wa.Right - $f.Width; $f.Top = $wa.Top

$status = New-Object Windows.Forms.Label
$status.Dock = 'Bottom'; $status.Height = 64; $status.Padding = '8,6,8,6'; $status.BackColor = [Drawing.Color]::FromArgb(238, 241, 245)
$status.Text = '한글에서 글자나 문단을 고르고 버튼을 누르세요.'
function Set-Status([string]$msg, [bool]$bad = $false) {
  $status.Text = $msg
  $status.ForeColor = $(if ($bad) { [Drawing.Color]::FromArgb(179, 53, 43) } else { [Drawing.Color]::FromArgb(20, 29, 39) })
}

$flow = New-Object Windows.Forms.FlowLayoutPanel
$flow.Dock = 'Fill'; $flow.AutoScroll = $true; $flow.FlowDirection = 'LeftToRight'; $flow.WrapContents = $true; $flow.Padding = '6,4,6,4'
$f.Controls.Add($flow); $f.Controls.Add($status)
$inner = 262

function Head([string]$t) {
  $l = New-Object Windows.Forms.Label; $l.Text = $t; $l.Font = $bold; $l.ForeColor = $accent
  $l.Width = $inner; $l.Height = 24; $l.TextAlign = 'BottomLeft'; $l.Margin = '2,8,2,2'
  $flow.Controls.Add($l); $flow.SetFlowBreak($l, $false)
}
$tt = New-Object Windows.Forms.ToolTip
# 눌렀을 때 할 일은 스크립트 범위에서 실행한다(GetNewClosure를 쓰면 위의 함수를 못 찾는다).
function Btn([string]$t, [scriptblock]$on, [int]$w = 128, [string]$tip = '') {
  $b = New-Object Windows.Forms.Button; $b.Text = $t; $b.Width = $w; $b.Height = 28; $b.Margin = '2,2,2,2'
  $b.FlatStyle = 'Flat'; $b.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(214, 220, 227); $b.BackColor = [Drawing.Color]::White
  $b.Tag = $t
  $b.Add_Click($on)
  if ($tip) { $tt.SetToolTip($b, $tip) }
  $flow.Controls.Add($b); return $b
}

Head '글자 · 줄 (고른 글자에 적용)'
Btn '자간 좁게' { Do-Action 'CharShapeSpacingDecrease' '자간을 1% 줄였어요.' } 128 'Shift+Alt+N과 같아요. 한 글자가 다음 줄로 넘어갈 때.' | Out-Null
Btn '자간 넓게' { Do-Action 'CharShapeSpacingIncrease' '자간을 1% 늘렸어요.' } 128 'Shift+Alt+W와 같아요.' | Out-Null
Btn '줄 간격 좁게' { Do-Action 'ParagraphShapeDecreaseLineSpacing' '줄 간격을 줄였어요.' } | Out-Null
Btn '줄 간격 넓게' { Do-Action 'ParagraphShapeIncreaseLineSpacing' '줄 간격을 늘렸어요.' } | Out-Null
Btn '장평 좁게' { Do-Action 'CharShapeWidthDecrease' '장평을 줄였어요.' } | Out-Null
Btn '장평 넓게' { Do-Action 'CharShapeWidthIncrease' '장평을 늘렸어요.' } | Out-Null
Btn '글자 작게' { Do-Action 'CharShapeHeightDecrease' '글자를 작게 했어요.' } | Out-Null
Btn '글자 크게' { Do-Action 'CharShapeHeightIncrease' '글자를 크게 했어요.' } | Out-Null
Btn '밑줄' { Do-Action 'CharShapeUnderline' '밑줄을 바꿨어요.' } 84 | Out-Null
Btn '진하게' { Do-Action 'CharShapeBold' '진하게를 바꿨어요.' } 84 | Out-Null
Btn '되돌리기' { Do-Action 'Undo' '한 단계 되돌렸어요.' } 86 'Ctrl+Z와 같아요.' | Out-Null

Head '문항 서식 (커서가 있는 문단)'
Btn '발문 (번호 자동)' { Do-Action 'StyleShortcut2' "'문제' 스타일: 번호가 자동으로 붙어요." } 128 'Ctrl+2 (양식의 문제 스타일)' | Out-Null
Btn '선택지' { Do-Action 'StyleShortcut3' "'선택지' 스타일을 입혔어요." } 128 'Ctrl+3 (양식의 선택지 스타일)' | Out-Null
Btn '<보기> 안 글' { Do-Action 'StyleShortcut5' "'<보기> 안 내용' 스타일을 입혔어요." } 128 'Ctrl+5' | Out-Null
Btn '바탕글 (번호 없음)' { Do-Action 'StyleShortcut1' '바탕글로 바꿨어요.' } 128 'Ctrl+1' | Out-Null
Btn '여기서 줄 맞추기' { Do-Action 'ParagraphShapeIndentAtCaret' '커서 자리에 맞춰 다음 줄을 맞췄어요.' } 128 'Shift+Tab과 같아요. 두 줄 넘는 발문·선택지를 위아래로 맞출 때 커서를 맞출 글자 앞에 두고 누르세요.' | Out-Null
Btn '부정어 밑줄' { Underline-Negative } 128 "커서가 있는 발문에서 '않은·아닌·없는·틀린 것' 같은 말을 찾아 밑줄을 그어요." | Out-Null
$pm = Btn '−' { $script:point = [Math]::Max(0.1, [Math]::Round($script:point - 0.1, 1)); $pv.Text = '【' + $script:point.ToString('0.0') + '점】' } 30
$pv = New-Object Windows.Forms.Label; $pv.Width = 70; $pv.Height = 28; $pv.TextAlign = 'MiddleCenter'; $pv.Font = $bold; $pv.Margin = '2,2,2,2'; $pv.Text = '【3.5점】'; $flow.Controls.Add($pv)
$pp = Btn '+' { $script:point = [Math]::Round($script:point + 0.1, 1); $pv.Text = '【' + $script:point.ToString('0.0') + '점】' } 30
Btn '배점 넣기' { Insert-Point } 122 '커서가 있는 문단 끝에 넣어요.' | Out-Null

Head '상자 넣기 (기출 모양 그대로)'
Btn '<보기> 상자' { Insert-Box 'box_bogi.hwpx' '<보기> 상자를' } 128 | Out-Null
Btn '지문 상자' { Insert-Box 'box_passage.hwpx' '지문 상자를' } 128 | Out-Null
Btn '빈칸 (        )' { Insert-Symbol '(          )' } 128 | Out-Null
Btn '☞ 다음 쪽에 계속' { Insert-Symbol '☞ 다음 쪽에 계속' } 128 | Out-Null

Head '선택지 (①~⑤ 줄을 드래그한 뒤)'
Btn '짧은 것부터 ①' { Sort-Choices } 128 '선택지 글 길이가 짧은 것부터 ①~⑤로 다시 놓아요. 정답 번호가 바뀌니 아래 안내를 보고 고치세요.' | Out-Null
Btn '번호 다시 매기기' { Renumber-Choices } 128 '①②③④⑤가 빠지거나 겹쳤을 때 차례대로 고쳐요.' | Out-Null

Head '기호 넣기 (커서 자리에)'
$sets = @(
  @('( A )', '( B )', '( C )', '( D )', '( E )'),
  @('( a )', '( b )', '( c )', '( d )', '( e )'),
  @('( 가 )', '( 나 )', '( 다 )', '( 라 )', '( 마 )'),
  @('Ⓐ', 'Ⓑ', 'Ⓒ', 'Ⓓ', 'Ⓔ'),
  @('ⓐ', 'ⓑ', 'ⓒ', 'ⓓ', 'ⓔ'),
  @('㉮', '㉯', '㉰', '㉱', '㉲'),
  @('①', '②', '③', '④', '⑤'),
  @('ㄱ.', 'ㄴ.', 'ㄷ.', 'ㄹ.', 'ㅁ.')
)
foreach ($set in $sets) { foreach ($sym in $set) { Btn $sym { param($sender) Insert-Symbol ([string]$sender.Tag) } 50 | Out-Null } }

$foot = New-Object Windows.Forms.Label; $foot.Text = '© 2026 Kang SeongHo · 비영리 공유 허락'; $foot.ForeColor = [Drawing.Color]::Gray
$foot.Width = $inner; $foot.Height = 30; $foot.TextAlign = 'BottomLeft'; $flow.Controls.Add($foot)

# 개발용: 화면 없이 창 그림만 저장해 모양을 확인한다.
if ($env:EXAM_HELPER_SNAPSHOT) {
  $f.Show(); [Windows.Forms.Application]::DoEvents()
  $bmp = New-Object Drawing.Bitmap($f.Width, $f.Height); $f.DrawToBitmap($bmp, (New-Object Drawing.Rectangle(0, 0, $f.Width, $f.Height)))
  $bmp.Save($env:EXAM_HELPER_SNAPSHOT); $f.Close(); return
}
[void]$f.ShowDialog()
