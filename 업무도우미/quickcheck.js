// 생기부 빠른 점검 · © 2026 Kang SeongHo
// 규칙은 tools/check.html(일람표 점검기)과 같다. 규칙을 고치면 두 곳을 함께 고친다.
'use strict';
window.QC = (() => {
  const LIMIT = { 자율: 1500, 동아리: 1500, 진로: 1500, 행동: 900, 교과: 1500, 자유학기: 3000 };
  const ALL = null; // 모든 항목
  const SUBJ = ['교과'];
  // 2026-11-16: 학교 PC의 '중학교 생기부 점검기' 최신판 규칙에 맞췄다.
  const BANNED = [
    ['공인어학·인증시험', /토익|토플|텝스|오픽|TOEIC|TOEFL|TEPS|OPIc|HSK|JLPT|JPT|DELF|DALF|TESTDAF|DSH|DSD|TORFL|DELE|한자능력검정|한자급수|한자자격|실용한자|상무한검|상공회의소\s*한자|인증\s*시험|급수\s*시험|컴활/gi, '공인어학시험·인증시험은 어떤 항목에도 기재 불가', ALL],
    ['대회', /대회|경시|올림피아드|경연|입상|(?:대|금|은|동|최우수|우수|장려|특)상(?:을)?\s*(?:수상|받)/g, '교내외 대회 참여·수상은 기재 불가(교내대회는 수상경력에만). 체육대회 같은 학교 행사인지 확인', ALL],
    ['교외상', /표창장|감사장|공로상/g, '교외 기관·단체의 상은 기재 불가', ALL],
    ['논문', /소?논문|학회지|학술지|학회(?:에서)?\s*발표/g, '논문 투고·학회 발표는 기재 불가', ALL],
    ['도서출간', /출간|저서/g, '도서출간 사실은 기재 불가', ALL],
    ['지식재산권', /특허|실용신안|상표\s*(?:출원|등록)/g, '지식재산권 출원·등록은 기재 불가', ALL],
    ['해외활동', /해외\s*(?:연수|봉사|캠프|활동)|어학\s*연수|교환\s*학생/g, '해외 활동실적은 기재 불가', ALL],
    ['부모 배경', /(?:아버지|어머니|부모님?|아빠|엄마|삼촌|이모|고모|친척)(?:의|가|께서|는|이)?\s*(?:직업|직장|회사|병원|의사|변호사|교수|대표|사장|약사|판사|검사|공무원|운영하)/g, '부모·친인척의 사회·경제적 지위 암시는 기재 불가', ALL],
    ['장학', /장학생|장학금/g, '장학 관련 내용은 기재 불가', ALL],
    ['사교육·상호명', /(?<!대)학원|과외|인강|유튜브|메가스터디|이투스/g, '사교육·상호명은 기재 불가', ALL],
    ['특정 대학명', /[가-힣]{1,10}대학교/g, '특정 대학명은 기재 불가(문맥 확인)', ALL],
    ['자격증', /자격증|자격\s*(?:취득|획득)/g, '자격증 명칭·취득 사실은 기재 불가', ALL],
    ['온라인 강좌', /K-?MOOC|MOOC|KOCW|무크/gi, 'MOOC·KOCW 관련 사항은 교과 세특에 기재 불가', SUBJ],
    ['방과후학교', /방과\s*후/g, '방과후학교 활동은 기재 불가(동아리의 방과후학교스포츠클럽 클럽명만 예외)', ['교과', '행동', '자율', '진로', '자유학기']],
    ['연구보고서', /연구\s*보고서/g, '연구보고서(소논문) 관련은 세특 기재 불가, 창체에서도 제목·주제 등 불가', ['교과', '자율', '동아리', '진로']],
  ];
  // 금지로 단정하기 어려워 '확인 필요'로만 표시하는 후보
  const CAUTION_RULES = [
    ['상호명·기관명 후보', /네이버|구글|카카오|패들렛|캔바|미리캔버스|띵커벨|클래스카드|노션|챗\s*GPT|ChatGPT|뤼튼|(?<![가-힣])줌(?=을|를|으로|에서|\s*(?:화상|회의|수업))|Zoom|커리어넷|엔트리|스크래치|롯데월드|에버랜드/gi, '구체적인 기관명·상호명은 입력 불가. 교육관련기관이거나 일반 명사로 바꿀 수 있는지 확인'],
    ['강사명 후보', /[가-힣]{2,4}\s*(?:강사|작가|교수|박사)(?:님)?(?=의|가|를|와|과|에게|를\s*초청|\s*초청)/g, '학생이 참여한 강의의 강사명은 입력 불가'],
    ['청소년단체', /청소년\s*단체|스카우트|아람단|누리단|한별단|RCY|우주소년단/g, '청소년단체는 동아리에 단체명만 입력하고 특기사항은 입력하지 않음'],
  ];
  const SPELLING = [
    [/되요/g, "'되요' → '돼요'"], [/몇일/g, "'몇일' → '며칠'"], [/역활/g, "'역활' → '역할'"],
    [/오랜동안/g, "'오랜동안' → '오랫동안'"], [/오랫만/g, "'오랫만' → '오랜만'"], [/금새/g, "'금새' → '금세'"],
    [/구지/g, "'구지' → '굳이'"], [/왠만/g, "'왠만' → '웬만'"], [/설겆이/g, "'설겆이' → '설거지'"],
    [/있슴|없슴/g, "'-슴' → '-음'"], [/어떻해/g, "'어떻해' → '어떡해'"], [/희안/g, "'희안' → '희한'"],
  ];
  const SPACING = [[/ {2,}(?=\S)/g, '연속 공백'], [/[ \t]+[.,]/g, '문장부호 앞 공백'], [/\.\.(?!\.)|\. \./g, '마침표 중복'], [/\t/g, '탭 문자']];
  const SYMBOLS = /[•‣⁃※〓←-⇿■-◿☀-⛿✀-➿⬀-⯿]/g;
  const PASSIVE = [
    [/생각(?:됨|된다|되어|되며|되는)/g, '피동 표현: 관찰한 사실로'], [/보여(?:짐|진다|지는|지며)/g, '피동 표현: 관찰한 사실로'],
    [/판단(?:됨|된다|되는)/g, '피동 표현: 관찰한 사실로'], [/것\s*같(?:음|다|아|은)/g, "추측 표현 '~것 같-': 관찰한 사실로"],
    [/듯\s*(?:함|하다|보임)/g, "추측 표현 '~듯': 관찰한 사실로"],
  ];
  const ENGLISH_OK = new Set(['AI', 'SNS', 'PPT', 'UCC', 'IT', 'TV', 'PAPS', 'CEO', 'PD', 'POP', 'CF', 'PC']);
  const CAUTION = ['산만', '부족함', '떨어짐', '못함', '느림', '불성실', '나쁨', '무관심', '거짓말', 'ㅋㅋ', 'ㅎㅎ', '기타등등'];

  const AI_TRACE = [
    [/\*\*[^*\n]+\*\*|^\s*#{1,6}\s|```/gm, 3, 'AI 답변의 서식 기호(**, #) 그대로 남음: 지우고 입력'],
    [/\$[^$\n]{1,60}\$|\\(?:frac|times|div|sqrt|cdot|left|right|alpha|beta|pi|leq|geq)\b|\^\{|_\{/g, 3, '수식 코드(LaTeX)가 그대로 남음: 나이스에서 깨짐. 글로 풀어 씀'],
    [/다음은\s|아래는\s|작성해\s*(?:드|봤|보았)|물론입니다|도움이\s*되었|수정한\s*(?:버전|내용)|생활기록부\s*[:：]|세특\s*[:：]|행발\s*[:：]/g, 2, 'AI 답변 앞뒤 문구가 남은 것 같음: 확인'],
  ];
  const SUBJECT_WORD = /(?:^|[.]\s*)(?:이|본|해당|위)?\s*학생(?:은|는)\s/gm;
  const RECORD_WORD = /수행\s*평가|생활\s*기록부|생기부|세부\s*능력\s*및\s*특기\s*사항|세특|행발|평가\s*기준/g;

  const bytes = s => [...s].reduce((n, ch) => n + (ch.charCodeAt(0) < 128 ? 1 : 3), 0);

  function sentenceRanges(text) {
    const out = []; let start = 0, depth = 0;
    const push = (a, b) => { while (a < b && /\s/.test(text[a])) a++; while (b > a && /\s/.test(text[b - 1])) b--; if (a < b) out.push([a, b]); };
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if ('([{'.includes(ch)) depth++;
      else if (')]}'.includes(ch)) depth = Math.max(0, depth - 1);
      const boundary = ('.!?'.includes(ch) && depth === 0 && !(ch === '.' && /\d/.test(text[i - 1] || ''))) || ch === '\n';
      if (boundary) { push(start, ch === '\n' ? i : i + 1); start = i + 1; depth = ch === '\n' ? 0 : depth; }
    }
    push(start, text.length);
    return out;
  }
  function endsProperly(sent) {
    let core = sent.replace(/[”’"'」』)\s]+$/, '');
    if (!core.endsWith('.')) return false;
    core = core.slice(0, -1).replace(/[”’"'」』)\s]+$/, '');
    const code = core.charCodeAt(core.length - 1);
    return code >= 0xAC00 && code <= 0xD7A3 && [10, 16].includes((code - 0xAC00) % 28);
  }
  const isExempt = s => /^(해당\s*사항\s*없음\.?\s*)+$/.test(s) || /^\(.*\)$/.test(s) || /^[^\n]{1,20}[:：]$/.test(s) || /\d+\s*시간\s*\)?\.?$/.test(s) || s.replace(/[.\s]/g, '').length < 2;
  const OFFICER = /(?:(?:1|2)\s*학기\s*)?(?:전교|학년|학급)?\s*(?:학생\s*자치회\s*)?(?:부회장|회장|부반장|반장)/g;
  const TERM = /^\s*\(\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*[-~∼～–]\s*\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?\s*\)/;

  function check(text, field) {
    const issues = [];
    if (!text.trim()) return issues;
    const add = (sev, msg, start = -1, end = -1) => issues.push({ sev, msg, start, end });
    const each = (re, sev, msg) => { for (const m of text.matchAll(re)) add(sev, typeof msg === 'function' ? msg(m) : msg, m.index, m.index + m[0].length); };

    const limit = LIMIT[field];
    const n = bytes(text.trim());
    if (limit && n > limit) add(3, `${n.toLocaleString()}Byte로 한도 ${limit.toLocaleString()}Byte를 ${(n - limit).toLocaleString()}Byte 넘음`);
    for (const [kind, re, msg, scope] of BANNED) if (!scope || scope.includes(field)) each(re, 3, `기재 금지 후보(${kind}): ${msg}`);
    for (const [kind, re, msg] of CAUTION_RULES) each(re, 2, `${kind}: ${msg}`);
    for (const [re, msg] of SPELLING) each(re, 2, '맞춤법: ' + msg);
    for (const [re, msg] of SPACING) each(re, 2, msg + ' 확인');
    each(SYMBOLS, 2, '특수문자 입력 지양(기재요령 30쪽)');
    each(/^[ \t]*(?:\d{1,2}[.)](?!\d)|[①-⑳]|[가-하][.)]|[-•▶▸○●■□※])\s*|[①-⑳]/gm, 2, '문단구분 기호(번호) 입력 지양(기재요령 30쪽)');
    each(/[·ㆍ‧∙•]/g, 1, "가운데점: 쉼표나 '와/과', '및'으로 바꿀 수 있는지 검토");
    for (const m of text.matchAll(/[A-Za-z]+/g)) {
      // 한 글자(음이름 C·G, 변수 x 등)는 교과 내용에서 흔해 보지 않는다.
      if (m[0].length === 1 || ENGLISH_OK.has(m[0].toUpperCase())) continue;
      if (/^(cm|mm|m|km|g|kg|mg|ml|mL|L)$/.test(m[0]) && /\d\s*$/.test(text.slice(0, m.index))) continue;
      add(2, `영문 '${m[0]}': 한글 표기나 허용 예외인지 검토`, m.index, m.index + m[0].length);
    }
    for (const [re, msg] of PASSIVE) each(re, 1, msg);
    for (const w of CAUTION) each(new RegExp(w, 'g'), 2, `'${w}': 관찰 근거와 문맥 확인`);
    if (field === '자율') for (const m of text.matchAll(OFFICER)) {
      if (!TERM.test(text.slice(m.index + m[0].length))) add(2, "임원은 '전교·학년·학급'과 재임기간 (YYYY.MM.DD.-YYYY.MM.DD.) 병기 확인", m.index, m.index + m[0].length);
      else if (!/전교|학년|학급/.test(m[0])) add(2, '임원의 전교·학년·학급 범위 확인', m.index, m.index + m[0].length);
    }
    const seenSent = new Map();
    for (const [a, b] of sentenceRanges(text)) {
      const sent = text.slice(a, b);
      const key = sent.replace(/\s/g, '').replace(/[.]$/, ''), k = (seenSent.get(key) || 0) + 1; seenSent.set(key, k);
      if (key.length >= 10 && k === 2) add(2, '같은 문장이 두 번 이상 들어 있음', a, b);
      if (isExempt(sent) || endsProperly(sent)) continue;
      add(2, '명사형 종결(~함, ~음, ~임)과 마침표 확인', Math.max(a, b - 6), b);
    }
    // 2026-11-16: 점검기와 같이 AI 글 흔적, 주어, 기록 용어를 본다.
    for (const [re, sev, msg] of AI_TRACE) each(re, sev, msg);
    each(SUBJECT_WORD, 1, "주어('학생은' 등)는 생략함");
    each(RECORD_WORD, 1, '기록 용어(수행평가·생기부 등) 대신 활동 내용으로 서술함');
    issues.sort((x, y) => y.sev - x.sev || x.start - y.start);
    return issues;
  }

  return { check, bytes, LIMIT };
})();
