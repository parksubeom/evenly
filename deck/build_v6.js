// 기획서 v6 (편집형 30장) 파이프라인 생성기. 디자인·문구·장 순서는 v6_source/build6.js 그대로이고, 결과 칸만
// tools/prepare_deck_data.py 가 만든 data/results.json 의 결과 키(V6.장.이름 등)로 채운다. 키 표: docs/기획서_v6_결과키.md
//   node build_v6.js [--expect real|fake|rehearsal] [--out 파일] [--missing 파일]
//   results.json 의 source: fake = 가상 수치(make_fake_results) / rehearsal = 공개 대역 / real = 실제 반출
//   오른쪽 위 표시: fake "가상 수치 · 검토용", rehearsal "공개 대역 · 제출 금지", real 없음
//   값이 없으면 ___ 로 남기고 data/missing.txt 에 "누락: 장, 값, 필요한 파일 [key]" (tools/check_deck.py 가 1:1 대조).
//   공개 대역 판에서 원래 채울 수 없는 칸(결과 키의 later)은 ___ 대신 "실제 결과 후" 등으로 보이고 "대체" 로 적음
//   node build_v6.js --expect real --later-ok : 실제 판에서 관악 실측·상호제공 칸만 later 문구로 (22일 판정용)
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
process.chdir(__dirname);
const argv = process.argv.slice(2);
const arg = k => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : undefined; };

// ── 결과 데이터와 가드 ─────────────────────────────────────────
const DATA_PATH = path.join('data', 'results.json');
const R = fs.existsSync(DATA_PATH) ? JSON.parse(fs.readFileSync(DATA_PATH, 'utf8')) : { source:'none', fields:{}, images:{}, tables:{} };
const EXPECT = arg('--expect');
if (EXPECT && R.source !== EXPECT) {     // real 빌드가 가짜·공개 대역 결과를 받으면 멈춤 (prepare_deck_data --expect real 과 같은 가드를 생성기에서도)
  console.error(`!! --expect ${EXPECT} 인데 data/results.json 의 source 가 '${R.source}' 입니다 → 기획서를 만들지 않습니다`);
  process.exit(1);
}
const FAKE = R.source === 'fake', REH = R.source === 'rehearsal', REAL = R.source === 'real';
// [10/13] 대비책 판: 1차 반출(10/2) 결과만 (tools/prepare_fallback_deck.py). 제출 후보라 검토 표시 없음.
//   1차 숫자로 못 채우는 결과 칸은 "2차 분석 결과 반영 예정" (missing 에 '대체'), 팀명·방문일이 비면 그대로 누락
const FALLBACK = R.source === 'fallback';
const FB_TEXT = '2차 분석 결과 반영 예정';
const INPUT_KEYS = new Set(['team_name', 'team_display', 'V6.13.visit2', 'V6.13.visit3']);
// [10/13] 실제 판 --later-ok (22일 판정용, docs/22일_기획서_절차.md): 자료가 원래 없을 수 있는 칸(관악 실측·상호제공)만
//   ___ 대신 결과 키의 later 문구 ("실측 후"·"상호제공데이터 확보 시", missing 에 '대체'). 그 밖의 누락은 그대로 ___
const LATER_OK = R.source === 'real' && argv.includes('--later-ok');
const LATER_OK_RE = /^V6\.15\.\d\.(app|meas|model)$|^V6\.15\.date$|^V6\.16\.meas_r$|^V6\.21\.(skt|kcb)$|^V6\.22\.acc$/;
const BANDS = R.bands || 'mix', MINB = BANDS === 'min';
const HB = () => Q('V6.hb', '1.3'), RMIN = () => Q('V6.rmin', '10');   // 체감 부담 HBI 문턱, 고립 위험 왕복 추가 분 (결과의 run_meta = mapping 한 곳)

const pres = new pptxgen(); pres.layout = 'LAYOUT_16x9';
pres.title = (FAKE ? '[가상 수치 · 검토용] ' : REH ? '[공개 대역 · 제출 금지] ' : '') + '언덕 위 우리동네: 경사 반영 이동약자 접근성 지도';
const F = 'Malgun Gothic';
const C = { ink:'1C2321', text:'2B2F2E', muted:'6B7370', line:'DADFDC', soft:'F3F4F3', acc:'E4572E', accD:'B8401F', teal:'2F7D6D', white:'FFFFFF',
  r1:'8CB8A0', r2:'F2B134', r3:'E4572E', r4:'9E2A2B', onDark:'C9D0CD', reh:'1F5FA8' };
const img = n => 'v6_source/' + n;
let page = 0;

// ── 빈칸 추적 (build_deck.js 와 같은 방식) ───────────────────────
// V() 가 값을 못 찾으면 pending 에 key 를 쌓고, 빈칸(___ / ○○○)이 든 글상자·표가 만들어질 때 빈칸 수만큼 꺼내
// objectName 에 "BLANK:<장>:<key>|..." 로 적음 → tools/check_deck.py 가 missing.txt 와 1:1 대조
const BLANK_RE = /_{3,}|○○○/g;
const pending = [], missing = [], seen = new Set(), fallbacks = [], seenFb = new Set();
const LATER = new Set();                                  // 공개 대역 판에서 보이는 "실제 결과 후" 등 (회색으로)
const flat = t => Array.isArray(t) ? t.map(r => (r && r.text !== undefined) ? flat(r.text) : String(r)).join('') : String(t);
const runs = t => (flat(t).match(BLANK_RE) || []).length;
function take(n, explicit = []) {
  const keys = [];
  for (const k of explicit) { const i = pending.findIndex(p => p.key === k && p.page === page); if (i >= 0) pending.splice(i, 1); keys.push(k); }
  for (let i = 0; i < n; i++) {
    const p = pending.shift();
    if (!p || p.page !== page) { console.error(`!! ${page}장: 빈칸에 대응하는 누락 key 없음 (${p ? p.page + '장 ' + p.key + ' 가 남아 있음' : 'pending 비어 있음'})`); process.exitCode = 1; if (p) pending.unshift(p); break; }
    keys.push(p.key);
  }
  return keys.length ? `BLANK:${page}:` + keys.join('|') : undefined;
}
function miss(key, meta) {
  const k = page + '|' + key; if (seen.has(k)) return; seen.add(k);
  missing.push({ page, key, label: (meta && meta.label) || key, need: (meta && meta.need) || [] });
}
function fb(key, used) {
  const k = page + '|' + key; if (seenFb.has(k)) return; seenFb.add(k);
  const f = R.fields[key] || {};
  fallbacks.push({ page, key, label: f.label || key, need: f.need || [], used });
}
// V: 결과 키 값 → 문자열. 없으면 공개 대역 판은 later 문구(대체), 나머지는 ___(누락)
function V(key, blank = '___') {
  const f = R.fields[key];
  if (f && f.value !== null && f.value !== undefined && f.value !== '') return String(f.value);
  const lok = LATER_OK && LATER_OK_RE.test(key);
  if ((REH || FALLBACK || lok) && f && f.later) {
    const t = (lok && key === 'V6.15.date') ? '실측 후' : f.later;      // 실측을 안 했으면 측정일 자리도 "실측 후" ("2026.10.__" 는 빈칸처럼 보임)
    LATER.add(t); fb(key, t); return t;
  }
  if (FALLBACK && !INPUT_KEYS.has(key)) { LATER.add(FB_TEXT); fb(key, FB_TEXT); return FB_TEXT; }
  if (f && f.optional) { fb(key, blank); return blank; }
  miss(key, f || { label:key, need:[] }); pending.push({ key, page });
  return blank;
}
const has = key => { const f = R.fields[key]; return !!(f && f.value !== null && f.value !== undefined && f.value !== ''); };
const Q = (key, dflt) => { if (has(key)) return String(R.fields[key].value); fb(key, dflt); return dflt; };   // 기본 문구로 말이 되는 보조 값
function IMG(key) {
  const m = R.images[key];
  if (m && m.path && fs.existsSync(m.path)) return m.path;
  if (REH && m && m.later) { fb('img:' + key, m.later); return null; }
  if (FALLBACK) { fb('img:' + key, FB_TEXT); return null; }
  miss('img:' + key, m || { label:key, need:[] }); pending.push({ key:'img:' + key, page });
  return null;
}
function TBL(key) {
  const t = R.tables[key];
  if (t && t.rows && t.rows.length) return t.rows;
  if (FALLBACK) { fb('tbl:' + key, FB_TEXT); return null; }
  miss('tbl:' + key, t || { label:key, need:[] });
  return null;
}
const isLater = t => LATER.has(String(t));

const T = (s, text, o = {}) => {
  const tag = ('_keys' in o) ? o._keys : (runs(text) ? take(runs(text)) : undefined);
  const opt = Object.assign({ fontFace:F, color:C.text, isTextBox:true, margin:0, valign:'top' }, o);
  delete opt._keys; if (tag) opt.objectName = tag;
  return s.addText(text, opt);
};
const hr = (s, x, y, w, color, pt) => s.addShape(pres.shapes.LINE, { x, y, w, h:0, line:{ color:color||C.line, width:pt||0.75 } });
const vr = (s, x, y, h, color, pt) => s.addShape(pres.shapes.LINE, { x, y, w:0, h, line:{ color:color||C.line, width:pt||0.75 } });
const bar = (s, x, y, h, color) => s.addShape(pres.shapes.RECTANGLE, { x, y, w:0.06, h, fill:{color:color||C.acc}, line:{color:color||C.acc} });
const box = (s, x, y, w, h, fill, line) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill:{color:fill||C.white}, line:{color:line||fill||C.white, width:0.75} });
function tag(s, x, y, text, w, color) {
  color = color || C.acc;
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h:0.27, fill:{color:C.white}, line:{color, width:1} });
  T(s, text, { x, y, w, h:0.27, fontSize:10, bold:true, color, align:'center', valign:'middle' });
}
function reviewTag(s, dark) {
  if (!FAKE && !REH) return;
  const col = 'C0392B', txt = FAKE ? '가상 수치 · 검토용' : '공개 대역 · 제출 금지';   // [10/12 판정] 두 표시 모두 빨강 테두리 (청사진)
  s.addShape(pres.shapes.RECTANGLE, { x:7.90, y:0.16, w:1.60, h:0.25, fill:{color: dark ? C.ink : C.white}, line:{color:col, width:1} });
  T(s, txt, { x:7.90, y:0.16, w:1.60, h:0.25, fontSize:9, bold:true, color:col, align:'center', valign:'middle' });
}
const tsize = t => t.length > 34 ? 19 : t.length > 27 ? 21 : 24;
const SCOPE = REH ? `${Q('V6.scope', '관악구')}(공개 대역)` : FALLBACK ? '관악 일대(1차 반출)' : '5개 구';      // 14·17 장의 범위 표현 (공개 대역·대비책 판에서만 바뀜)
// title 에 결과 값(V)이 들어가면 함수로 넘김: 장 번호를 올린 뒤에 값을 읽어야 누락이 이 장에 적힘
function base(kicker, title, o={}) {
  const s = pres.addSlide(); page++;
  if (typeof title === 'function') title = title();
  s.background = { color: C.white };
  T(s, kicker, { x:0.6, y:0.38, w:6.9, h:0.26, fontSize:11, bold:true, color:C.acc });
  T(s, title, { x:0.6, y:0.64, w:8.8, h:0.62, fontSize:o.tsize||tsize(flat(title)), bold:true, color:C.ink, valign:'middle' });
  T(s, String(page), { x:9.0, y:5.25, w:0.45, h:0.22, fontSize:9, color:C.muted, align:'right' });
  reviewTag(s);
  return s;
}
const src = (s, t) => T(s, t, { x:0.6, y:5.22, w:8.2, h:0.28, fontSize:8.5, color:C.muted });
function takeaway(s, text, y) { bar(s, 0.6, y, 0.42); T(s, text, { x:0.82, y, w:8.6, h:0.42, fontSize:13, bold:true, color:C.ink, valign:'middle' }); }
function stat(s, x, y, w, label, value, o={}) {
  T(s, label, { x, y, w, h:0.26, fontSize:11, color:C.muted });
  const v = String(value), later = isLater(v);
  // [10/12 청사진] 대체 문구도 값과 같은 크기·굵기 (색은 회색, laterInk 면 검정)
  T(s, v, { x, y:y+0.26, w, h:0.46, fontSize:(o.size||20), bold:true, color: later ? (o.laterInk ? C.ink : C.muted) : (o.color||(v.includes('___') ? C.accD : C.ink)), valign:'top' });
}
// 자리 상자. key(그림 결과 키)를 주면 그 그림이 빠진 자리: 연한 주황(FFF7F2, check_deck 이 빈칸으로 봄) + 이름표
// [10/13] 사진을 칸(w×h)에 꽉 차게: 가로·세로 비를 맞춰 가운데를 자름 (jpg·png 머리에서 크기를 읽음)
function imgSize(f) {
  const b = fs.readFileSync(f);
  if (b[0] === 0x89 && b[1] === 0x50) return { w:b.readUInt32BE(16), h:b.readUInt32BE(20) };
  for (let i = 2; i < b.length - 9;) {                       // JPEG: SOF0~SOF15 (C4·C8·CC 제외) 의 높이·너비
    if (b[i] !== 0xFF) { i++; continue; }
    const m = b[i+1], len = b.readUInt16BE(i+2);
    if (m >= 0xC0 && m <= 0xCF && ![0xC4, 0xC8, 0xCC].includes(m)) return { w:b.readUInt16BE(i+7), h:b.readUInt16BE(i+5) };
    i += 2 + len;
  }
  return null;
}
function photoCover(f, w, h) {
  const z = imgSize(f);
  if (!z || !z.w || !z.h) return { w, h };
  const k = Math.max(w / z.w, h / z.h);                       // pptxgenjs cover: w·h 는 사진 원래 비율, sizing 이 칸 크기
  return { w:z.w * k, h:z.h * k, sizing:{ type:'cover', w, h } };
}
function slot(s, x, y, w, h, label, key) {
  if (key && FALLBACK) { key = undefined; label = label.split('\n')[0] + '\n' + FB_TEXT; }   // [10/13] 대비책 판: 빈칸이 아니라 예정 자리
  const t = key ? take(0, ['img:' + key]) : undefined;
  s.addShape(pres.shapes.RECTANGLE, Object.assign({ x, y, w, h, fill:{color: key ? 'FFF7F2' : C.white}, line:{color: key ? C.acc : C.muted, width:1, dashType:'dash'} }, t ? { objectName:t } : {}));
  T(s, label, { x:x+0.1, y, w:w-0.2, h, fontSize:11, color: key ? C.accD : C.muted, align:'center', valign:'middle', _keys:t });
}
// 편집형 표: 머리 아래 굵은 선, 행 사이 가는 선, 세로선 없음. explicit = 표 전체가 한 항목(tbl:)의 빈칸일 때
function etable(s, rows, o, explicit) {
  const opt = Object.assign({ x:0.6, y:1.45, w:8.8, fontFace:F, fontSize:11, color:C.text, valign:'middle',
    border:[{type:'none'},{type:'none'},{pt:0.75,color:C.line},{type:'none'}] }, o);
  const body = rows.map((r, i) => r.map(cell => {
    const c = typeof cell === 'string' ? { text:cell, options:{} } : cell;
    const b = i === 0 ? { bold:true, color:C.ink, fontSize:11, border:[{type:'none'},{type:'none'},{pt:1.5,color:C.ink},{type:'none'}] } : {};
    if (String(c.text).includes('___')) b.color = C.accD;
    if (isLater(c.text)) Object.assign(b, { color:C.muted, fontSize:9 });
    return { text:c.text, options:Object.assign({}, b, c.options||{}) };
  }));
  const n = explicit ? 0 : rows.reduce((a, r) => a + r.reduce((b2, c) => b2 + runs(c && c.text !== undefined ? c.text : c), 0), 0);
  const t = (explicit || n) ? take(n, explicit ? [explicit] : []) : undefined;
  s.addTable(body, Object.assign({}, opt, t ? { objectName:t } : {}));
}
const B = (t, o={}) => ({ text:t, options:Object.assign({ bold:true }, o) });
const team = () => has('team_display') ? String(R.fields['team_display'].value) : V('team_name', '○○○');   // [10/12 판정] 1·26장은 표시 이름 (inputs.json team_display, 없으면 team_name)

// ── 1 표지 ──
{ const s = pres.addSlide(); page++; s.background = { color:C.ink };
  s.addImage({ path:img('contour_dark.png'), x:0, y:0, w:10, h:5.625, transparency:55 });
  T(s, '2026 데이터+AI 혁신 챌린지 · 데이터안심구역 경진대회 (한국국토정보공사)', { x:0.7, y:0.7, w:8.6, h:0.3, fontSize:12, color:C.onDark });
  T(s, '언덕 위 우리동네', { x:0.7, y:1.4, w:8.6, h:0.95, fontSize:46, bold:true, color:C.white });
  T(s, '경사 반영 이동약자 접근성 지도', { x:0.7, y:2.35, w:8.6, h:0.5, fontSize:22, color:C.white });
  bar(s, 0.7, 3.2, 0.42); T(s, '지도앱의 7분이, 누군가에게는 14분입니다.', { x:0.92, y:3.2, w:8, h:0.42, fontSize:18, bold:true, color:C.white, valign:'middle' });
  T(s, `서비스명 evenly   |   팀명 ${team()}   |   2026.10`, { x:0.7, y:4.8, w:7, h:0.3, fontSize:12, color:C.onDark });
  if (FAKE) T(s, '검토용 초안: 결과 숫자는 시나리오 확인을 위한 가상 값입니다. 제출 전 실제 분석 결과로 바꿔야 합니다.', { x:0.7, y:4.3, w:8.6, h:0.3, fontSize:11, bold:true, color:'F0A08A' });
  if (REH) T(s, `완성본 청사진: ${Q('V6.scope', '관악구')} 공개 대역(리허설) 값으로 채운 검토판입니다. 실제 결과가 아니며 제출하지 않습니다.`, { x:0.7, y:4.3, w:8.6, h:0.3, fontSize:11, bold:true, color:'F0A08A' });
  reviewTag(s, true); }

// ── 2 한 장 요약 ──
{ const s = base('한 장 요약', '언덕 부담을 숫자로 만들어, 다섯 가지 결정에 씁니다');
  const st = [['아이디어','지도앱 도보 시간에 "오르막"을 더하면, 평지 지도가 숨긴 동네가 보입니다'],['데이터','LX 수치지형도·DEM·필지에 건축물대장, SKT·KCB·교통사고를 더합니다'],['분석 결과','5개 구 집집마다 언덕 부담 지수, 우선 검토 후보, 시설 효과를 계산합니다'],['활용','시설 입지부터 돌봄·교통·길안내까지, 같은 지도 하나로 결정합니다']];
  st.forEach((t, i) => { const x = 0.6 + i*2.22;
    T(s, String(i+1), { x, y:1.45, w:0.6, h:0.6, fontSize:30, bold:true, color: i==3 ? C.acc : C.ink });
    T(s, t[0], { x, y:2.08, w:2.0, h:0.32, fontSize:14, bold:true, color: i==3 ? C.acc : C.ink });
    T(s, t[1], { x, y:2.45, w:1.98, h:1.15, fontSize:12, color:C.text, lineSpacingMultiple:1.15 });
    if (i<3) vr(s, x+2.1, 1.5, 2.05); });
  hr(s, 0.6, 3.8, 8.8, C.ink, 1.25);
  T(s, '이렇게 씁니다', { x:0.6, y:3.92, w:2, h:0.3, fontSize:11, bold:true, color:C.muted });
  const uses = ['이동편의시설 입지','방문돌봄 대상','정류장 검토','보행로·계단 정비','길안내 서비스'];
  uses.forEach((u, i) => { const x = 0.6 + i*1.76; T(s, u, { x, y:4.3, w:1.7, h:0.4, fontSize:13, bold:true, color: i==0 ? C.acc : C.ink }); if (i<4) vr(s, x+1.66, 4.3, 0.4); });
  src(s, '핵심 활용은 이동편의시설 입지, 나머지는 같은 지도를 다른 부서가 쓰는 확장 활용입니다'); }

// ── 3 같은 길, 다른 시간 ──
{ const s = base('한 사람의 귀갓길', '같은 450m, 다른 시간'); tag(s, 4.85, 0.82, '예시 계산', 1.0);
  s.addImage({ path:img('profile.png'), x:0.5, y:1.4, w:5.7, h:2.76 });
  [['7분','지도앱 도보 안내','평지 · 성인 보행속도',C.muted],['9분','고령자 보행속도','경사는 아직 반영 전',C.ink],['14분','오르막 경사까지','지도앱 안내의 2배',C.acc]].forEach((r, i) => {
    const y = 1.45 + i*0.93; if (i) hr(s, 6.5, y-0.06, 2.9);
    T(s, r[0], { x:6.5, y, w:1.25, h:0.7, fontSize:i==2?32:28, bold:true, color:r[3], valign:'middle' });
    T(s, r[1], { x:7.8, y:y+0.08, w:1.7, h:0.3, fontSize:12.5, bold:true, color:C.ink });
    T(s, r[2], { x:7.8, y:y+0.38, w:1.7, h:0.28, fontSize:11, color:C.muted }); });
  takeaway(s, '집은 언덕 위, 약국은 언덕 아래. 돌아오는 길은 고도 54m를 올라야 합니다.', 4.5);
  src(s, '예시 계산: 성인 1.1m/s, 고령자 0.8m/s, 평균 경사 12%, Tobler 보행함수. 현장 실측 구간 값으로 교체 예정'); }

// ── 4 페르소나 ──
{ const s = base('한 사람의 귀갓길', '김순자 할머니(78)의 "약 받는 날"'); tag(s, 6.05, 0.82, '가상 인물', 1.0);
  [['09:30','집을 나선다','내리막이라 금방이지만, 넘어질까 무릎이 긴장한다.'],['09:40','약국 도착','3주치 약봉투가 생각보다 무겁다.'],['09:50','돌아오는 길','오르막 중간에 두 번 멈춘다. 담벼락이 쉼터다.'],['다음 달','약 받는 날을 미룬다','비·눈·폭염인 날은 나가지 않는다.']].forEach((st, i) => {
    const x = 0.6 + i*2.22, hot = i==3; hr(s, x, 1.5, 2.0, hot ? C.acc : C.ink, 2);
    T(s, st[0], { x, y:1.65, w:2.0, h:0.45, fontSize:20, bold:true, color: hot ? C.acc : C.ink });
    T(s, st[1], { x, y:2.15, w:2.0, h:0.35, fontSize:13.5, bold:true, color:C.ink });
    T(s, st[2], { x, y:2.55, w:1.95, h:1.2, fontSize:12, color:C.text, lineSpacingMultiple:1.15 }); });
  takeaway(s, '문제는 거리가 아니라 "돌아오는 오르막"이고, 이 부담은 지금 어떤 지도에도 없습니다.', 4.1);
  src(s, '실제 보도·연구 사례를 바탕으로 구성한 가상 인물입니다'); }

// ── 5 규모 ──
{ const s = base('문제의 규모', '한 사람의 이야기가 아닙니다');
  [['31%','서울 면적 중 구릉지','저층 주거가 밀집하고 인프라 설치가 어려운 지형'],['20.43%','서울 65세 이상 인구 비중','2025년 처음으로 20%를 넘었습니다'],['51곳','구릉지 고령자 이동취약지역','거주 고령인구 16,773명, 25개 구 중 17개 구'],['420m','후기고령자 평균 이동거리','75세 이상 어르신이 걷는 거리의 한계']].forEach((st, i) => {
    const x = 0.6 + (i%2)*4.5, y = 1.45 + Math.floor(i/2)*1.45;
    if (i%2) vr(s, x-0.25, y, 1.2); if (i>=2) hr(s, x, y-0.12, 4.2);
    T(s, st[0], { x, y, w:2.1, h:0.75, fontSize:st[0].length>5?30:36, bold:true, color:C.acc, valign:'middle' });
    T(s, st[1], { x:x+2.15, y:y+0.08, w:2.0, h:0.62, fontSize:13, bold:true, color:C.ink, valign:'middle' });
    T(s, st[2], { x, y:y+0.8, w:4.1, h:0.32, fontSize:11.5, color:C.muted }); });
  takeaway(s, '서울의 3분의 1이 언덕이고, 5명 중 1명이 어르신입니다.', 4.5);
  src(s, '출처: 구릉지 고령자 이동취약지역 분석 연구(한국공간디자인학회 논문집) / 행정안전부 2025 주민등록 인구통계 / 이소민·오성훈(2025) 토지주택연구 16(1)'); }

// ── 6 현장 사례 ──
{ const s = base('실제 사례', '지도와 현실의 차이는 이미 현장에서 확인됩니다');
  [['중구 신당동','대현산배수지공원','계단 190개, 약 110m. 휠체어는 약 770m를 돌아가야 했습니다.','모노레일 설치, 3~4분'],['종로구 숭인동','창신역 일대 계단','길이 115m, 경사 30도 이상. 학생 통학로이기도 합니다.','경사형 엘리베이터, 2027 준공 목표'],['관악구 봉천동','비안어린이공원 인근','가파른 계단을 피해 주민들이 200m 이상 돌아갔습니다.','수직 엘리베이터·데크길 추진']].forEach((c, i) => {
    const x = 0.6 + i*2.97; hr(s, x, 1.5, 2.75, C.ink, 2);
    T(s, c[0], { x, y:1.62, w:2.7, h:0.28, fontSize:11, bold:true, color:C.acc });
    T(s, c[1], { x, y:1.92, w:2.7, h:0.36, fontSize:14.5, bold:true, color:C.ink });
    T(s, c[2], { x, y:2.35, w:2.7, h:0.95, fontSize:12, color:C.text, lineSpacingMultiple:1.12 });
    T(s, c[3], { x, y:3.32, w:2.7, h:0.3, fontSize:11.5, bold:true, color:C.teal }); });
  hr(s, 0.6, 3.85, 8.8);
  T(s, [{ text:'110m', options:{ color:C.ink } }, { text:'  →  ', options:{ color:C.muted } }, { text:'770m', options:{ color:C.acc } }], { x:0.6, y:4.0, w:4.2, h:0.75, fontSize:28, bold:true, valign:'middle' });
  T(s, '휠체어에게 같은 목적지는 약 7배 멀었습니다. 이런 곳을 미리 찾아낼 도구가 필요합니다.', { x:4.95, y:4.0, w:4.45, h:0.75, fontSize:13, bold:true, color:C.ink, valign:'middle' });
  src(s, '출처: 서울시 구릉지 이동편의 개선사업 보도자료(2020.11) / 내 손안에 서울(2025.06.13)'); }

// ── 7 정책 흐름 ──
{ const s = base('정책 흐름', '서울시는 이미 200억 원을 들여, 다음 후보지를 찾고 있습니다', { tsize:21 });
  hr(s, 0.6, 2.2, 8.8, C.ink, 1.25);
  [['2018','후암동 108하늘계단, 서울 첫 경사형 엘리베이터'],['2020','주민공모로 모노레일·엘리베이터 대상지 선정'],['2024','자치구 전수조사로 급경사 계단 후보 25곳 발굴'],['2025','타당성 조사 뒤 5곳 선정, 총 200억 원'],['2026','종로구 무악동 85계단 공모 선정, 40억 원'],['2027','2025년 선정 5곳 준공 목표']].forEach((t, i) => {
    const x = 0.6 + i*1.48, hot = (i==2||i==4);
    s.addShape(pres.shapes.RECTANGLE, { x, y:2.13, w:0.14, h:0.14, fill:{color: hot?C.acc:C.ink}, line:{color: hot?C.acc:C.ink} });
    T(s, t[0], { x, y:1.55, w:1.3, h:0.45, fontSize:19, bold:true, color: hot?C.acc:C.ink });
    T(s, t[1], { x, y:2.45, w:1.35, h:1.35, fontSize:11.5, color:C.text, lineSpacingMultiple:1.12 }); });
  takeaway(s, '예산과 정책은 움직이고 있습니다. 필요한 것은 다음 후보지를 같은 기준으로 비교하고 효과를 미리 계산할 도구입니다.', 4.2);
  src(s, '출처: 내 손안에 서울(2023), 서울시 보도자료(2020.11, 2025.06), 아주경제(2025.02.20), 경향신문(2026.02.24)'); }

// ── 8 문제 정의 ──
{ const s = base('문제 정의', '서울시는 가파른 "계단"을 찾았고, 우리는 가파른 "일상"을 찾습니다', { tsize:20 });
  T(s, '지금의 발굴 기준 (2024 전수조사)', { x:0.6, y:1.5, w:4.1, h:0.3, fontSize:12.5, bold:true, color:C.muted });
  T(s, '경사 20도·폭 2.5m·길이 30m 이상 계단 + 민원', { x:0.6, y:1.82, w:4.1, h:0.3, fontSize:12.5, bold:true, color:C.ink });
  hr(s, 0.6, 2.25, 4.0);
  T(s, '이 기준 밖에 남는 것', { x:0.6, y:2.38, w:4, h:0.28, fontSize:11.5, bold:true, color:C.acc });
  ['계단이 없는 급경사 도로','폭 2.5m 미만의 좁은 계단','그 길을 쓰는 사람과 목적지(병원·약국·역)'].forEach((l, i) => {
    T(s, String(i+1), { x:0.6, y:2.75+i*0.6, w:0.35, h:0.45, fontSize:18, bold:true, color:C.muted, valign:'middle' });
    T(s, l, { x:1.0, y:2.75+i*0.6, w:3.6, h:0.45, fontSize:12.5, color:C.text, valign:'middle' }); });
  box(s, 5.0, 1.42, 4.5, 3.6, C.ink);
  T(s, 'evenly 의 기준 (사람 중심)', { x:5.3, y:1.55, w:4, h:0.3, fontSize:12.5, bold:true, color:C.acc });
  T(s, '집에서 필수시설까지 실제 걷는 길의 부담', { x:5.3, y:1.87, w:4, h:0.3, fontSize:12.5, bold:true, color:C.white });
  ['계단·급경사 도로를 한 잣대(언덕 부담 지수)로 비교','집집마다 병원·약국·역까지 오르막 부담 계산','설치 전, 수혜 인원과 단축 시간을 미리 계산'].forEach((l, i) => {
    T(s, String(i+1), { x:5.3, y:2.75+i*0.6, w:0.35, h:0.45, fontSize:18, bold:true, color:C.acc, valign:'middle' });
    T(s, l, { x:5.7, y:2.75+i*0.6, w:3.65, h:0.5, fontSize:12.5, color:C.white, valign:'middle' }); });
  src(s, 'evenly 는 서울시 방식을 대체하지 않고, 다음 후보지 발굴과 비교를 보완합니다 / 출처: 서울시 보도자료(2025.06), 아주경제(2025.02.20)'); }

// ── 9 비교표 ──
{ const s = base('기존 방법·서비스와의 차이', '기존 방법과 서비스가 보지 못하는 것을 채웁니다');
  etable(s, [['구분','누가 쓰나','무엇을 보나','결과물','보지 못하는 것'],
    [B('서울시 전수조사 (2024)'),'서울시·자치구','계단 경사·폭·길이, 민원','후보지 25곳','계단 없는 급경사 길, 거주자·목적지'],
    [B('서울동행맵 (2024.11~)'),'시민 개인','단차·경사·보도폭·엘리베이터','지금 가는 길 안내','지역 우선순위, 시설 효과'],
    [B('선행연구'),'연구자','지역 단위 취약지역, 이동거리 한계','취약지역 51곳','건물 단위 경로 부담, 시설 효과'],
    [B('evenly',{color:C.acc}),B('서울시·자치구 정책 담당'),B('집→필수시설 실제 경로의 오르막·계단 부담'),B('언덕 부담 지도, 우선 후보, 시설 1기 효과'),{text:'지반·규제·보상 (현장 조사 단계)',options:{color:C.muted}}]],
    { colW:[1.65,1.45,2.2,1.75,1.75], rowH:[0.38,0.62,0.56,0.56,0.7] });
  takeaway(s, '동행맵이 "오늘 가는 길"을 안내한다면, evenly 는 "어디에 길을 새로 낼지"를 정합니다.', 4.55);
  src(s, '출처: 서울시 교통정보(2024.11) 서울동행맵, 서울시 보도자료(2025.06), 선행연구는 부록 1'); }

// ── 10 데이터 ──
{ const s = base('활용 데이터', '길·높이·집: 미개방데이터 3종을 하나의 보행 모델로 잇습니다', { tsize:20 });
  [['길','수치지형도 1:5,000','2024.11','도로중심선·계단·건물, 자동차전용 속성'],['높이','DEM 5M_수도권','2024.11 (2021 기준)','5m 격자 고도'],['집의 위치','국토정보필지 + 건물 용도','2024~2026','단독·공동주택 구분, 필지로 대장 교차 확인']].forEach((d, i) => {
    const x = 0.6 + i*2.97; hr(s, x, 1.5, 2.75, C.ink, 2);
    T(s, d[0], { x, y:1.6, w:2.7, h:0.55, fontSize:24, bold:true, color:C.acc });
    T(s, d[1], { x, y:2.18, w:2.7, h:0.32, fontSize:13.5, bold:true, color:C.ink });
    T(s, 'LX 미개방 · ' + d[2], { x, y:2.5, w:2.7, h:0.27, fontSize:10.5, color:C.muted });
    T(s, d[3], { x, y:2.8, w:2.7, h:0.3, fontSize:12, color:C.text }); });
  hr(s, 0.6, 3.38, 8.8);
  bar(s, 0.6, 3.55, 1.25); T(s, '상호제공데이터 (가점)', { x:0.82, y:3.55, w:3.9, h:0.3, fontSize:12.5, bold:true, color:C.acc });
  T(s, [{ text:'SKT 60세 이상 유동인구 · KCB 행정동 소득 · 도로교통공단 교통사고', options:{ bold:true, breakLine:true, color:C.ink } }, { text:'외출·소득·안전과 언덕 부담의 관계 (보조 관찰)', options:{ color:C.muted } }], { x:0.82, y:3.88, w:3.9, h:0.95, fontSize:12, lineSpacingMultiple:1.12 });
  bar(s, 5.2, 3.55, 1.25, C.ink); T(s, '공공데이터', { x:5.42, y:3.55, w:4, h:0.3, fontSize:12.5, bold:true, color:C.ink });
  T(s, [{ text:'건축물대장(건물 용도·층수), 약국·지하철 엘리베이터 위치', options:{ bold:true, breakLine:true, color:C.ink } }, { text:'고령·장애인·독거노인 인구, 서울 도보 네트워크(대조군)', options:{ color:C.muted } }], { x:5.42, y:3.88, w:4.0, h:0.95, fontSize:12, lineSpacingMultiple:1.12 });
  src(s, '전체 목록과 기간은 부록 1'); }

// ── 11 방법 ──
{ const s = base('분석 방법', '다섯 단계로 "체감 거리"를 계산합니다');
  [['길 만들기','도로중심선·계단을 30m 링크 네트워크로'],['높이 입히기','DEM 5m로 링크마다 오르막·내리막 경사'],['집과 목적지','주거 건물 ↔ 병원·약국·지하철 엘리베이터'],['사람별 시간','고령자: 경사 보정 속도 / 휠체어: 계단 불가'],['지수와 효과','언덕 부담 지수, 우선 후보, 시설 시뮬레이션']].forEach((t, i) => {
    const x = 0.6 + i*1.78, hot = i==4; hr(s, x, 1.5, 1.6, hot ? C.acc : C.ink, 2);
    T(s, String(i+1), { x, y:1.62, w:0.6, h:0.6, fontSize:28, bold:true, color: hot ? C.acc : C.ink });
    T(s, t[0], { x, y:2.25, w:1.6, h:0.35, fontSize:13.5, bold:true, color: hot ? C.acc : C.ink });
    T(s, t[1], { x, y:2.65, w:1.58, h:1.1, fontSize:12, color:C.text, lineSpacingMultiple:1.12 }); });
  takeaway(s, '안심구역 안에서 자동 점검(setup·check) 후 실행하고, 격자·행정동 집계만 반출합니다.', 4.15);
  src(s, '전처리와 경사 모델은 부록 2, 가정값과 민감도는 부록 3'); }

// ── 12 HBI ──
{ const s = base('핵심 지표', '언덕 부담 지수: 평지보다 몇 배 걸리는가');
  box(s, 0.6, 1.42, 8.8, 0.95, C.ink);
  T(s, [{ text:'HBI', options:{ color:C.acc } }, { text:'  =  경사 반영 왕복 시간  ÷  평지 가정 왕복 시간', options:{ color:C.white } }], { x:0.9, y:1.48, w:8.3, h:0.5, fontSize:21, bold:true, valign:'middle' });
  T(s, '같은 사람이, 같은 집에서, 같은 목적지까지. 1.0이면 평지와 같습니다.', { x:0.9, y:1.98, w:8.3, h:0.3, fontSize:11.5, color:C.onDark });
  [[`${HB()} 미만`,'평지 수준',C.r1],[`HBI ${HB()} 이상`,'체감 부담',C.r2],[`왕복 +${RMIN()}분`,'고립 위험',C.r3]].forEach((b, i) => {   // 10/12: 고립 위험은 HBI 가 아니라 왕복 추가 시간
    const x = 0.6 + i*1.42; s.addShape(pres.shapes.RECTANGLE, { x, y:2.65, w:1.38, h:0.14, fill:{color:b[2]}, line:{color:b[2]} });
    T(s, b[0], { x, y:2.85, w:1.38, h:0.32, fontSize:13.5, bold:true, color:C.ink });
    T(s, b[1], { x, y:3.17, w:1.38, h:0.3, fontSize:12, color:C.muted }); });
  vr(s, 5.05, 2.6, 2.3);
  T(s, '예시: 김순자 할머니의 귀갓길 (편도)', { x:5.3, y:2.62, w:4.1, h:0.3, fontSize:11.5, bold:true, color:C.muted });
  T(s, [{ text:'14.3분', options:{ color:C.acc, bold:true } }, { text:'  ÷  9.4분  =  ', options:{ color:C.ink } }, { text:'1.52배', options:{ color:C.acc, bold:true } }], { x:5.3, y:2.95, w:4.1, h:0.55, fontSize:20, valign:'middle' });
  T(s, '"분"이라 누구나 이해하고, 시설 설치 전후를 같은 잣대로 비교할 수 있습니다. 비율이라 보행속도 가정에도 덜 흔들립니다.', { x:5.3, y:3.6, w:4.1, h:1.1, fontSize:12, color:C.text, lineSpacingMultiple:1.12 });
  // [v6.3] 고립 위험 문턱의 근거 (5장 420m 와 같은 출처, 고령자 속도 0.8m/s = 모델 기본값)
  T(s, [{ text:`왕복 +${RMIN()}분의 근거  `, options:{ bold:true, color:C.ink } }, { text:'후기고령자 평균 이동거리 420m ÷ 어르신 걸음 0.8m/s ≈ 편도 9분. 왕복 10분이 더 걸리면 하루에 감당하는 거리를 한 번 더 걷는 셈입니다.', options:{ color:C.text } }],
    { x:0.6, y:3.62, w:4.3, h:0.95, fontSize:11, lineSpacingMultiple:1.12 });
  src(s, `체감 부담은 HBI(배수), 고립 위험은 왕복 추가 시간(분)으로 판정 / 문턱(${HB()}·${RMIN()}분)은 실제 관악 결과로 확정`); }

// ── 13 안심구역 ──
{ const s = base('데이터안심구역 분석', '데이터안심구역에서 직접 분석했습니다');
  [['1차 방문','2026.10.02','자료 구조 점검, 수도권 shp 확보, 실데이터로 분석 코드 실행'],['2차 방문',V('V6.13.visit2','2026.10.___'),'관악구 분석, 봉천 시설 시뮬레이션, 결과 반출'],['3차 방문',V('V6.13.visit3','2026.10.___'),'5개 구 확대 분석 (자료 수령 시)']].forEach((v, i) => {
    const x = 0.6 + i*2.97; hr(s, x, 1.5, 2.75, i==0 ? C.ink : C.acc, 2);
    T(s, v[0], { x, y:1.62, w:2.7, h:0.36, fontSize:15, bold:true, color: i==0 ? C.ink : C.acc });
    T(s, v[1], { x, y:2.0, w:2.7, h:0.3, fontSize:12, bold:true, color: v[1].includes('__') ? C.accD : C.muted });
    T(s, v[2], { x, y:2.36, w:2.7, h:0.9, fontSize:12, color:C.text, lineSpacingMultiple:1.12 }); });
  hr(s, 0.6, 3.45, 8.8);
  bar(s, 0.6, 3.62, 1.2, C.ink); T(s, '안심구역 밖 사전 준비', { x:0.82, y:3.62, w:3.9, h:0.3, fontSize:12.5, bold:true, color:C.ink });
  T(s, '공개데이터로 코드를 미리 시험하고, 자료 구조가 달라도 스스로 맞추는 자동 점검 도구를 준비', { x:0.82, y:3.95, w:3.9, h:0.85, fontSize:12, color:C.text });
  bar(s, 5.2, 3.62, 1.2); T(s, '반출 원칙', { x:5.42, y:3.62, w:4, h:0.3, fontSize:12.5, bold:true, color:C.acc });
  T(s, '250m 격자·행정동 집계만 반출, 건물 5개 미만 칸 제외. 건물·필지 단위 결과와 소유 정보는 반출하지 않음', { x:5.42, y:3.95, w:4.0, h:0.85, fontSize:12, color:C.text });
  if (!(has('V6.13.visit2') && has('V6.13.visit3'))) src(s, '방문일은 실제 일자로 기입'); }   // [10/13] 작성 안내 줄: 방문일을 다 넣으면 빠짐

// ── 14 결과 ① 사각지대 ──
{ const s = base('분석 결과 · 사각지대' + ((REH || FALLBACK) ? ' · ' + SCOPE : ''), () => FALLBACK
    ? `관악 일대 건물의 약 ${V('V6.fb.share13')}%가 평지보다 ${Math.round((Number(HB()) - 1) * 100)}% 넘게 더 걸립니다`   // [10/13] 대비책 판: 1차 HBI 1.3 이상 비율
    : `평지 지도에서 "가까운 동네"의 ${V('V6.14.near_burden')}%가 실제로는 ${Math.round((Number(HB()) - 1) * 100)}% 넘게 더 걸립니다`, { tsize:19 });
  const m = IMG('V6.map');
  if (m) s.addImage({ path:m, x:0.6, y:1.42, w:5.3, h:3.53 });
  else slot(s, 0.6, 1.42, 5.3, 3.53, `결과 지도 자리\n${SCOPE} 250m 격자 · 언덕 부담 지수`, 'V6.map');
  stat(s, 6.25, 1.45, 3.2, Q('V6.14.risk_label', `고립 위험(왕복 +${RMIN()}분) 건물`), V('V6.14.risk_bld'), { size:17 });
  hr(s, 6.25, 2.32, 3.2);
  stat(s, 6.25, 2.42, 3.2, '그 집에 사는 어르신 (추정)', V('V6.14.elderly'), { size:17 });
  hr(s, 6.25, 3.29, 3.2);
  stat(s, 6.25, 3.39, 3.2, '부담이 가장 큰 동', V('V6.14.top_dong'), { size:17 });
  bar(s, 6.25, 4.38, 0.6); T(s, '거리만 보는 지도에서는 이 동네들이 "가깝다"고 나옵니다.', { x:6.45, y:4.38, w:3.0, h:0.6, fontSize:12, bold:true, color:C.ink, valign:'middle' });
  const nt = has('V6.14.elderly_note') ? ` (${R.fields['V6.14.elderly_note'].value})` : '';
  src(s, FALLBACK ? `제목: ${Q('V6.fb.limits', '1차 반출(10/2) 값')} / 지도·건물·어르신·동 = 2차 분석 결과 반영 예정`
    : (REH ? '공개 대역(리허설) 값 · ' : '') + `어르신은 행정동 65세 이상을 주거 연면적으로 배분한 추정${nt}`); }

// ── 15 현장실측 ──
{ const s = base('현장실측 · 관악구', '직접 걸어서 확인했습니다');
  // [10/13] 사진: tools/prep_photos.py 가 docs/photos/15_1~15_4 를 바로 세우고 촬영 정보(GPS)를 지운 사본 docs/photos/_deck/15_N.jpg 가 있으면 넣고
  //   (가운데를 잘라 칸에 맞춤), 없으면 자리 표시. 원본(EXIF 남음)은 읽지 않음. 사진은 git 에 넣지 않음 (얼굴·번지 표지 제외)
  ['봉천동 선정지 계단','봉천역 → 언덕 오르막','도림천 산책로 (평지)','낙성대역 → 언덕'].forEach((p, i) => { const x = 0.6 + (i%2)*2.25, y = 1.45 + Math.floor(i/2)*1.6;
    const ph = [`../docs/photos/_deck/15_${i+1}.jpg`].find(f => fs.existsSync(f));
    if (!ph) return slot(s, x, y, 2.1, 1.45, '사진 자리\n' + p);
    s.addImage(Object.assign({ path:ph, x, y }, photoCover(ph, 2.1, 1.45)));
    box(s, x, y+1.17, 2.1, 0.28, C.white); T(s, p, { x:x+0.08, y:y+1.17, w:1.94, h:0.28, fontSize:9.5, color:C.ink, valign:'middle' }); });
  const rn = ['계단 · 봉천 선정지','오르막 · 봉천역','평지 · 도림천','오르막 · 낙성대'];   // 10/12 청사진: prepare 의 V6.15.<i> 도 관악 네 구간 (현장실측①~④)
  const r15 = rn.map((n, i) => [V(`V6.15.${i}.app`), V(`V6.15.${i}.meas`), V(`V6.15.${i}.model`)]);
  etable(s, [['구간','지도앱','실측','모델']].concat(rn.map((n, i) => FALLBACK && r15[i].every(v => v === FB_TEXT)
      ? [B(n), { text:FB_TEXT, options:{ colspan:3, align:'center' } }]          // [10/13] 대비책 판: 세 칸을 하나로
      : [B(n)].concat(r15[i]))), { x:5.25, w:4.15, colW:[1.6,0.85,0.85,0.85], rowH:[0.36,0.44,0.44,0.44,0.44] });
  bar(s, 5.25, 3.95, 0.95);
  T(s, [{ text:'봉천 선정지 계단: 오름 3회 · 내림 1회', options:{ bold:true, color:C.ink, breakLine:true } }, { text:'성인이 평소 걸음으로 측정, 고도계 앱으로 높이 차 기록', options:{ color:C.muted } }], { x:5.47, y:3.95, w:3.95, h:0.95, fontSize:12, valign:'middle' });
  src(s, `관악 실측 기록지 기준 / 측정일 ${V('V6.15.date', '2026.10.___')} / 사람 얼굴·집 안·번지 표지는 찍지 않음`); }

// ── 16 결과 ② 신뢰 ──
{ const s = base('분석 결과 · 믿을 수 있는가', '서울시 선정지를 다시 찾아내고, 고해상도 높이 없이는 결과가 달라집니다', { tsize:19 });
  T(s, '현장과 맞는가', { x:0.6, y:1.45, w:4, h:0.32, fontSize:13.5, bold:true, color:C.ink }); hr(s, 0.6, 1.82, 4.1, C.ink, 1.25);
  [[Q('V6.16.site_label', '서울시 2025 선정지 5곳 중 상위 10%'), V('V6.16.site')], [Q('V6.16.wheel_label', '대현산 휠체어 우회 (서울시: 약 770m)'), V('V6.16.wheel')], ['현장실측 4구간, 예측 vs 실측', V('V6.16.meas_r')]].forEach((r, i) => { stat(s, 0.6, 1.95+i*0.8, 4.1, r[0], r[1], { size:18 }); });
  T(s, 'LX 데이터가 왜 필요한가', { x:5.3, y:1.45, w:4, h:0.32, fontSize:13.5, bold:true, color:C.acc }); hr(s, 5.3, 1.82, 4.1, C.acc, 1.25);
  [['높이(DEM 5m)를 빼면 바뀌는 상위 10%', V('V6.16.dem_top10')], ['보행 판단 속성 (자동차전용·단독/공동 구분)', '공개판에 없음'], ['공개데이터 대조 (공개 도보망 + 30m 지형)', V('V6.16.pub_miss')]].forEach((r, i) => { stat(s, 5.3, 1.95+i*0.8, 4.1, r[0], r[1], { size:18, color:C.acc }); });
  takeaway(s, '5m 높이와 보행 판단용 현행 속성은 LX 데이터에 있습니다. 공개 연속수치지형도에는 자동차전용 칸이 없습니다.', 4.55);
  const notes16 = [has('V6.16.wheel_note') ? R.fields['V6.16.wheel_note'].value : null, has('V6.16.daehyun_note') ? R.fields['V6.16.daehyun_note'].value : null].filter(Boolean).join(' · ');
  src(s, FALLBACK ? `선정지 백분위: ${Q('V6.fb.limits', '1차 반출(10/2) 값')}`
    : (REH ? '공개 대역(리허설) 값 · ' : '') + `선정지 백분위: 반경 300m 원 평균 비교 · 계단을 빼면 휠체어 시간 과소 계산 ${V('V6.16.stairs')}` + (notes16 ? ' · ' + notes16 : '')); }

// ── 17 우선 검토 후보 ──
const NCAND = () => V('V6.17.n_cand');
// [v6.3] 09 후보 자동 결과(intervention_candidates.csv)가 있으면 후보·선정지 비교표 (후보별 수혜·1억 원당·규모별 처방), 없으면 v6.2 격자 표
const CANDT = (R.tables['V6.17.cand'] && R.tables['V6.17.cand'].rows && R.tables['V6.17.cand'].rows.length) ? R.tables['V6.17.cand'].rows : null;
if (CANDT) {
  const s = base('정책 제안' + ((REH || FALLBACK) ? ' · ' + SCOPE : ''), () => `어디부터 무엇을: 자동 후보 ${CANDT.filter(r => r.kind === '후보').length}곳 중 시설 검토 ${V('V6.17.n_facility')}`);
  const rows = [['위치', '고립 위험 집', '시설 (자동 배치)', '수혜 (고령자)', '1억 원당', '처방']];
  const cw = [1.75, 0.95, 2.1, 1.25, 0.85, 1.9];
  const unit = v => (v === '' || v === null || v === undefined) ? '-' : (/^[0-9.]+$/.test(String(v)) ? `${v}채` : String(v));
  CANDT.forEach(r => {
    const site = r.kind !== '후보', fac = r.rx === '시설 검토';
    const o = site ? { color:C.muted } : {};
    rows.push([B(site ? `선정지 · ${r.name.split(' ')[0]}` : `${r.name.replace('후보', '후보 ')} · ${r.loc.split(' ').pop()}`, o), { text:unit(r.n_risk), options:o },
               { text:r.fac, options:Object.assign({ fontSize:9.5 }, o) }, { text:unit(r.benefit) + ((r.elder30 !== '' && r.elder30 !== undefined && r.elder30 !== null) ? ` (${r.elder30})` : ''), options:o },
               { text:(r.per100m === '' || r.per100m === null) ? '-' : `${Number(r.per100m).toFixed(1)}채`, options:o },
               B({ '난간·쉼터·계단 정비 + 방문돌봄':'정비 + 방문돌봄' }[r.rx] || r.rx, fac ? { color:C.teal } : { color:C.muted, bold:false })]);
  });
  etable(s, rows, { colW:cw, rowH:[0.34].concat(CANDT.map(() => 0.36)), fontSize:10.5 });
  bar(s, 0.6, 4.25, 0.75);
  T(s, [{ text:'처방 규칙  ', options:{ bold:true, color:C.ink } }, { text:Q('V6.17.cand_rule', '500m 안 기존 시설 → 기존 시설 연계 / 고립 위험 30채 이상이고 1억 원당 1채 이상 → 시설 검토 / 그 밖 → 난간·쉼터·계단 정비 + 방문돌봄 (시설 1곳 40억 원 가정)'), options:{ color:C.text } }],
    { x:0.82, y:4.25, w:8.6, h:0.75, fontSize:10.5, valign:'middle' });
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + '후보 = 고립 위험 집이 가장 많은 250m 격자에서 그 집들의 길이 가장 많이 지나는 가파른 구간에 시설을 자동 배치 · 수혜 = 고령자 왕복 30초 또는 휠체어 1분 이상 단축(의료), 괄호 = 그중 고령자 30초 이상 · 시설 양 끝 좌표는 반출하지 않음');
} else { const s = base('정책 제안' + ((REH || FALLBACK) ? ' · ' + SCOPE : ''), () => FALLBACK ? '어디부터 무엇을: 우선 검토 후보' : `어디부터 무엇을: 우선 검토 후보 ${NCAND()}곳`);
  // 10/12: 열 = 위치, 고립 위험 건물 수, 왕복 추가 시간 중앙값, 500m 안 기존 시설, 처방 방향 (규칙). 1억 원당 수혜는 20장(시뮬레이션한 시설)만
  const rows = [['위치', Q('V6.17.n_head', '고립 위험 건물'), '왕복 추가 (중앙값)', '500m 안 기존 시설', '처방 방향']];
  const cw = [2.35, 1.35, 1.45, 1.6, 2.05];
  const t = TBL('V6.17.rows');
  if (t) {
    t.forEach(r => { const o = r.meets ? {} : { color:C.muted };
      rows.push([B(r.loc, o), { text: r.n === null || r.n === undefined ? V('V6.17.n') : r.n, options:o }, { text: r.med === null || r.med === undefined ? V('V6.17.med') : r.med, options:o },
                 { text:r.fac, options:o }, B(r.rx, r.meets ? { color:C.teal } : { color:C.muted, bold:false })]); });
    etable(s, rows, { colW:cw, rowH:[0.36].concat(t.map(() => 0.4)), fontSize:10.5 });
  } else if (FALLBACK) {                          // [10/13] 대비책 판: 후보 표는 2차 분석에서
    rows.push([{ text:FB_TEXT, options:{ color:C.muted } }, '', '', '', '']);
    etable(s, rows, { colW:cw, rowH:[0.36,0.4], fontSize:10.5 });
  } else {
    for (let i = 0; i < 5; i++) rows.push(['___','___','___','___','___']);
    etable(s, rows, { colW:cw, rowH:[0.36,0.4,0.4,0.4,0.4,0.4], fontSize:10.5 }, 'tbl:V6.17.rows');
  }
  bar(s, 0.6, 4.15, 0.85);
  T(s, [{ text:'처방 규칙  ', options:{ bold:true, color:C.ink } }, { text:'고립 위험이 몰려 있고 500m 안 시설 없음 → 이동편의시설 검토 / 흩어져 있음 → 방문돌봄·계단 정비 / 시설 있음 → 기존 시설 연계 확인', options:{ color:C.text } }], { x:0.82, y:4.15, w:8.6, h:0.85, fontSize:11.5, valign:'middle' });
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + '후보 = 250m 격자 · 시설 효과는 실제로 시뮬레이션한 선정지(20장)에서만 계산' + (FALLBACK ? ' / 후보 표는 2차 분석 결과 반영 예정' : '')); }

// ── 18 활용 개요 ──
{ const s = base('활용 방안', '언덕 부담 지도 하나로, 다섯 가지 결정을 돕습니다');
  etable(s, [['결정','누가','무엇을 보고','결과물'],
    [B('핵심 · 이동편의시설 입지',{color:C.acc}),'서울시·자치구 균형발전','고립 위험 지역 + 설치 여지 + 시설 효과','우선 후보, 예산 대비 효과'],
    [B('확장 · 방문돌봄 대상'),'자치구 복지·보건소','고립 위험 × 독거노인·장애인 × 외출','방문 우선 동·가구 규모'],
    [B('확장 · 정류장 검토'),'자치구 교통','정류장까지 부담이 큰 주거지','정류장 신설·이전 검토 지역'],
    [B('확장 · 보행로·계단 정비'),'자치구 도로·건설','부담 큰 경로 위 계단·급경사 + 사고','난간·쉼터·열선 우선순위'],
    [B('확장 · 길안내 서비스'),'서울동행맵·지도앱','구간별 경사 비용, 지역 부담 지수','오르막 반영 도보 시간']],
    { colW:[2.35,1.95,2.6,1.9], rowH:[0.36,0.52,0.52,0.52,0.52,0.52] });
  takeaway(s, '같은 지도를 부서마다 다른 질문에 씁니다. 다음 장부터 하나씩 보여 드립니다.', 4.6); }

// ── 19 활용 ① 시설 입지 ──
{ const s = base('활용 · 이동편의시설 입지', '후보 발굴부터 예산 효과까지 한 번에 비교합니다', { tsize:21 });
  [['후보 발굴', FALLBACK ? '부담 상위 지역을 계단 기준 밖까지 포함해 찾음 → 후보는 2차 분석 결과 반영 예정'
                  : `부담 상위 지역을 계단 기준 밖까지 포함해 찾음 → 후보 ${NCAND()}곳 (${(sc => /^[가-힣]{1,3}구$/.test(sc) ? sc.slice(0, -1) : sc)(Q('V6.scope', '관악구'))})`],['설치 여지','후보 주변 필지의 도로·공원 비율로 1차 거르기'],['효과 비교','시설 1기당 수혜 가구, 평균 단축 분, 휠체어 신규 도달'],['예산 검토','1억 원당 수혜 건물(고령자·휠체어)로 우선순위']].forEach((t, i) => {
    const y = 1.45 + i*0.78; if (i) hr(s, 0.6, y-0.07, 4.7);
    T(s, String(i+1), { x:0.6, y, w:0.4, h:0.62, fontSize:20, bold:true, color: i==2 ? C.acc : C.ink, valign:'middle' });
    T(s, t[0], { x:1.05, y, w:1.25, h:0.62, fontSize:13, bold:true, color: i==2 ? C.acc : C.ink, valign:'middle' });
    T(s, t[1], { x:2.3, y, w:3.0, h:0.62, fontSize:11.5, color:C.text, valign:'middle' }); });
  const iso = IMG('V6.iso');
  if (iso) s.addImage({ path:iso, x:5.6, y:1.42, w:3.85, h:3.05, sizing:{ type:'contain', w:3.85, h:3.05 } });
  else slot(s, 5.6, 1.42, 3.85, 3.05, '등시선 그림 자리\n선정지에서 10분 안에 걸어 닿는 범위\n평지 가정 vs 경사 반영 vs 휠체어', 'V6.iso');
  takeaway(s, '"민원이 많은 곳"이 아니라 "효과가 큰 곳"부터 설치할 근거를 줍니다.', 4.62);
  src(s, '비용 가정: 1곳 약 40억 원 (서울시 5곳 200억 원, 무악동 1곳 40억 원)' + (iso ? ' / 등시선: 12_isochrone 결과 (봉천 선정지)' : '')); }

// ── 20 한 사람에게 돌아가는 변화 ──
if (Q('V6.20.mode', 'example') === 'wheel') {
  const s = base('한 곳에 돌아가는 변화 · 봉천동 선정지', '수직 엘리베이터 한 대가 바꾸는 봉천 계단의 휠체어 길', { tsize:20 });
  tag(s, 0.6, 1.42, REH ? '리허설 시뮬레이션' : '모델 시뮬레이션', 1.55);
  T(s, '지금 (휠체어)', { x:0.6, y:1.85, w:3.6, h:0.3, fontSize:12.5, bold:true, color:C.muted });
  T(s, V('V6.20.before'), { x:0.6, y:2.12, w:3.6, h:0.85, fontSize:46, bold:true, color:C.acc });
  T(s, `높이 ${V('V6.20.rise')} 계단을 피해 비탈길로 우회\n서울시 발표: 200m 이상 우회`, { x:0.6, y:2.98, w:3.6, h:0.6, fontSize:11.5, color:C.text, lineSpacingMultiple:1.12 });
  T(s, '→', { x:4.3, y:2.2, w:0.8, h:0.8, fontSize:36, color:C.muted, align:'center', valign:'middle' });
  box(s, 5.25, 1.42, 4.2, 2.2, C.ink);
  T(s, '계단 아래·위를 잇는 수직 엘리베이터 1기', { x:5.5, y:1.55, w:3.8, h:0.3, fontSize:12, bold:true, color:C.white });
  T(s, V('V6.20.after'), { x:5.5, y:2.05, w:3.8, h:0.85, fontSize:46, bold:true, color:C.white });
  T(s, `엘리베이터 통과 약 ${V('V6.20.pass')} (대기 포함)`, { x:5.5, y:2.95, w:3.8, h:0.4, fontSize:12, color:C.onDark });
  stat(s, 0.6, 3.82, 2.8, '휠체어 1분 이상 단축', `${V('V6.20.wheel_n')} (${Q('V6.20.tgt', '지하철역').replace(/\(.*\)/, '')} 기준)`, { size:17 });
  vr(s, 3.45, 3.85, 0.7);
  stat(s, 3.6, 3.82, 2.8, '고령자 30초 이상 단축', V('V6.20.elder30'), { size:17 });
  vr(s, 6.45, 3.85, 0.7);
  stat(s, 6.6, 3.82, 2.8, '1억 원당 수혜', V('V6.20.per100m'), { size:17 });
  takeaway(s, `짧은 계단 하나가 휠체어에게는 ${has('V6.20.before') ? R.fields['V6.20.before'].value + ' ' : '먼 길 '}우회입니다. 큰 계단(5개 구)에서는 고령자 시간 단축이 더해집니다.`, 4.68);
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + '수혜 = 고령자 30초 이상 또는 휠체어 1분 이상 단축(새 도달 포함) · 1곳 40억 원 가정'
    + (has('V6.16.wheel_note') ? ' · 설치 전 경로 1,000m 초과: 공개 대역 계단 면 왜곡일 수 있음' : ''));
} else {
  const s = base('한 사람에게 돌아가는 변화', '엘리베이터 한 대가 바꾸는 김순자 할머니의 귀갓길', { tsize:21 });
  tag(s, 0.6, 1.45, '예시 시뮬레이션', 1.45);
  T(s, '지금', { x:0.6, y:1.9, w:3.6, h:0.3, fontSize:12.5, bold:true, color:C.muted });
  T(s, '14분', { x:0.6, y:2.2, w:3.6, h:0.95, fontSize:50, bold:true, color:C.acc });
  T(s, 'HBI 1.52 · 오르막에서 두 번 쉼\n궂은 날은 약 받는 날을 미룸', { x:0.6, y:3.2, w:3.6, h:0.75, fontSize:12, color:C.text, lineSpacingMultiple:1.12 });
  T(s, '→', { x:4.3, y:2.3, w:0.8, h:0.8, fontSize:36, color:C.muted, align:'center', valign:'middle' });
  box(s, 5.25, 1.45, 4.2, 2.55, C.ink);
  T(s, '가장 가파른 150m 구간에 경사형 엘리베이터 1기', { x:5.5, y:1.6, w:3.8, h:0.3, fontSize:12, bold:true, color:C.white });
  T(s, '약 10분', { x:5.5, y:2.2, w:3.8, h:0.95, fontSize:50, bold:true, color:C.white });
  T(s, 'HBI 약 1.0 · 평지와 같은 부담\n쉬지 않고 집에 도착', { x:5.5, y:3.2, w:3.8, h:0.75, fontSize:12, color:C.onDark, lineSpacingMultiple:1.12 });
  takeaway(s, '이 계산을 집집마다 하면 "엘리베이터 한 대가 몇 명의 하루에서 몇 분을 돌려주는지" 설치 전에 알 수 있습니다.', 4.35);
  src(s, '예시 가정: 엘리베이터 대기 60초, 1m/s / 실제 선정지 계단 좌표로 시설 설치 시뮬레이션 후 교체'); }

// ── 21 활용 ② 방문돌봄 ──
{ const s = base('활용 · 방문돌봄 대상', '언덕 위 혼자 사는 어르신을 먼저 찾아갑니다', { tsize:22 });
  const q = [[0.6,1.45,'일반 돌봄','부담 낮음 · 돌봄 수요 많음',false],[2.75,1.45,'최우선 방문','부담 높음 · 돌봄 수요 많음',true],[0.6,2.95,'모니터링','부담 낮음 · 돌봄 수요 적음',false],[2.75,2.95,'이동 지원','부담 높음 · 돌봄 수요 적음',false]];
  q.forEach(v => { if (v[4]) box(s, v[0], v[1], 2.1, 1.42, C.acc); else box(s, v[0], v[1], 2.1, 1.42, C.white, C.line);
    T(s, v[2], { x:v[0]+0.15, y:v[1]+0.15, w:1.85, h:0.38, fontSize:14, bold:true, color: v[4] ? C.white : C.ink });
    T(s, v[3], { x:v[0]+0.15, y:v[1]+0.6, w:1.85, h:0.7, fontSize:11.5, color: v[4] ? C.white : C.muted }); });
  T(s, '돌봄 수요(독거노인·장애인) ↑', { x:0.6, y:4.43, w:2.2, h:0.25, fontSize:10, color:C.muted });
  T(s, '언덕 부담(HBI) →', { x:2.75, y:4.43, w:2.1, h:0.25, fontSize:10, color:C.muted, align:'right' });
  const sk21 = V('V6.21.skt'), kc21 = V('V6.21.kcb');      // 10/12 청사진: 외출(SKT)·소득(KCB)을 한 칸에 (둘 다 같은 대체 문구면 하나만. 둘 다 ___ 면 빈칸 둘: 누락 key 가 둘)
  const rk21 = has('V6.21.risk_dongs') ? R.fields['V6.21.risk_dongs'].value + '곳' : (FALLBACK ? V('V6.21.risk_dongs') : '-');   // 선택 키 (고위험 동 = 값이 0 보다 큰 동 중 상위 25%)
  [[`고립 위험(왕복 +${RMIN()}분) 건물이 많은 동`, rk21],(has('V6.21.alone_cells') || !has('V6.21.alone_top3')) ? ['고립 위험 격자 안 혼자 사는 어르신 (추정)', V('V6.21.alone_cells')]   // [v6.3] 동 통계 × 격자 안 주거 연면적 비율
      : ['고립 위험 상위 3개 동의 독거노인 수 (합, 공개 통계)', V('V6.21.alone_top3')],['외출(SKT)·소득(KCB)과 겹치는 동', (sk21 === kc21 && !runs(sk21)) ? sk21 : `${sk21} · ${kc21}`]].forEach((r, i) => { if (i) hr(s, 5.3, 1.45+i*0.88-0.08, 4.1); stat(s, 5.3, 1.45+i*0.88, 4.1, r[0], r[1], { size:18, laterInk:true }); });
  bar(s, 5.3, 4.2, 0.55); T(s, '보건소 방문건강관리, 돌봄SOS, 방문 약료의 대상 선정에 씁니다', { x:5.52, y:4.2, w:3.9, h:0.55, fontSize:12, bold:true, color:C.ink, valign:'middle' });
  src(s, (has('V6.21.alone_cells') ? `혼자 사는 어르신 = 서울시 동별 독거노인 × 고립 위험 격자 안 주거 연면적 비율 (${Q('V6.21.alone_cells_n', '추정을 낸 동')}) / `
         : (has('V6.21.alone_top3_dongs') ? `고립 위험 상위 3개 동: ${R.fields['V6.21.alone_top3_dongs'].value} (독거노인: 서울시 동별 통계) / ` : '')) + '외출·소득은 행정동 단위 보조 지표이며 상관 관찰입니다 / SKT는 60세 이상 기준'); }

// ── 22 활용 ③ 교통·보행 ──
{ const s = base('활용 · 교통·보행', '정류장과 계단, 어디부터 손볼지 정합니다', { tsize:22 });
  [[0.6,'마을버스 정류장','정류장까지 부담이 큰 주거지를 찾아 정류장 신설·이전 검토 지역으로 제시합니다.','정류장 검토 지역 (버스정류소 기준)',V('V6.22.bus'),'도로 폭·회차 공간은 교통 부서가 함께 확인',C.ink],[5.3,'보행로·계단 정비','부담 큰 경로가 지나는 계단·급경사 구간에 난간·쉼터·미끄럼 방지·열선 순위를 매깁니다.','사고가 겹치는 고부담 법정동',V('V6.22.acc'),'사고 자료: 도로교통공단 (법정동 단위)',C.acc]].forEach(c => {
    hr(s, c[0], 1.5, 4.1, c[6], 2);
    T(s, c[1], { x:c[0], y:1.62, w:4.1, h:0.36, fontSize:15, bold:true, color:c[6] });
    T(s, c[2], { x:c[0], y:2.05, w:4.1, h:0.75, fontSize:12, color:C.text, lineSpacingMultiple:1.12 });
    stat(s, c[0], 2.95, 4.1, c[3], c[4], { size:22, laterInk:true });
    T(s, c[5], { x:c[0], y:3.75, w:4.1, h:0.3, fontSize:11, color:C.muted }); });
  vr(s, 4.95, 1.5, 2.6);
  takeaway(s, '큰 공사 전에, 작은 개선으로 줄일 수 있는 부담부터 찾습니다.', 4.45); }

// ── 23 활용 ④ 길안내 ──
{ const s = base('활용 · 길안내 서비스', '도보 시간에 "오르막"을 더합니다');
  s.addImage({ path:img('mobile_v6.png'), x:0.5, y:1.35, w:3.76, h:3.28 });
  hr(s, 4.75, 1.5, 4.65, C.ink, 2);
  T(s, '무엇이 달라지나', { x:4.75, y:1.62, w:4.6, h:0.3, fontSize:13, bold:true, color:C.acc });
  T(s, [{ text:'같은 450m라도 오르막과 계단을 출발 전에 알려 줍니다', options:{ bullet:{ indent:12 }, breakLine:true } }, { text:'어르신·휠체어 모드에서 계단 없는 완만한 길을 고릅니다', options:{ bullet:{ indent:12 } } }], { x:4.75, y:1.98, w:4.6, h:0.9, fontSize:12, color:C.text, paraSpaceAfter:4 });
  T(s, '제공 방식', { x:4.75, y:2.98, w:4.6, h:0.3, fontSize:13, bold:true, color:C.ink });
  T(s, '서울동행맵 등에 지역 부담 지수와 구간 경사 정보를 공공데이터로 제공합니다. 구간 단위 원자료는 반출 제한이 있어 기관 간 협의나 공개데이터 재구축으로 연계합니다.', { x:4.75, y:3.3, w:4.6, h:1.15, fontSize:11.5, color:C.text, lineSpacingMultiple:1.1 });
  takeaway(s, '시민에게는 "출발 전에 아는 오르막", 행정에는 "고칠 곳의 목록"이 됩니다.', 4.72); }

// ── 24 화면 ──
{ const s = base('evenly 화면', '담당자는 이렇게 씁니다', { tsize:24 });
  T(s, '동을 고르고, 후보를 보고, 시설을 놓아 보면 효과가 바로 나옵니다', { x:4.9, y:0.64, w:4.55, h:0.62, fontSize:12, color:C.muted, valign:'middle', align:'right' });
  s.addImage({ path:img('dashboard_v6.png'), x:0.6, y:1.38, w:8.8, h:3.72 });
  src(s, '화면 예시(구상), 가상 수치 / 본선에서는 실제 결과 격자로 동작하는 데모로 시연'); }

// ── 25 확산·한계 ──
{ const s = base('확산과 한계', '관악구에서 시작해, 서울 전역과 전국으로 넓힙니다', { tsize:21 });
  hr(s, 0.6, 1.62, 8.8, C.ink, 1.25);
  ['관악구 시범','5개 구 확대','서울 전역','사업·서비스 연계','전국 구릉지 · 매년 갱신'].forEach((t, i) => { const x = 0.6 + i*1.78, hot = i==4;
    s.addShape(pres.shapes.RECTANGLE, { x, y:1.55, w:0.14, h:0.14, fill:{color: hot?C.acc:C.ink}, line:{color: hot?C.acc:C.ink} });
    T(s, String(i+1) + '단계', { x, y:1.8, w:1.6, h:0.25, fontSize:10.5, color:C.muted });
    T(s, t, { x, y:2.05, w:1.65, h:0.5, fontSize:12.5, bold:true, color: hot?C.acc:C.ink }); });
  [['공공','후보 선정의 공통 기준, 예산 효과의 사전 근거'],['서비스','동행맵·지도앱에 오르막 정보'],['확산','같은 LX 데이터로 부산 산복도로 등 전국 구릉지']].forEach((e, i) => { const x = 0.6 + i*2.97;
    bar(s, x, 2.75, 0.75, i==0 ? C.acc : C.ink); T(s, e[0], { x:x+0.22, y:2.75, w:2.6, h:0.3, fontSize:13, bold:true, color: i==0 ? C.acc : C.ink });
    T(s, e[1], { x:x+0.22, y:3.07, w:2.55, h:0.5, fontSize:11.5, color:C.text }); });
  hr(s, 0.6, 3.75, 8.8);
  T(s, '한계와 대응', { x:0.6, y:3.85, w:4, h:0.28, fontSize:12, bold:true, color:C.muted });
  [['후보 발굴까지가 역할','지반·규제·보상은 다음 단계 현장 타당성 조사로'],['1:5,000 지도·외출 자료의 한계','작은 골목 일부 누락 가능, 외출은 보조 관찰로만 사용']].forEach((l, i) => { const y = 4.18 + i*0.45;
    T(s, l[0], { x:0.6, y, w:3.0, h:0.4, fontSize:12, bold:true, color:C.acc, valign:'middle' }); T(s, l[1], { x:3.7, y, w:5.7, h:0.4, fontSize:12, color:C.text, valign:'middle' }); }); }

// ── 26 마감 ──
{ const s = pres.addSlide(); page++; s.background = { color:C.ink };
  s.addImage({ path:img('contour_dark.png'), x:0, y:0, w:10, h:5.625, transparency:55 });
  T(s, '어디에 살든,', { x:0.7, y:1.55, w:8.6, h:0.6, fontSize:28, color:C.white });
  T(s, '7분은 7분이어야 합니다.', { x:0.7, y:2.15, w:8.6, h:0.85, fontSize:38, bold:true, color:C.acc });
  T(s, [{ text:'evenly', options:{ bold:true, color:C.white, fontSize:26 } }, { text:'   even = 평평한 + 공평한', options:{ color:C.onDark, fontSize:14 } }], { x:0.7, y:3.25, w:8.6, h:0.5 });
  T(s, '언덕 위 우리동네 · 경사 반영 이동약자 접근성 지도', { x:0.7, y:3.8, w:8.6, h:0.35, fontSize:13, color:C.onDark });
  T(s, `${team()}   |   한국국토정보공사 데이터 활용`, { x:0.7, y:4.8, w:7, h:0.3, fontSize:12, color:C.onDark });
  reviewTag(s, true); }

// ── 부록 ──
{ const s = base('부록 1', '활용 데이터 목록');
  etable(s, [['구분','제공','데이터','기간·기준','용도'],
    [B('미개방',{color:C.acc}),'한국국토정보공사','수치지형도 1:5,000 (shp)','2024.11','길·계단·건물'],[B('미개방',{color:C.acc}),'한국국토정보공사','DEM 5M_수도권 (img)','2024.11','링크 경사'],[B('미개방',{color:C.acc}),'한국국토정보공사','국토정보필지_전국 (shp)','2024~2025','건물↔대장 연결'],
    [B('상호제공'),'SKT · KCB · 도로교통공단','유동인구·소득·교통사고','2020~2024','보조 관찰'],[B('공공'),'서울시 · 행정안전부','건축물대장·법정동 코드','2026','건물 용도·층수'],[B('공공'),'공공데이터포털·서울시','약국·엘리베이터·도보망','2026','목적지·대조군'],[B('공공'),'행정안전부 · 서울시','고령·장애인·독거노인','2025~2026','수혜 인원 추정']],
    { colW:[0.95,2.1,2.55,1.3,1.9], rowH:[0.36,0.4,0.4,0.4,0.4,0.4,0.4,0.4] });
  src(s, '선행연구: 이희연 외(2015) 서울도시연구 / 구릉지 고령자 이동취약지역 연구 / 이소민·오성훈(2025) / 강현미·박소현(2009)'); }
{ const s = base('부록 2', '전처리와 경사 모델');
  [['수치지형도','도로중심선·계단 추출, 교차점 분할, 끊긴 끝점 10m 연결, 30m 링크'],['DEM 5M','좌표계 통일(EPSG:5186), 링크 양 끝 고도, ±40% 초과는 자름, 다리·터널 경사 0'],['건물·필지·대장','건물 중심점 → 필지 → 건축물대장, 주용도로 주거·의료·노유자, 연결률 보고']].forEach((c, i) => { const y = 1.45 + i*1.2; if (i) hr(s, 0.6, y-0.1, 4.4);
    T(s, c[0], { x:0.6, y, w:4.4, h:0.3, fontSize:13, bold:true, color: i==2 ? C.acc : C.ink }); T(s, c[1], { x:0.6, y:y+0.34, w:4.4, h:0.7, fontSize:11.5, color:C.text }); });
  const xs = [0,2,4,6,8,10,12,14,16,18,20], tob = sl => 6*Math.exp(-3.5*Math.abs(sl+0.05)), flatv = tob(0);
  s.addChart(pres.charts.LINE, [{ name:'오르막 소요시간 배수', labels:xs.map(x=>x+'%'), values:xs.map(x => +(flatv/tob(x/100)).toFixed(2)) }], { x:5.25, y:1.4, w:4.2, h:2.45, chartColors:[C.acc], lineSize:2.5, lineDataSymbol:'circle', lineDataSymbolSize:5, showTitle:true, title:'오르막 경사별 소요시간 배수', titleFontSize:11, titleColor:C.ink, titleFontFace:F, catAxisLabelColor:C.muted, valAxisLabelColor:C.muted, catAxisLabelFontSize:9, valAxisLabelFontSize:9, valGridLine:{ color:'E8EAE9', size:0.5 }, catGridLine:{ style:'none' }, showLegend:false, valAxisMinVal:1 });
  T(s, [{ text:'고령자 ', options:{ bold:true, color:C.ink } }, { text:'0.8m/s × Tobler 배수, 내리막은 오르막 부담의 50%, 계단 최소 25%·1.2배', options:{ breakLine:true } }, { text:'휠체어 ', options:{ bold:true, color:C.teal } }, { text:'1.0m/s, 1/12 초과는 10배(회피), 계단 통행 불가', options:{} }], { x:5.25, y:4.0, w:4.2, h:1.0, fontSize:11, color:C.text, valign:'middle' });
  src(s, 'Tobler 보행함수 v = 6·exp(−3.5·|s+0.05|) km/h / 휠체어 경사 기준: 장애인·노인·임산부 등의 편의증진 보장에 관한 법률 시행규칙'); }
{ const s = base('부록 3', '가정을 바꿔도 결론이 유지되는가');
  const r = (a,b,c2,d) => [B(a), b, c2, d];
  etable(s, [['가정','값','근거','바꿨을 때 (순위상관)'], r('고령자 보행속도','0.8m/s','가정 (민감도로 점검)',V('V6.29.speed')), r('내리막 부담','오르막의 50%','가정 (0%·100% 비교)',V('V6.29.down')), r('계단','최소 25% 경사, 1.2배','가정 (1.5배 비교)',V('V6.29.stair')), r('휠체어 경사 한계','1/12 (8.3%)','법정 경사로 기준','해당 없음 (법정)'), r(`고립 위험 문턱`,`왕복 +${RMIN()}분`,'420m ÷ 0.8m/s ≈ 편도 9분',Q('V6.29.band_rho_short', '실제 결과 후')), r('엘리베이터 대기',`${Q('V6.29.facility_w', '30·60·90초')} 비교`,'서울시 발표 + 실측',{ text:V('V6.29.facility'), options:{ fontSize:9 } }), r('반출 최소 건물 수','5채','비식별 기준','해당 없음')],
    { colW:[2.2,2.1,2.6,1.9], rowH:[0.34,0.4,0.4,0.4,0.4,0.4,0.4,0.4] });
  src(s, '순위상관이 0.9 이상이면 "누가 더 취약한가"의 순서가 가정에 크게 흔들리지 않는다는 뜻'); }
{ const s = base('부록 4', '경사 비용 계산 (발췌)');
  const code = ['def tobler(s):                       # 경사 s → 보행속도 km/h','    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))','FLAT = tobler(0.0)','','def elder_time(length, s, stair):    # 고령자 링크 통과 시간(초)','    s = np.where(stair, np.sign(s + 1e-9) * np.maximum(np.abs(s), 0.25), s)','    up = FLAT / tobler(np.abs(s))','    down = 1 + C.DOWNHILL_WEIGHT * (up - 1)   # 내리막은 오르막 부담의 일부','    factor = np.where(s >= 0, FLAT / tobler(s), down)','    t = length / C.ELDER_SPEED * factor','    return np.where(stair, t * C.STAIR_FACTOR, t)','','def wheel_time(length, s, stair):    # 휠체어: 1/12 초과는 사실상 회피, 계단 불가','    up = np.maximum(s, 0)','    t = length / (C.WHEEL_SPEED * np.maximum(0.4, 1 - 5 * up))','    t = np.where(np.abs(s) > C.WHEEL_LIMIT, t * C.WHEEL_STEEP_PENALTY, t)','    return np.where(stair, np.inf, t)'].join('\n');
  box(s, 0.6, 1.4, 8.8, 3.7, C.soft);
  T(s, code, { x:0.8, y:1.5, w:8.5, h:3.5, fontFace:'Consolas', fontSize:10.5, color:C.text });
  src(s, 'analysis/hbi/lib/model.py 발췌 / 실행 환경: QGIS 3.32 내장 Python, numpy·GDAL, 자체 다익스트라, 자동 점검(setup·check)'); }

// ── 저장 + 누락 목록 ────────────────────────────────────────
if (pending.length) { console.error('!! 빈칸으로 그려지지 않은 누락 key: ' + pending.map(p => p.page + '장 ' + p.key).join(', ')); process.exitCode = 1; }
if (page > 30) { console.error(`!! 슬라이드 ${page}장 — 30장 제한 초과`); process.exit(1); }
const OUT = arg('--out') || (REAL ? '../deliverables/언덕위우리동네_기획서_final.pptx'
          : FALLBACK ? '../deliverables/언덕위우리동네_기획서_대비책.pptx'
          : FAKE ? '../deliverables/_test_기획서_v6.pptx'
          : REH ? `../deliverables/_rehearsal_기획서_v6${BANDS === 'mix' ? '' : (MINB ? '_B' : '_A')}.pptx`
          : '../deliverables/_blank_기획서_v6.pptx');
const MISS = arg('--missing') || path.join('data', REH ? `missing_v6${BANDS === 'mix' ? '' : (MINB ? '_B' : '_A')}.txt` : FALLBACK ? 'missing_fallback.txt' : 'missing.txt');   // 공개 대역은 A·B 판을 나란히 보려고 따로
const lines = [`# 기획서 v6 누락 목록 — source=${R.source}${R.src ? ', src=' + R.src : ''}, bands=${R.bands || 'hbi'}, ${new Date().toISOString().slice(0, 19)}`,
  `# 출력: ${OUT.replace('../', '')} (${page}장)`,
  ...missing.map(m => `누락: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}  [${m.key}]`),
  ...(fallbacks.length ? ['# 대체 (공개 대역 판에서 원래 채울 수 없는 칸·기본 문구로 바뀐 곳. 필수 빈칸이 아니라 check_deck N=M=K 에는 넣지 않음)',
    ...fallbacks.map(m => `대체: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}  [${m.key}] → "${String(m.used).replace(/\n/g, ' ').slice(0, 40)}"`)] : [])];
fs.mkdirSync(path.dirname(MISS), { recursive:true });
fs.writeFileSync(MISS, lines.join('\n') + '\n');
if (R.source === 'none') console.warn('!! data/results.json 없음 → 빈칸 판');
if (FAKE) console.warn('!! 가상 수치 — 모든 장 오른쪽 위에 "가상 수치 · 검토용"');
if (REH) console.warn('!! 공개 대역 — 모든 장 오른쪽 위에 "공개 대역 · 제출 금지"');
console.log(`슬라이드 ${page}장, 누락 ${missing.length}건, 대체 ${fallbacks.length}건 → ${MISS}`);
pres.writeFile({ fileName: OUT }).then(f => console.log('wrote', f));
