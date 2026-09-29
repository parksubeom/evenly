// 기획서 생성기. 반출 결과는 tools/prepare_deck_data.py 가 만든 data/results.json 에서 읽는다.
//   npm run build:fake  → 가짜 결과로 시험 (워터마크 + deliverables/_test_기획서.pptx)
//   npm run build:real  → 실제 반출 결과 (deliverables/언덕위우리동네_기획서_final.pptx)
// 값이 없으면 기존처럼 ___ / 주황 점선 박스를 남기고 data/missing.txt 에 "누락: 슬라이드, 값, 필요한 파일"을 적는다.
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
process.chdir(__dirname);
const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
pres.title = '언덕 위 우리동네: 경사 반영 이동약자 접근성 지도';
const F = 'Malgun Gothic';
const C = { dark:'1F3B2D', orange:'E8743B', sage:'7FA88E', tint:'EEF3EF', ink:'22302A', muted:'5F6B64', line:'D5E2D8', white:'FFFFFF', paleO:'FCEBE2' };
const img = n => 'img/' + n;
let page = 0;
// 빈칸 추적: V() 가 값을 못 찾으면 pending 에 key 를 쌓고, 빈칸(___ / ○○○)이 든 글상자·표·점선 박스가 만들어질 때
// 빈칸 수만큼 앞에서부터 꺼내 objectName 에 "BLANK:<장>:<key>|..." 로 적는다 → tools/check_deck.py 가 missing.txt 와 1:1 대조
const BLANK_RE = /_{3,}|○○○/g;
const pending = [];
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
const T = (s, text, o = {}) => {
  const tag = ('_keys' in o) ? o._keys : (runs(text) ? take(runs(text)) : undefined);
  const opt = Object.assign({ fontFace:F, color:C.ink, isTextBox:true, margin:0, valign:'top' }, o);
  delete opt._keys; if (tag) opt.objectName = tag;
  return s.addText(text, opt);
};
// 표: explicit(표 전체가 한 항목의 빈칸)이 있으면 그것만, 없으면 칸 안의 빈칸 수만큼
function TB(s, rows, o, explicit) {
  const n = explicit ? 0 : rows.reduce((a, r) => a + r.reduce((b, c) => b + runs(c && c.text !== undefined ? c.text : c), 0), 0);
  const tag = (explicit || n) ? take(n, explicit ? [explicit] : []) : undefined;
  return s.addTable(rows, Object.assign({}, o, tag ? { objectName: tag } : {}));
}

// ── 결과 데이터 ──────────────────────────────────────────────
const DATA_PATH = path.join('data', 'results.json');
const R = fs.existsSync(DATA_PATH) ? JSON.parse(fs.readFileSync(DATA_PATH, 'utf8')) : { source:'none', fields:{}, images:{}, tables:{} };
const FAKE = R.source === 'fake';
if (FAKE) pres.title = '[테스트 데이터 — 제출 금지] ' + pres.title;
const missing = [], notes = [], seen = new Set();
function miss(key, meta) {
  if (meta && meta.optional) return;
  const k = page + '|' + key;
  if (seen.has(k)) return;
  seen.add(k);
  missing.push({ page, key, label: (meta && meta.label) || key, need: (meta && meta.need) || [] });
}
// V: 값이 있으면 문자열, 없으면 fallback(기본 ___)을 돌려주고 누락으로 기록
function V(key, fallback = '___') {
  const f = R.fields[key];
  if (f && f.value !== null && f.value !== undefined) return String(f.value);
  miss(key, f || { label:key, need:[] });
  if (!(f && f.optional)) pending.push({ key, page });
  return fallback;
}
const has = key => { const f = R.fields[key]; return !!(f && f.value !== null && f.value !== undefined); };
// Q: 값이 없어도 누락으로 치지 않는 보조 문구 (기본값이 그대로 말이 되는 곳)
const Q = (key, fallback) => has(key) ? String(R.fields[key].value) : fallback;
function IMG(key) {
  const m = R.images[key];
  if (m && m.path && fs.existsSync(m.path)) return m.path;
  miss('img:' + key, m || { label:key, need:[] });
  return null;
}
const hasImg = key => { const m = R.images[key]; return !!(m && m.path && fs.existsSync(m.path)); };
function TBL(key) {
  const t = R.tables[key];
  if (t && t.rows && t.rows.length) return t.rows;
  miss('tbl:' + key, t || { label:key, need:[] });
  return null;
}
// 가짜 데이터 워터마크: 모든 슬라이드 하단
function wm(s) {
  if (!FAKE) return;
  s.addShape(pres.shapes.RECTANGLE, { x:3.1, y:5.42, w:3.8, h:0.19, fill:{color:'B23A2A', transparency:8}, line:{color:'B23A2A'} });
  T(s, '테스트 데이터 — 제출 금지', { x:3.1, y:5.42, w:3.8, h:0.19, fontSize:9, bold:true, color:C.white, align:'center', valign:'middle' });
}

let sec = 0;
function base(kicker, title, opts={}) {
  const s = pres.addSlide(); page++;
  kicker = kicker.replace(/^\d+\s+/, '');
  if (!opts.appendix) { sec++; kicker = String(sec).padStart(2,'0') + '  ' + kicker; } else { kicker = 'APPENDIX  ' + kicker; }
  s.background = { color: C.white };
  s.addImage({ path: img('contour_light.png'), x:5.5, y:-1.2, w:6, h:3.4, transparency: 40 });
  T(s, kicker, { x:0.5, y:0.32, w:6, h:0.28, fontSize:11, bold:true, color:C.orange });
  T(s, title, { x:0.5, y:0.6, w:9, h:0.6, fontSize:opts.tsize||24, bold:true, color:C.dark });
  T(s, String(page), { x:9.1, y:5.25, w:0.4, h:0.22, fontSize:9, color:C.muted, align:'right' });
  wm(s);
  return s;
}
function src(s, text) { T(s, text, { x:0.5, y:5.2, w:8.4, h:0.28, fontSize:8, color:C.muted }); }
function card(s, x, y, w, h, fill) { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill:{color:fill||C.tint}, line:{color:fill||C.tint}, rectRadius:0.08 }); }
function circleNum(s, x, y, n, fill) {
  s.addShape(pres.shapes.OVAL, { x, y, w:0.42, h:0.42, fill:{color:fill||C.dark}, line:{color:fill||C.dark} });
  T(s, String(n), { x, y, w:0.42, h:0.42, fontSize:13, bold:true, color:C.white, align:'center', valign:'middle' });
}

function ph(s, x, y, w, h, label, fs, key) {
  const tag = take(runs(label), key ? [key] : []);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, Object.assign({ x, y, w, h, fill:{color:'FFF7F2'}, line:{color:C.orange, width:1.25, dashType:'dash'}, rectRadius:0.08 }, tag ? { objectName: tag } : {}));
  T(s, label, { x:x+0.15, y, w:w-0.3, h, fontSize:fs||10.5, color:'C0612F', align:'center', valign:'middle', bold:true, _keys: tag });
}
const B = {};

B.DATA = () => {
  const s = base('활용 데이터', '미개방데이터 3종을 하나의 보행 모델로 연결합니다');
  const ds = [
    ['국토정보필지_전국', '2024.06 ~ 2025.07', '방문 시 제공 · 건물 결과 결합', '결과의 공간 단위, "집"'],
    ['수치지형도_수도권', '2024.11', '도로·보도·계단·건물·정거장', '보행 네트워크, "길"'],
    ['DEM 5M_수도권', '2024.11 (2021 기준)', '5m 격자 고도값', '링크별 경사, "언덕"'],
  ];
  ds.forEach((d, i) => {
    const x = 0.5 + i*3.05;
    card(s, x, 1.4, 2.85, 1.85, C.dark);
    T(s, 'LX 한국국토정보공사 · 미개방', { x:x+0.2, y:1.52, w:2.5, h:0.22, fontSize:8.5, color:'B9CFC0' });
    T(s, d[0], { x:x+0.2, y:1.76, w:2.5, h:0.35, fontSize:13.5, bold:true, color:C.white });
    T(s, d[1], { x:x+0.2, y:2.1, w:2.5, h:0.25, fontSize:9.5, color:'B9CFC0' });
    T(s, d[2], { x:x+0.2, y:2.45, w:2.5, h:0.3, fontSize:10.5, color:C.white });
    T(s, d[3], { x:x+0.2, y:2.8, w:2.5, h:0.35, fontSize:12, bold:true, color:C.orange });
  });
  card(s, 0.5, 3.45, 4.4, 1.6, C.paleO);
  T(s, '상호제공데이터 (가점 연계)', { x:0.7, y:3.55, w:4, h:0.3, fontSize:11.5, bold:true, color:C.orange });
  T(s, [
    { text:'SKT 성·연령별 유동인구(2024)', options:{ bold:true, breakLine:true } },
    { text:'경사가 고령자 외출을 줄이는지 검증', options:{ color:C.muted, breakLine:true } },
    { text:'코리아크레딧뷰로 행정동 소득 통계', options:{ bold:true, breakLine:true } },
    { text:'언덕 부담과 저소득 고령층의 중첩 분석', options:{ color:C.muted } },
  ], { x:0.7, y:3.9, w:4.1, h:1.1, fontSize:10, lineSpacingMultiple:1.1 });
  card(s, 5.1, 3.45, 4.4, 1.6);
  T(s, '공개데이터 (반입 신청)', { x:5.3, y:3.55, w:4, h:0.3, fontSize:11.5, bold:true, color:C.dark });
  T(s, [
    { text:'행정동 경계 · 서울시 2025 선정지 5곳 위치', options:{ bold:true, breakLine:true } },
    { text:'행정동 집계·지도 배경, 모델 검증의 정답지', options:{ color:C.muted, breakLine:true } },
    { text:'행정동별 65세 이상 인구', options:{ bold:true, breakLine:true } },
    { text:'행정안전부 주민등록 인구통계 (반출 후 결합)', options:{ color:C.muted, breakLine:true } },
    { text:'목적지(의료·노유자시설, 정류장, 지하철역)는 수치지형도에서 추출', options:{ color:C.orange, fontSize:8.5 } },
  ], { x:5.3, y:3.88, w:4.1, h:1.15, fontSize:10, lineSpacingMultiple:1.05 });
  s.addNotes('핵심은 미개방데이터 3종이 서로 없으면 성립하지 않는 구조라는 점. 출발점은 수치지형도의 주거 건물이고, 국토정보필지는 방문 시 센터가 제공해 건물 결과를 필지에 결합합니다. 목적지는 수치지형도 건물 용도(의료·노유자시설), 정류장, 정거장(지하철역) 레이어에서 뽑습니다. 약국은 공개 경로로 자동 수집이 안 돼 이번 분석에서는 빠졌고 의료시설로 대체합니다. 상호제공데이터는 결과 검증용으로 연계합니다.');
};

B.LINK = () => {
  const s = base('데이터 연계 구조', '세 데이터는 이렇게 하나로 묶입니다');
  const box = (x, y, w, h, t1, t2, fill, tc) => { card(s, x, y, w, h, fill); T(s, t1, { x:x+0.15, y:y+0.12, w:w-0.3, h:0.3, fontSize:11.5, bold:true, color:tc||C.ink }); T(s, t2, { x:x+0.15, y:y+0.45, w:w-0.3, h:h-0.5, fontSize:9.5, color: tc?'CFE0D4':C.muted }); };
  box(0.5, 1.4, 2.6, 1.05, '수치지형도 건물·정거장', '주거 건물 → 출발점\n의료·정류장·역 → 목적지', C.dark, C.white);
  box(0.5, 2.65, 2.6, 1.05, '수치지형도 도로·계단', '보도·도로 중심선, 계단 → 노드·링크', C.dark, C.white);
  box(0.5, 3.9, 2.6, 1.05, 'DEM 5M', '링크 양 끝점 고도 샘플링', C.dark, C.white);
  const arr = (y) => s.addShape(pres.shapes.RIGHT_ARROW, { x:3.2, y, w:0.45, h:0.3, fill:{color:C.sage}, line:{color:C.sage} });
  arr(1.78); arr(3.03); arr(4.28);
  box(3.75, 1.4, 2.7, 1.05, '결합 ① 공간 스냅', '건물·목적지를 가장 가까운 보행 노드에 연결 (60m 이내)');
  box(3.75, 2.65, 2.7, 1.05, '결합 ② 방향 그래프', '링크마다 정방향·역방향 두 개의 비용 생성');
  box(3.75, 3.9, 2.7, 1.05, '결합 ③ 경사 비용', '고도차 ÷ 링크 길이 → 오르막·내리막 경사');
  card(s, 6.75, 1.4, 2.75, 3.55, C.paleO);
  T(s, '산출물', { x:6.95, y:1.52, w:2.4, h:0.3, fontSize:12, bold:true, color:C.orange });
  T(s, [
    { text:'건물별 언덕 부담 지수(HBI)', options:{ bold:true, breakLine:true } },
    { text:'고령자·휠체어 각각, 국토정보필지(방문 시 제공)에 결합', options:{ color:C.muted, breakLine:true } },
    { text:' ', options:{ breakLine:true } },
    { text:'250m 격자·행정동 집계', options:{ bold:true, breakLine:true } },
    { text:'→ SKT 유동인구, KCB 소득과 결합 (행정동 코드 기준)', options:{ color:C.muted, breakLine:true } },
    { text:' ', options:{ breakLine:true } },
    { text:'후보지별 효과 지표', options:{ bold:true, breakLine:true } },
    { text:'수혜 인원 × 단축 시간', options:{ color:C.muted, breakLine:true } },
    { text:' ', options:{ breakLine:true } },
    { text:'데이터 경계 500m 이내 건물은 제외 (경계 밖 시설 때문에 시간이 부풀지 않도록)', options:{ color:C.orange, fontSize:9 } },
  ], { x:6.95, y:1.9, w:2.45, h:2.95, fontSize:10, lineSpacingMultiple:1.05 });
  s.addNotes('데이터 간 연계 활용의 완성도를 보여주는 장표. 공간 스냅, 방향 그래프, 경사 비용 세 단계로 결합합니다.');
};

B.SAFE = () => {
  const s = base('데이터안심구역 분석 수행', '5일간 안심구역에서 수행한 작업');
  const days = [
    ['1일차', '데이터 구조 파악\n소규모 범위 시험 실행'],
    ['2일차', '보행 네트워크·경사\nHBI 산출·필지 결합'],
    ['3일차', '선정지·구간 검증\n상호제공데이터 결합'],
    ['4일차', '민감도 분석\n보완·2차 반출'],
    ['5일차', '최종 수정\n결과 정리·반출 심사'],
  ];
  days.forEach((d, i) => {
    const x = 0.5 + i*1.83;
    card(s, x, 1.4, 1.65, 2.2, i==4?C.paleO:C.tint);
    T(s, d[0], { x:x+0.15, y:1.52, w:1.4, h:0.32, fontSize:13, bold:true, color: i==4?C.orange:C.dark });
    const dt = V(`SAFE.day${i+1}`, null);
    if (dt) T(s, dt, { x:x+0.15, y:1.9, w:1.4, h:0.32, fontSize:10.5, bold:true, color:C.orange, valign:'middle' });
    else ph(s, x+0.15, 1.9, 1.35, 0.32, '2026.  .  .', 9, `SAFE.day${i+1}`);
    T(s, d[1], { x:x+0.15, y:2.35, w:1.4, h:1.15, fontSize:10, color:C.ink, lineSpacingMultiple:1.15 });
  });
  card(s, 0.5, 3.8, 4.4, 1.25);
  T(s, '사전 준비 (안심구역 밖)', { x:0.7, y:3.9, w:4, h:0.3, fontSize:11.5, bold:true, color:C.dark });
  T(s, '공개 DEM·도로 데이터로 분석 코드를 미리 완성하고 테스트. 방문 시간은 실데이터 적용과 결과 도출에 집중', { x:0.7, y:4.22, w:4.05, h:0.8, fontSize:10, color:C.muted });
  card(s, 5.1, 3.8, 4.4, 1.25, C.dark);
  T(s, '반출 결과물', { x:5.3, y:3.9, w:4, h:0.3, fontSize:11.5, bold:true, color:C.orange });
  T(s, '행정동·격자 단위 집계 결과, 시각화 지도, 검증 통계표. 개별 필지 원자료는 반출하지 않음', { x:5.3, y:4.22, w:4.05, h:0.8, fontSize:10, color:C.white });
  s.addNotes('방문일수는 기술평가 점수입니다. 실제 방문일을 기입하고, 일자별 작업을 증빙과 일치시키세요.');
};

B.PRE = () => {
  const s = base('전처리 파이프라인', '원자료를 분석 가능한 형태로 만드는 과정');
  const cols = [
    ['건물·필지', ['용도·종류 코드로 주거 건물 추출 (출발점)', '의료·노유자시설, 정류장·정거장(역) = 목적지', '데이터 경계 500m 이내 건물 제외', '국토정보필지(방문 시 제공)에 건물 HBI 결합']],
    ['수치지형도 도로', ['보도·도로 중심선과 계단 레이어 추출', '토폴로지 정리: 끊긴 선 연결, 중복 제거', '30m 단위 링크 분할', '계단 속성 태깅 (휠체어 통행 불가)']],
    ['DEM 5M', ['좌표계 통일 (EPSG:5186)', '링크 양 끝점 고도 샘플링', '링크 경사 = 고도차 ÷ 길이', '교량·터널은 경사 0, ±40% 초과는 절단']],
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i*3.05;
    card(s, x, 1.4, 2.85, 3.3);
    T(s, c[0], { x:x+0.2, y:1.52, w:2.5, h:0.35, fontSize:13, bold:true, color:C.dark });
    c[1].forEach((t, j) => {
      circleNum(s, x+0.2, 2.0 + j*0.66, j+1, i==2?C.orange:C.dark);
      T(s, t, { x:x+0.72, y:1.98 + j*0.66, w:1.98, h:0.48, fontSize:9.8, valign:'middle' });
    });
  });
  T(s, '품질 점검: 보행 네트워크에 연결되지 않은 건물 비율, 비정상 경사(±40% 초과) 링크 비율을 단계별로 기록', { x:0.5, y:4.85, w:9, h:0.3, fontSize:10, bold:true, color:C.orange });
  s.addNotes('전처리 타당성은 예선 논리성 항목. 좌표계, 토폴로지, 이상값 처리를 구체적으로 보여줍니다. 명세 확인 후 세부 기준은 수정하세요.');
};

B.RES1 = () => {
  const s = base('분석 결과 ①', '평지 기준으로는 보이지 않던 사각지대');
  const map = IMG('map');
  if (map) {
    s.addImage({ path: map, x:0.5, y:1.35, w:5.1, h:3.4 });
    s.addImage({ path: hasImg('legend') ? R.images.legend.path : img('legend.png'), x:0.5, y:4.78, w:2.2, h:0.37 });
    T(s, `언덕 부담 지수 · 250m 격자 · ${Q('RES1.target', '의료시설')} 왕복`, { x:2.75, y:4.83, w:2.9, h:0.25, fontSize:8.5, color:C.muted });
  } else {
    s.addImage({ path: img('hbi_map.png'), x:0.5, y:1.35, w:5.1, h:3.4, transparency:55 });
    ph(s, 1.3, 2.55, 3.5, 1.0, '실제 결과 지도 삽입\n(5개 구 250m 격자 HBI)', 11, 'img:map');
    s.addImage({ path: img('legend.png'), x:0.5, y:4.78, w:2.2, h:0.37 });
    T(s, '언덕 부담 지수', { x:2.75, y:4.83, w:1.5, h:0.25, fontSize:8.5, color:C.muted });
  }
  T(s, '주요 발견', { x:5.9, y:1.35, w:3.6, h:0.3, fontSize:13, bold:true, color:C.dark });
  const k = [
    [`HBI 1.8 이상 주거 건물 (${Q('RES1.target', '의료시설')} 기준)`, `${V('RES1.high_n')}동 (전체의 ${V('RES1.high_share', '___%')})`],
    ['평지 기준 "양호" → 경사 반영 "취약"', `약 ${V('RES1.inverted_n')}동`],
    ['HBI 1.8 이상 건물 거주 고령인구 추정', `약 ${V('RES1.elderly')}명`],
  ];
  k.forEach((v, i) => {
    const y = 1.75 + i*0.8;
    card(s, 5.9, y, 3.6, 0.68);
    T(s, v[0], { x:6.05, y:y+0.06, w:3.3, h:0.26, fontSize:9.5, color:C.muted });
    T(s, v[1], { x:6.05, y:y+0.3, w:3.3, h:0.34, fontSize:13, bold:true, color:C.orange });
  });
  card(s, 5.9, 4.2, 3.6, 0.6, C.paleO);
  const ins = has('RES1.insight') ? V('RES1.insight') : '인사이트 한 줄: ' + V('RES1.insight', '________________');
  T(s, ins, { x:6.05, y:4.2, w:3.3, h:0.6, fontSize:10.5, bold:true, color:C.dark, valign:'middle' });
  src(s, `분석 주거 건물 ${V('RES1.n_bld')}동 (데이터 경계 500m 이내 제외) · 국토정보필지(지목 '대') 기준 HBI 1.8 이상 ${V('RES1.parcel_share', '___%')}`);
  const bt = (R.tables['RES1.by_target'] || {}).rows || [];
  s.addNotes('안심구역 분석 결과로 자동 생성된 장표입니다 (tools/prepare_deck_data.py). ___ 가 남아 있으면 deck/data/missing.txt 를 확인하세요.'
    + (bt.length ? ' 목적지별 HBI 1.8 이상 비율: ' + bt.map(r => `${r[0]} ${r[1]}(중앙값 ${r[2]})`).join(', ') + '.' : '')
    + edgeNote() + (has('RES1.wheel_ev') ? ` 휠체어 도달불가 비율(엘리베이터 있는 역 기준) ${Q('RES1.wheel_ev', '')}.` : ''));
};

// 경계 500m 포함 여부가 버전마다 다른 세 지표: v5 "(경계 제외)"면 그대로, v4면 "v4, 경계 500m 포함" 표시. 본문에는 넣지 않음
function edgeNote() {
  const items = [['RES1.median', 'HBI 중앙값', ''], ['RES1.home_ratio', '귀갓길 편도 배수 중앙값', ''], ['RES1.elder_rt', '고령자 왕복 중앙값', '분']].filter(([k]) => has(k));
  if (!items.length) return '';
  const scope = R.fields[items[0][0]].scope;
  return ` 의료시설 기준 ${items.map(([k, l, u]) => `${l} ${Q(k, '')}${u}`).join(', ')}` + (scope === 'v5' ? ' (경계 500m 제외).' : ' (v4 산출, 경계 500m 포함 — 다른 지표와 모집단이 달라 본문에는 쓰지 않음).');
}

B.VALID = () => {
  const s = base('분석 결과 ② 모델 검증', '우리 모델은 서울시의 판단을 재현하는가');
  const hdr = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:10, align:'center', valign:'middle' };
  const c = (t, o={}) => ({ text:t, options:Object.assign({ fontSize:10, align:'center', valign:'middle', color:C.ink }, o) });
  const blank = c('____', { color:'C0612F', bold:true });
  const sites = TBL('VALID.sites');
  const simg = sites && hasImg('sites') ? R.images.sites.path : null;
  if (simg) {
    T(s, (Q('VALID.pct_mode', 'grid') === 'circle' ? '2025 선정지 5곳 · 같은 반경 300m 원끼리 비교한 백분위' : '2025 서울시 선정지 5곳 · 반경 300m 평균 HBI의 백분위') + ` (상위 10% 안: ${V('VALID.top10_count')})`, { x:0.5, y:1.35, w:4.6, h:0.25, fontSize:9.5, bold:true, color:C.dark });
    s.addImage({ path: simg, x:0.5, y:1.62, w:4.6, h:2.2 });
  } else {
    const row = r => [ c(r.name), r.top_text ? c(r.top_text, { bold:true, color:C.orange }) : blank, r.top10 ? c(r.top10, { bold:true }) : blank ];
    const rows = sites || ['광진구 중곡동', '강서구 화곡동', '관악구 봉천동', '종로구 숭인동', '중구 신당동'].map(n => ({ name:n }));
    TB(s, [
      [ {text:'2025 서울시 선정지',options:hdr}, {text:'모델 HBI 순위',options:hdr}, {text:'상위 10% 포함',options:hdr} ],
      ...rows.map(row),
    ], { x:0.5, y:1.4, w:4.6, colW:[1.8,1.4,1.4], rowH:0.37, fontFace:F, border:{type:'solid',color:C.line,pt:0.75} }, sites ? undefined : 'tbl:VALID.sites');
  }
  card(s, 0.5, 3.95, 4.6, 1.05, C.paleO);
  T(s, '재현 사례: 대현산배수지공원 (계단 190개)', { x:0.7, y:4.03, w:4.2, h:0.28, fontSize:11, bold:true, color:C.dark });
  T(s, [
    { text:'서울시 발표 휠체어 우회 약 770m  ↔  모델 산출 ', options:{ color:C.ink } },
    { text:V('VALID.wheel_m', '____m'), options:{ bold:true, color:C.orange } },
  ], { x:0.7, y:4.36, w:4.2, h:0.55, fontSize:11, valign:'middle' });
  T(s, '현장 실측 vs 모델 예측', { x:5.4, y:1.4, w:4, h:0.3, fontSize:12, bold:true, color:C.dark });
  const meas = (R.tables['VALID.meas_rows'] || {}).rows || [];
  if (meas.length) {
    const mh = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:9.5, align:'center', valign:'middle' };
    s.addTable([
      [ {text:'구간',options:mh}, {text:'모델 예측 (성인 1.1m/s)',options:mh}, {text:'팀 실측',options:mh} ],
      ...meas.slice(0, 4).map(r => [ c(r[0], { fontSize:9.5 }), c(r[1], { fontSize:9.5 }), c(r[2], { fontSize:9.5, bold:true }) ]),
    ], { x:5.4, y:1.78, w:4.1, colW:[1.3,1.6,1.2], rowH:0.3, fontFace:F, border:{type:'solid',color:C.line,pt:0.75} });
    T(s, [
      { text:`파일럿 경로 ${V('VALID.meas_n')}개 · 상관계수 r = `, options:{ color:C.ink } },
      { text:V('VALID.meas_r', '____'), options:{ bold:true, color:C.orange } },
    ], { x:5.4, y:1.78 + 0.3*(Math.min(meas.length, 4)+1) + 0.1, w:4.1, h:0.3, fontSize:11, valign:'middle' });
    T(s, '경로 수가 적어 상관계수는 참고치입니다', { x:5.4, y:3.62, w:4.1, h:0.22, fontSize:8.5, color:C.muted });
  } else {
    ph(s, 5.4, 1.78, 4.1, 2.0, `산점도 삽입\n파일럿 경로 ${V('VALID.meas_n')}개, 실측 보행시간 vs 예측\n상관계수 r = ${V('VALID.meas_r', '____')}`, 10.5);
  }
  card(s, 5.4, 3.95, 4.1, 1.05, C.dark);
  T(s, `선정되지 않았지만 HBI가 더 높은 곳 ${V('VALID.new_n', '___곳')} 발견 → "공모 방식이 놓친 곳"`, { x:5.6, y:3.95, w:3.75, h:1.05, fontSize:11, bold:true, color:C.white, valign:'middle' });
  s.addNotes('분석결과의 타당성과 신뢰성(본선 우수성 30점)을 담당하는 장표. 전문가 판단 재현, 실측 비교, 새로운 발견 세 가지를 보여줍니다.'
    + (has('VALID.net_m') ? ` 대현산배수지공원 보행 최단거리 ${Q('VALID.net_m', '')}, 휠체어는 계단을 피해 ${Q('VALID.wheel_m', '-')}.` : '')
    + (Q('VALID.pct_mode', 'grid') === 'circle' ? ' 백분위는 선정지와 같은 반경 300m 원 평균끼리 비교한 값입니다(v5 percentile_circle).' : ' 백분위는 선정지 반경 300m 건물 평균을 전체 250m 격자 평균 분포에 놓은 값입니다(v4, 집계 단위가 달라 해석 주의).')
    + (has('VALID.new_n') && Q('VALID.new_n', '').includes('이상') ? ' validation_new_candidates.csv 는 상위 30개만 저장하므로 "30곳 이상"으로 표기합니다 (정확한 수는 04_validate.py 실행 로그).' : ''));
};

B.ABL = () => {
  const s = base('분석 결과 ③ 데이터 기여도', '데이터를 하나씩 빼면, 무엇이 보이지 않게 되는가');
  const hdr = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:10, valign:'middle' };
  const c = (t, o={}) => ({ text:t, options:Object.assign({ fontSize:10, valign:'middle', color:C.ink }, o) });
  const r = (t) => c(t, { bold:true, color:'C0612F', fontSize:9.5 });
  const sc = (a, b) => ({ text:[ { text:a, options:{ bold:true, breakLine:true } }, { text:b, options:{ fontSize:8, color:C.muted } } ], options:{ valign:'middle', fontSize:9.5 } });
  const rows = [
    [ {text:'빼는 데이터',options:hdr}, {text:'결과 변화',options:hdr} ],
    [ sc('기본 모델 (3종 결합)', '빠지는 정보 없음'), c('기준값') ],
    [ sc('DEM 제외 (평지 가정)', '오르막·내리막 경사'), r(`경사 반영 상위 10% 취약 건물의 ${V('ABL.dem_top10', '___%')}가 평지 기준으로는 상위 10% 밖`) ],
    [ sc('계단 레이어 제외', '휠체어 통행 불가 구간'), r(`휠체어 이동시간 평균 ${V('ABL.stairs', '___%')} 과소추정`) ],
    [ sc('500m 격자로 뭉뚱그림', '동네 안 경사 편차'), r(`HBI 1.8 이상 건물의 ${V('ABL.grid_hidden', '___%')}가 평균에 가려짐`) ],
  ];
  if (has('ABL.dem1m')) rows.push([ sc('DEM 5m ↔ 1m (관악구)', '해상도 차이'), c(`HBI 순위상관 ${V('ABL.dem1m')} → 5m로도 결론 유지`, { bold:true, fontSize:9.5 }) ]);
  const pub = has('ABL.pub_rho');
  if (pub) rows.push([ sc('공개데이터 대조군*', '공개 도보망 + 약 30m 지형'), r(`순위상관 ${Q('ABL.pub_rho', '')}, LX 1.3 이상 격자의 ${Q('ABL.pub_miss', '-')}를 놓침`) ]);
  TB(s, rows, { x:0.5, y:1.35, w:5.55, colW:[2.05,3.5], rowH:[0.34, ...rows.slice(1).map(() => (rows.length > 6 ? 0.355 : rows.length > 5 ? 0.44 : 0.56))], fontFace:F, border:{type:'solid',color:C.line,pt:0.75} });
  const rk = IMG('ranks');
  if (rk) {
    s.addImage({ path: rk, x:6.2, y:1.3, w:3.3, h:2.66 });
  } else {
    ph(s, 6.2, 1.35, 3.3, 2.55, '순위 역전 산점도\n격자별 평지 기준 vs 경사 반영 왕복 시간', 10, 'img:ranks');
  }
  const cy = rows.length > 6 ? 4.2 : 4.05, ch = rows.length > 6 ? 0.8 : 0.95;   // 표가 7줄이면 결론 카드를 조금 아래로
  card(s, 0.5, cy, 9, ch, C.dark);
  T(s, [
    { text:'결론: ', options:{ bold:true, color:C.orange } },
    { text:`DEM 없이 분석하면 가장 취약한 건물의 ${V('ABL.dem_top10', '___%')}를 놓칩니다. LX 데이터 3종은 "있으면 좋은" 데이터가 아니라 이 문제를 볼 수 있게 하는 유일한 데이터입니다.`, options:{ bold:true, color:C.white } },
  ], { x:0.75, y:cy, w:8.5, h:ch, fontSize:rows.length > 6 ? 11 : 11.5, valign:'middle' });
  src(s, pub ? `* 공개데이터 대조군 (공통 격자 ${Q('ABL.pub_n', '-')}개): ${Q('ABL.pub_note', '')}`
            : `순위상관(경사 반영 vs 평지, Spearman) ${V('ABL.rank_corr', '____')} · 그림: 250m 격자, 주황 = 평지 기준 '가까움'인데 HBI 1.8 이상`);
  if (pub) s.addNotes(`경사 반영 vs 평지 순위상관 ${Q('ABL.rank_corr', '-')}. 공개데이터 대조군은 tools/public_baseline.py 결과(results/public_baseline/compare_station.csv).`);
  s.addNotes('본선 데이터 활용성 30점의 "분석결과 미개방데이터 활용 기여도"에 직접 답하는 장표입니다.');
};

B.CROSS = () => {
  const s = base('분석 결과 ④ 상호제공데이터 연계', '경사는 실제로 어르신의 외출을 줄이고 있는가');
  card(s, 0.5, 1.4, 4.3, 1.3, C.dark);
  T(s, '가설', { x:0.7, y:1.5, w:4, h:0.28, fontSize:11, bold:true, color:C.orange });
  T(s, 'HBI가 높은 행정동일수록, 거주 고령인구 대비 고령자 유동인구가 적다', { x:0.7, y:1.8, w:3.95, h:0.8, fontSize:12, bold:true, color:C.white });
  card(s, 0.5, 2.85, 4.3, 1.1);
  T(s, '외출 지수', { x:0.7, y:2.95, w:4, h:0.28, fontSize:11, bold:true, color:C.dark });
  T(s, '= 65세 이상 유동인구(SKT) ÷ 65세 이상 거주인구(주민등록)\n시간대별로 비교해 낮 시간 외출 패턴 확인', { x:0.7, y:3.25, w:3.95, h:0.65, fontSize:9.8, color:C.muted });
  card(s, 0.5, 4.1, 4.3, 0.9, C.paleO);
  T(s, `중첩 분석: HBI 상위 25% × KCB 소득 하위 25% 행정동 ${V('CROSS.kcb_overlap', '___곳')} → 이동과 경제 부담이 겹친 최우선 지역`, { x:0.7, y:4.1, w:3.95, h:0.9, fontSize:10, bold:true, color:C.dark, valign:'middle' });
  const skt = IMG('skt');
  if (skt) s.addImage({ path: skt, x:5.1, y:1.4, w:4.4, h:2.75 });
  else ph(s, 5.1, 1.4, 4.4, 2.75, `산점도 삽입\nx: 행정동 평균 HBI · y: 외출 지수\n상관계수 r = ${V('CROSS.skt_r', '____')} (p = ${V('CROSS.skt_p', '____')})`, 10.5, 'img:skt');
  T(s, [
    { text:'결과 해석: ', options:{ bold:true, color:C.orange } },
    { text:V('CROSS.interp', '____________________________'), options:{ bold:true, color:C.dark } },
  ], { x:5.1, y:4.25, w:4.4, h:has('CROSS.points') ? 0.55 : 0.75, fontSize:10.5, valign:'top' });
  if (has('CROSS.points')) T(s, '보조 근거 · ' + Q('CROSS.points', ''), { x:5.1, y:4.82, w:4.4, h:0.36, fontSize:7.5, color:C.muted });
  src(s, '※ SKT·KCB 데이터의 공간 단위와 연계 가능 여부는 제공 명세 및 사무국 확인 후 확정');
  s.addNotes('상호제공데이터 연계 가점 장표. 가설이 기각되더라도 그 자체가 인사이트이니 결과를 그대로 보고합니다.');
};

B.IMPACT = () => {
  const s = base('기대효과와 확산', '서울의 언덕에서 시작해 전국으로');
  const impact = `후보지 ${V('IMPACT.n_sites', '___곳')} 설치 시 고령자 약 ${V('IMPACT.people')}명 수혜`;
  const impact2 = `1회 왕복마다 합계 약 ${V('IMPACT.minutes', '___분')} 단축`;
  const cols = [
    ['공익적 효과', C.dark, [impact, impact2, ...(has('IMPACT.joined') ? [`HBI 1.8 이상 거주 추정: ${Q('IMPACT.joined', '')}`] : []), '민원 이전에 취약지를 먼저 발견']],
    ['산업적 효과', C.orange, ['지도앱 도보 경로에 경사 반영 옵션', '휠체어·유아차 이용자용 경로 안내', '부동산·돌봄 서비스의 입지 분석 지표']],
    ['확산 가능성', C.sage, ['국토정보필지는 전국 단위로 제공', 'DEM 확보 시 부산 산복도로 등 구릉지 도시로 확장', '연 1회 갱신으로 시설 설치 효과 추적']],
  ];
  cols.forEach((c, i) => {
    const x = 0.5 + i*3.05;
    card(s, x, 1.35, 2.85, 2.7);
    s.addShape(pres.shapes.OVAL, { x:x+0.2, y:1.48, w:0.35, h:0.35, fill:{color:c[1]}, line:{color:c[1]} });
    T(s, c[0], { x:x+0.65, y:1.48, w:2.0, h:0.35, fontSize:13.5, bold:true, valign:'middle' });
    const n = c[2].length;
    if (n <= 3) {
      c[2].forEach((t, j) => {
        const hot = t === impact || t === impact2;
        T(s, t, { x:x+0.2, y:2.0 + j*0.68, w:2.45, h:0.62, fontSize:10.5, color: t.includes('___')?'C0612F':(hot?C.orange:C.ink), bold: hot });
      });
    } else {
      // 항목이 4개(동별 통계 추정 줄 포함)면 글자 수로 줄 수를 어림해 차례로 쌓음 (10pt 에서 한 줄 약 28자)
      let y = 1.98;
      c[2].forEach((t) => {
        const hot = t === impact || t === impact2;
        const h = Math.max(1, Math.ceil(t.length / 28)) * 0.175 + 0.06;
        T(s, t, { x:x+0.2, y, w:2.45, h, fontSize:10, color: t.includes('___')?'C0612F':(hot?C.orange:C.ink), bold: hot });
        y += h + 0.12;
      });
    }
  });
  // 서비스명 evenly
  card(s, 0.5, 4.17, 9, 0.85, C.dark);
  T(s, [ { text:'even', options:{ color:C.white } }, { text:'ly', options:{ color:C.sage } } ], { x:0.75, y:4.17, w:1.7, h:0.85, fontSize:30, bold:true, valign:'middle' });
  T(s, [
    { text:'서비스명 evenly(이븐리) — even = 평평한 + 공평한', options:{ bold:true, color:C.white, breakLine:true } },
    { text:'기울어진 길의 부담을 드러내, 어디에 살든 같은 7분이 되도록 돕는 접근성 지도', options:{ color:'CFE0D4' } },
  ], { x:2.5, y:4.17, w:6.8, h:0.85, fontSize:11.5, valign:'middle', lineSpacingMultiple:1.1 });
  if (has('IMPACT.minutes')) T(s, Q('IMPACT.note', ''), { x:0.5, y:5.07, w:8.5, h:0.3, fontSize:7, color:C.muted });
  s.addNotes('본선 실현 가능성 30점의 기대효과와 확산 가능성 항목. 공익 효과는 v5 개입 시뮬레이션(intervention_dong.csv)과 행정동 65세 이상 인구로 계산한 1회 왕복 기준 값입니다. 연간 환산은 출처 있는 외출 빈도 가정이 없어 넣지 않았습니다. 서비스명 evenly 는 이 장과 마지막 장에서 소개합니다.');
};

B.PLAN = () => {
  const s = base('실행 전략과 한계', '작게 검증하고, 넓게 확장합니다');
  const plan = [['1단계', '파일럿 구 분석\n현장 실측 보정'], ['2단계', '자치구 1곳과\n후보지 검토'], ['3단계', '서울 전역\n우선순위 지도'], ['4단계', '서울시에 후보지\n목록 제안'], ['5단계', '웹 지도 공개\n연 1회 갱신']];
  plan.forEach((p, i) => {
    const x = 0.5 + i*1.83;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:1.35, w:1.65, h:1.1, fill:{color: i==3?C.orange:C.dark}, line:{color: i==3?C.orange:C.dark}, rectRadius:0.08 });
    T(s, p[0], { x:x+0.15, y:1.45, w:1.4, h:0.3, fontSize:12, bold:true, color:C.white });
    T(s, p[1], { x:x+0.15, y:1.78, w:1.4, h:0.6, fontSize:10.5, color:C.white, lineSpacingMultiple:1.1 });
  });
  T(s, '알고 있는 한계와 대응', { x:0.5, y:2.6, w:5, h:0.3, fontSize:13, bold:true, color:C.dark });
  const lim = [
    ['보도 폭·노면·불법 주정차 미반영', '파일럿 경로 현장 실측 보행시간과 비교해 보정계수 적용'],
    ['건물별 거주 고령자 수 미상', '행정동 고령인구를 주거 연면적 비율로 배분한 추정치 사용'],
    ['DEM 5m 해상도 한계', '관악구 DEM 1m 결과와 비교, 가정별 민감도 분석 (부록)'],
    ['약국 데이터 미포함', '공개 경로로 자동 수집이 안 돼 의료시설(건물 용도)로 대체'],
    ['DEM(2021)·수치지형도(2024) 시점 차이', '그 사이 새로 난 길·절토 구간은 경사 오차 가능 → 현장 확인'],
  ];
  lim.forEach((l, i) => {
    const y = 2.98 + i*0.43;
    card(s, 0.5, y, 9, 0.37);
    T(s, l[0], { x:0.7, y, w:3.4, h:0.37, fontSize:10, bold:true, color:C.orange, valign:'middle' });
    T(s, l[1], { x:4.1, y, w:5.25, h:0.37, fontSize:10, color:C.ink, valign:'middle' });
  });
  s.addNotes('한계를 먼저 밝히면 질의응답이 쉬워집니다. 예상 질문 대부분이 이 다섯 가지에서 나옵니다. DEM은 2021년 기준, 수치지형도는 2024년 기준이라 그 사이 생긴 길은 고도와 선형이 어긋날 수 있습니다. 약국은 v4 분석 코드에 포함되지 않았고 의료시설로 대체했습니다.');
};

B.AP1 = () => {
  const s = base('부록 1. 활용 데이터 목록', '활용 데이터 목록', { appendix:true });
  const hdr = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:9, valign:'middle' };
  const c = (t, o={}) => ({ text:t, options:Object.assign({ fontSize:8.5, valign:'middle', color:C.ink }, o) });
  const rows = [
    ['미개방', '한국국토정보공사', '국토정보필지_전국 (방문 시 제공)', '2024.06~2025.07', '건물 결과를 필지에 결합'],
    ['미개방', '한국국토정보공사', '수치지형도_수도권 (도로·보도·계단·건물·정거장)', '2024.11', '보행 네트워크, 출발점·목적지'],
    ['미개방', '한국국토정보공사', 'DEM 5M_수도권', '2024.11 (2021 기준)', '링크별 경사 산출'],
    ['미개방', '한국국토정보공사', 'DEM 1M (관악구 일대)', '2024.11', '해상도 민감도 비교'],
    ['상호제공', 'SKT', '성·연령별, 요일별, 시간대별 유동인구', '2024.01~2024.12', '고령자 외출 지수 검증'],
    ['상호제공', '코리아크레딧뷰로', '행정동 단위 소득관련 통계정보', '2020.01~2023.12', '저소득 고령층 중첩 분석'],
    ['공개', 'vuski/admdongkor', '행정동 경계 (ver20250401)', '2025.04', '행정동 집계, 지도 배경'],
    ['공개', '서울시', '고지대 이동편의시설 우선설치대상지 5곳', '2025.06', '모델 검증 정답지'],
    ['공개', '행정안전부', '주민등록 인구통계(행정동 연령별)', '2025', '고령인구 추정 (반출 후)'],
  ];
  s.addTable([ ['구분','제공기관','데이터명','기간','활용 용도'].map(t=>({text:t,options:hdr})),
    ...rows.map(r => r.map((t,i) => c(t, i==0?{bold:true,color: t=='미개방'?C.orange:C.dark}:{}))) ],
    { x:0.5, y:1.3, w:9, colW:[0.8,1.45,3.2,1.45,2.1], rowH:0.365, fontFace:F, border:{type:'solid',color:C.line,pt:0.75} });
  src(s, '약국 위치는 공개 경로로 자동 수집이 안 돼 이번 분석에서 제외(의료시설로 대체). 원자료는 안심구역 밖으로 반출하지 않음');
};

B.AP4 = () => {
  const s = base('부록 4. 민감도 분석', '가정을 바꿔도 "누가 가장 취약한가"는 그대로인가', { appendix:true, tsize:22 });
  const hdr = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:10, align:'center', valign:'middle' };
  const c = (t, o={}) => ({ text:t, options:Object.assign({ fontSize:10, align:'center', valign:'middle', color:C.ink }, o) });
  const rows = TBL('APPX.sens');
  const head = ['시나리오', 'HBI 중앙값', 'HBI 1.8 이상 비율', '순위상관 (기본 대비)', '상위 10% 일치율'].map(t => ({ text:t, options:hdr }));
  const body = rows
    ? rows.map((r, i) => r.map((t, j) => c(t == null ? '—' : t, j == 0 ? { align:'left', bold:true, fill:{color: i==0?C.paleO:C.white} } : (i==0 ? { fill:{color:C.paleO} } : {}))))
    : ['기본값', '보행속도 0.7m/s', '보행속도 1.0m/s', '내리막 부담 0%(Tobler 원식)', '내리막 부담 100%', '계단 가중 1.5', '경사 절단 30%']
        .map(n => [ c(n, { align:'left', bold:true }), ...[0,1,2,3].map(() => c('___', { bold:true, color:'C0612F' })) ]);
  TB(s, [head, ...body], { x:0.5, y:1.35, w:9, colW:[2.8,1.4,1.6,1.7,1.5], rowH:0.36, fontFace:F, border:{type:'solid',color:C.line,pt:0.75} }, rows ? undefined : 'tbl:APPX.sens');
  card(s, 0.5, 4.35, 9, 0.7, C.tint);
  T(s, '순위상관·상위 10% 일치율이 1(100%)에 가까울수록, 보행속도나 내리막 가정을 바꿔도 "가장 먼저 도와야 할 곳"의 순서가 유지된다는 뜻입니다. 속도는 시간만 바꾸고 HBI(비율)는 거의 바꾸지 않습니다.',
    { x:0.7, y:4.35, w:8.6, h:0.7, fontSize:10, color:C.ink, valign:'middle' });
  src(s, '의료시설 기준, 08_sensitivity.py (네트워크는 그대로 두고 설정값만 바꿔 재계산)');
  s.addNotes('질의응답 대비 장표. "보행속도나 내리막 가정을 바꾸면요?"에 숫자로 답합니다.');
};

B.AP2 = () => {
  const s = base('부록 2. 분석 기술', '분석 환경과 기술 스택', { appendix:true });
  const items = [
    ['실행 환경', 'QGIS 3.32 내장 Python', '안심구역 분석 PC 기본 환경. 별도 설치 없이 실행 (반입은 txt 번들 1개)'],
    ['공간·래스터 처리', 'GDAL/OGR (osgeo) · numpy', '수치지형도 shp 읽기, 좌표계 변환, 링크 분할, DEM 끝점 고도 샘플링'],
    ['네트워크 분석', '자체 다익스트라 (lib/qgraph.py)', '방향 그래프, 다중 출발점 최단시간. scipy 가 있으면 scipy.sparse.csgraph 사용'],
    ['통계 검증', 'numpy (scipy 선택)', 'Spearman 순위상관, 실측-예측 상관, 기여도·민감도 분석'],
    ['시각화', 'QGIS · matplotlib(있을 때)', '격자 GPKG 를 QGIS로 색칠, 데모는 html 한 파일(외부 요청 없음)'],
  ];
  items.forEach((it, i) => {
    const y = 1.35 + i*0.74;
    card(s, 0.5, y, 9, 0.64, i%2?C.white:C.tint);
    T(s, it[0], { x:0.7, y, w:1.5, h:0.64, fontSize:11, bold:true, color:C.dark, valign:'middle' });
    T(s, it[1], { x:2.2, y, w:2.9, h:0.64, fontSize:10, bold:true, color:C.orange, valign:'middle' });
    T(s, it[2], { x:5.1, y, w:4.25, h:0.64, fontSize:10, valign:'middle' });
  });
};

B.AP3 = () => {
  const s = base('부록 3. 핵심 분석 코드', '경사 비용과 언덕 부담 지수 계산', { appendix:true });
  const code = [
"# analysis/hbi/lib/model.py 발췌 (QGIS 내장 Python, numpy)",
"def tobler(s):                                  # 경사 s → 보행속도 km/h",
"    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))",
"FLAT = tobler(0.0)",
"",
"def elder_time(length, s, stair):               # 고령자 링크 통과 시간(초)",
"    s = np.where(stair, np.sign(s + 1e-9) * np.maximum(np.abs(s), 0.25), s)",
"    up = FLAT / tobler(np.abs(s))",
"    down = 1 + C.DOWNHILL_WEIGHT * (up - 1)     # 내리막 = 오르막 부담의 50%",
"    factor = np.where(s >= 0, FLAT / tobler(s), down)",
"    t = length / C.ELDER_SPEED * factor         # 0.8 m/s",
"    return np.where(stair, t * C.STAIR_FACTOR, t)",
"",
"def wheel_time(length, s, stair):                # 휠체어: 계단 통행 불가",
"    t = length / (C.WHEEL_SPEED * np.maximum(0.4, 1 - 5 * np.maximum(s, 0)))",
"    t = np.where(np.abs(s) > C.WHEEL_LIMIT, t * C.WHEEL_STEEP_PENALTY, t)   # 1/12 초과 10배",
"    return np.where(stair, np.inf, t)",
"",
"# 왕복: go = G.dijkstra(dests, reverse=True) (집→시설), back = G.dijkstra(dests) (시설→집)",
"# HBI = (go + back)[고령자] ÷ (go + back)[평지 가정]",
"",
"# analysis/hbi/lib/qgraph.py 발췌 — Graph.dijkstra (scipy 없을 때의 자체 구현)",
"    dist = np.full(self.n, np.inf); dist[sources] = 0.0",
"    h = [(0.0, int(s)) for s in sources]; heapq.heapify(h)",
"    while h:",
"        d, x = heapq.heappop(h)",
"        if d > dist[x]: continue",
"        for k in range(ptr[x], ptr[x + 1]):",
"            y, nd = nb[k], d + wt[k]",
"            if nd < dist[y]: dist[y] = nd; heapq.heappush(h, (nd, int(y)))",
  ].join('\n');
  card(s, 0.5, 1.3, 9, 3.85, 'F4F6F4');
  T(s, code, { x:0.7, y:1.36, w:8.6, h:3.75, fontFace:'Courier New', fontSize:7.2, color:C.ink });
  s.addNotes('실제 반입 코드(analysis/hbi/lib/model.py, lib/qgraph.py)에서 발췌·축약. 전체 코드는 반입 번들(hbi_code_bundle_*.txt)과 같습니다.');
};

// 1 COVER
{
  const s = pres.addSlide(); page++;
  s.background = { color: C.dark };
  s.addImage({ path: img('contour_dark.png'), x:0, y:0, w:10, h:5.625 });
  T(s, '한국국토정보공사 데이터 활용 아이디어 제안', { x:0.6, y:0.7, w:8, h:0.3, fontSize:12, color:'B9CFC0' });
  T(s, '언덕 위 우리동네', { x:0.6, y:1.4, w:8.5, h:0.9, fontSize:44, bold:true, color:C.white });
  T(s, '경사 반영 이동약자 접근성 지도', { x:0.6, y:2.3, w:8.5, h:0.5, fontSize:24, color:C.white });
  T(s, '지도앱의 7분이, 누군가에게는 14분입니다.', { x:0.6, y:3.15, w:8.5, h:0.4, fontSize:16, bold:true, color:C.orange });
  T(s, `팀명 ${V('team_name', '○○○')}  |  2026.10`, { x:0.6, y:4.75, w:6, h:0.3, fontSize:11, color:'B9CFC0' });
  wm(s);
  s.addNotes('표지. "지도앱의 7분이 누군가에게는 14분"이라는 한 문장으로 시작합니다.');
}

// 2 HOOK
{
  const s = base('01  한 사람의 귀갓길', '같은 450m, 다른 거리');
  s.addImage({ path: img('profile.png'), x:0.35, y:1.45, w:5.6, h:2.71 });
  const rows = [
    ['7분', '지도앱 도보 안내', '평지 · 성인 보행속도 기준', C.sage],
    ['9분', '같은 길, 고령자 보행속도', '경사는 아직 반영 전', C.muted],
    ['14분', '오르막 경사까지 반영하면', '지도앱 안내의 2배', C.orange],
  ];
  rows.forEach((r, i) => {
    const y = 1.45 + i*1.0;
    card(s, 6.2, y, 3.3, 0.85, i==2 ? C.paleO : C.tint);
    T(s, r[0], { x:6.35, y:y+0.12, w:1.2, h:0.6, fontSize:i==2?30:26, bold:true, color:r[3], valign:'middle' });
    T(s, r[1], { x:7.55, y:y+0.16, w:1.9, h:0.3, fontSize:11.5, bold:true });
    T(s, r[2], { x:7.55, y:y+0.46, w:1.9, h:0.26, fontSize:9.5, color:C.muted });
  });
  T(s, '집은 언덕 위, 약국은 언덕 아래. 가는 길은 내리막이지만 돌아오는 길은 고도 54m를 올라야 합니다.', { x:0.5, y:4.45, w:9, h:0.5, fontSize:13, color:C.ink });
  src(s, '가정: 성인 1.1m/s, 고령자 0.8m/s, 평균 경사 12% 오르막 / 경사 보정은 Tobler 보행함수 적용 / 팀 자체 산출');
  s.addNotes('핵심 후킹 장표. 같은 길을 세 번 계산합니다. 지도앱 7분, 고령자 평지 9분, 경사 반영 14분. 지도에는 이 차이가 표시되지 않습니다.');
}

// 3 PERSONA
{
  const s = base('01  한 사람의 귀갓길', '김순자 할머니(78)의 "약 받는 날"');
  T(s, '※ 실제 보도·연구 사례를 바탕으로 구성한 가상 인물입니다', { x:0.5, y:1.12, w:6, h:0.25, fontSize:9.5, color:C.muted });
  const steps = [
    ['09:30', '집을 나선다', '내리막이라 금방이지만 무릎이 먼저 긴장한다. 내려가는 길은 넘어질까 무섭다.'],
    ['09:40', '약국 도착', '고혈압·관절약 3주치를 받는다. 약봉투가 생각보다 무겁다.'],
    ['09:50', '돌아오는 길', '오르막 중간에서 두 번 멈춘다. 전봇대와 남의 집 담벼락이 쉼터다.'],
    ['다음 달', '약 받는 날을 미룬다', '비 오는 날, 눈 오는 날, 폭염인 날은 나가지 않는다. 그렇게 한 주가 밀린다.'],
  ];
  steps.forEach((st, i) => {
    const x = 0.5 + i*2.3;
    const hot = i==3;
    card(s, x, 1.55, 2.1, 2.45, hot ? C.paleO : C.tint);
    T(s, st[0], { x:x+0.18, y:1.72, w:1.8, h:0.35, fontSize:16, bold:true, color: hot?C.orange:C.dark });
    T(s, st[1], { x:x+0.18, y:2.12, w:1.8, h:0.3, fontSize:12.5, bold:true });
    T(s, st[2], { x:x+0.18, y:2.5, w:1.78, h:1.4, fontSize:10.5, color:C.muted, lineSpacingMultiple:1.2 });
    if (i<3) s.addShape(pres.shapes.CHEVRON, { x:x+2.12, y:2.66, w:0.16, h:0.22, fill:{color:C.sage}, line:{color:C.sage} });
  });
  card(s, 0.5, 4.2, 9, 0.8, C.dark);
  T(s, [
    { text:'문제는 거리가 아니라 "돌아오는 오르막"입니다. ', options:{ bold:true, color:C.white } },
    { text:'그리고 이 부담은 지금 어떤 지도에도 표시되지 않습니다.', options:{ color:'CFE0D4' } },
  ], { x:0.75, y:4.2, w:8.5, h:0.8, fontSize:13.5, valign:'middle' });
  s.addNotes('숫자 전에 사람을 먼저 보여줍니다. 가상 인물임을 반드시 밝히고, 실제 사례는 다음 장들에서 근거로 제시합니다.');
}

// 4 SCALE
{
  const s = base('02  문제의 규모', '한 사람의 이야기가 아닙니다');
  const stats = [
    ['31%', '서울 면적 중 구릉지', '지하철 등 인프라 설치가 어렵고 저층 주거가 밀집한 지형'],
    ['20.43%', '서울 65세 이상 인구 비중', '2025년 처음으로 20%를 넘어 초고령 도시에 진입'],
    ['51곳', '구릉지 고령자 이동취약지역', '해당 지역 거주 고령인구 16,773명, 25개 구 중 17개 구에 분포'],
    ['420m', '75세 이상 고령자의 평균 이동거리', '가까운 공원시설 조건에서 측정된 후기고령자의 보행 한계'],
  ];
  stats.forEach((st, i) => {
    const x = 0.5 + (i%2)*4.6, y = 1.45 + Math.floor(i/2)*1.8;
    card(s, x, y, 4.4, 1.6);
    T(s, st[0], { x:x+0.25, y:y+0.2, w:2.0, h:0.75, fontSize:st[0].length>5?27:32, bold:true, color:C.orange, valign:'middle' });
    T(s, st[1], { x:x+2.3, y:y+0.28, w:1.95, h:0.6, fontSize:12.5, bold:true, valign:'middle' });
    T(s, st[2], { x:x+0.25, y:y+1.0, w:3.95, h:0.5, fontSize:10, color:C.muted });
  });
  src(s, '출처: GIS 분석을 통한 구릉지 고령자 이동취약지역 분석 연구(한국공간디자인학회 논문집) / 행정안전부 2025년 주민등록 인구통계 / 이소민·오성훈(2025), 토지주택연구 16(1)');
  s.addNotes('서울 면적의 31%가 구릉지이고, 서울은 2025년 처음 고령인구 20%를 넘었습니다. 선행연구는 이미 51곳의 이동취약지역을 찾아냈습니다.');
}

// 5 REAL CASES
{
  const s = base('03  실제 사례', '지도와 현실의 괴리는 이미 현장에서 확인됩니다');
  const cs = [
    ['중구 신당동', '대현산배수지공원', '계단 190개, 약 110m 구간. 휠체어 이용자는 약 770m를 돌아가야 했다.', '곡선형 모노레일 설치, 3~4분 만에 공원 도착'],
    ['종로구 숭인동', '창신역 일대 계단', '길이 115m, 경사 30도 이상의 급경사 계단. 인근 학생 통학로로도 쓰인다.', '경사형 엘리베이터 추진, 2027년 준공 목표'],
    ['관악구 봉천동', '비안어린이공원 인근', '역 근처에서 장을 본 주민들이 가파른 계단을 피해 200m 이상 우회해 왔다.', '수직 엘리베이터와 데크길 추진'],
  ];
  cs.forEach((c, i) => {
    const x = 0.5 + i*3.05;
    card(s, x, 1.45, 2.85, 2.55);
    T(s, c[0], { x:x+0.2, y:1.6, w:2.5, h:0.25, fontSize:10, bold:true, color:C.orange });
    T(s, c[1], { x:x+0.2, y:1.88, w:2.5, h:0.32, fontSize:13.5, bold:true });
    T(s, c[2], { x:x+0.2, y:2.3, w:2.48, h:0.95, fontSize:10.5, color:C.ink, lineSpacingMultiple:1.15 });
    T(s, '→ ' + c[3], { x:x+0.2, y:3.35, w:2.48, h:0.55, fontSize:10, bold:true, color:C.dark });
  });
  card(s, 0.5, 4.2, 9, 0.85, C.paleO);
  T(s, '110m', { x:0.75, y:4.25, w:1.3, h:0.75, fontSize:26, bold:true, color:C.dark, valign:'middle' });
  T(s, '→', { x:2.0, y:4.25, w:0.4, h:0.75, fontSize:22, color:C.orange, valign:'middle' });
  T(s, '770m', { x:2.4, y:4.25, w:1.4, h:0.75, fontSize:26, bold:true, color:C.orange, valign:'middle' });
  T(s, '휠체어 이용자에게 같은 목적지는 약 7배 멀었습니다. 이 차이를 사전에 찾아낼 도구가 필요합니다.', { x:3.9, y:4.25, w:5.4, h:0.75, fontSize:12, bold:true, valign:'middle' });
  src(s, '출처: 서울시 구릉지 이동편의 개선사업 보도자료(2020.11) / 내 손안에 서울(2025.06.13) 고지대 이동편의시설 우선 설치대상지 발표');
  s.addNotes('실제 서울시 사례입니다. 직선 110m를 휠체어로는 770m 돌아가야 했던 곳. 이런 곳을 민원 이전에 데이터로 찾는 것이 제안의 핵심입니다.');
}

// 6 POLICY TIMELINE
{
  const s = base('04  정책 흐름', '정책은 이미 움직이고 있습니다');
  const tl = [
    ['2018', '지역균형발전 구상에 구릉지 이동편의 개선 포함'],
    ['2020', '주민공모로 대상지 선정, 모노레일·경사형 엘리베이터 도입 시작'],
    ['2025', '후보지 25곳 중 5곳 우선 설치 대상 선정 (중곡·화곡·봉천·숭인·신당)'],
    ['2026', '서울시장 선거에서 고지대 이동약자 편의시설이 공약으로 재등장'],
    ['2027', '2025년 선정 5곳 준공 목표'],
  ];
  s.addShape(pres.shapes.LINE, { x:0.9, y:2.35, w:7.7, h:0, line:{ color:C.sage, width:2 } });
  tl.forEach((t, i) => {
    const x = 0.6 + i*1.85;
    const hot = i==2;
    s.addShape(pres.shapes.OVAL, { x:x+0.17, y:2.2, w:0.3, h:0.3, fill:{color: hot?C.orange:C.dark}, line:{color:C.white, width:2} });
    T(s, t[0], { x:x-0.1, y:1.6, w:0.85, h:0.45, fontSize:18, bold:true, color: hot?C.orange:C.dark, align:'center' });
    T(s, t[1], { x:x-0.12, y:2.7, w:1.62, h:1.1, fontSize:10.5, color:C.ink, lineSpacingMultiple:1.15 });
  });
  card(s, 0.5, 4.05, 9, 0.95, C.dark);
  T(s, [
    { text:'예산과 정책 의지는 이미 있습니다.\n', options:{ color:'CFE0D4', breakLine:true } },
    { text:'부족한 것은 "어디가 가장 급한가"에 대한 서울 전역 단위의 객관적 근거입니다.', options:{ bold:true, color:C.white } },
  ], { x:0.75, y:4.05, w:8.5, h:0.95, fontSize:13, valign:'middle' });
  src(s, '출처: 내 손안에 서울(2020.01, 2025.06) / 서울시 보도자료(2020.11) / 뉴스1(2026.05.11)');
  s.addNotes('이 제안은 새로운 정책을 만들자는 것이 아니라, 이미 진행 중인 정책의 입지 선정을 데이터로 돕자는 것입니다. 심사에서 실현 가능성을 보여주는 장표입니다.');
}

// 7 PROBLEM DEFINITION
{
  const s = base('05  문제 정의', '서울에서 가장 먼저 엘리베이터가 필요한 곳은 어디인가?', { tsize:22 });
  card(s, 0.5, 1.45, 4.3, 3.55);
  T(s, '지금의 방식', { x:0.75, y:1.6, w:3.8, h:0.35, fontSize:14, bold:true, color:C.muted });
  T(s, '공모·신청으로 올라온 후보지를 선정위원회가 심사', { x:0.75, y:1.98, w:3.85, h:0.5, fontSize:11, color:C.ink });
  const lim = [
    '목소리를 내기 어려운 곳은 후보에도 오르지 못한다. 거동이 불편한 사람일수록 민원도 어렵다.',
    '후보지끼리 비교할 공통 기준이 없다.',
    '설치 후 몇 명이 얼마나 편해지는지 수치로 말하기 어렵다.',
  ];
  lim.forEach((l, i) => {
    circleNum(s, 0.75, 2.6 + i*0.78, i+1, C.muted);
    T(s, l, { x:1.3, y:2.58 + i*0.78, w:3.35, h:0.7, fontSize:10.5, color:C.ink, valign:'middle' });
  });
  card(s, 5.2, 1.45, 4.3, 3.55, C.dark);
  T(s, '우리의 방식', { x:5.45, y:1.6, w:3.8, h:0.35, fontSize:14, bold:true, color:C.orange });
  T(s, '데이터가 먼저 후보지를 찾는다', { x:5.45, y:1.98, w:3.85, h:0.5, fontSize:11, color:'CFE0D4' });
  const ans = [
    '서울 전역 주거 필지를 전수 스크리닝해서, 신청이 없어도 찾아낸다.',
    '모든 필지를 "언덕 부담 지수" 하나의 기준으로 비교한다.',
    '효과를 "몇 명 × 몇 분 단축"으로 계산한다.',
  ];
  ans.forEach((l, i) => {
    circleNum(s, 5.45, 2.6 + i*0.78, i+1, C.orange);
    T(s, l, { x:6.0, y:2.58 + i*0.78, w:3.35, h:0.7, fontSize:10.5, color:C.white, valign:'middle' });
  });
  s.addNotes('기존 방식을 비판하기보다 보완한다는 톤으로 설명합니다. 특히 목소리를 내기 어려운 곳이 누락될 수 있다는 점이 핵심입니다.');
}

// 8 PRIOR RESEARCH
{
  const s = base('06  선행연구 검토', '선행연구가 밝힌 것, 우리가 더하는 것');
  const hdr = { bold:true, color:C.white, fill:{color:C.dark}, fontSize:11, valign:'middle' };
  const cell = (t, o={}) => ({ text:t, options:Object.assign({ fontSize:9.5, color:C.ink, valign:'middle' }, o) });
  const rows = [
    [ {text:'연구',options:hdr}, {text:'주요 발견',options:hdr}, {text:'우리가 더하는 것',options:hdr} ],
    [ cell('이희연 외(2015)\n서울도시연구',{bold:true}), cell('경사지 저소득 노인 밀집지구는 녹지는 풍부하지만 보행환경이 열악하고 대중교통·공공시설 접근성이 불량'), cell('경사를 정량화해 보행시간으로 환산',{color:C.dark,bold:true}) ],
    [ cell('구릉지 고령자\n이동취약지역 연구',{bold:true}), cell('서울 구릉지 이동취약지역 51곳, 거주 고령인구 16,773명 도출'), cell('지역 단위에서 필지 단위로 세분화',{color:C.dark,bold:true}) ],
    [ cell('이소민·오성훈(2025)\n토지주택연구',{bold:true}), cell('후기고령자 평균 이동거리 약 420m, 보도 없는 보차혼용도로에서 경로 1.3배 증가'), cell('거리 한계에 경사 부담을 결합',{color:C.dark,bold:true}) ],
    [ cell('강현미·박소현(2009)\n대한건축학회논문집',{bold:true}), cell('구릉지 아파트단지에서 보행약자 이동 평가틀 제안'), cell('단지 단위에서 도시 전역으로 확장',{color:C.dark,bold:true}) ],
  ];
  s.addTable(rows, { x:0.5, y:1.4, w:9, colW:[1.9, 4.6, 2.5], rowH:[0.36,0.62,0.52,0.62,0.52], fontFace:F, border:{type:'solid', color:C.line, pt:0.75}, fill:{color:C.white} });
  const chips = ['필지 단위 분석', '오르막·내리막 방향 구분', '고령자·휠체어 사용자별 모델'];
  chips.forEach((c, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.5 + i*3.05, y:4.45, w:2.85, h:0.5, fill:{color:C.paleO}, line:{color:C.orange, width:1}, rectRadius:0.25 });
    T(s, c, { x:0.5 + i*3.05, y:4.45, w:2.85, h:0.5, fontSize:11.5, bold:true, color:C.dark, align:'center', valign:'middle' });
  });
  s.addNotes('선행연구를 충분히 검토했다는 신호를 주는 장표. 각 연구의 한계를 지적하기보다 "우리가 무엇을 더하는지"로 표현합니다.');
}

B.DATA();
B.LINK();
B.SAFE();
B.PRE();
// 10 FRAMEWORK
{
  const s = base('08  분석 프레임워크', '다섯 단계로 "체감 거리"를 계산합니다');
  const st = [
    ['대상지 스크리닝', 'DEM으로 구별 경사 편차를 계산해 파일럿 구 선정'],
    ['보행 네트워크', '수치지형도 도로·계단을 30m 이내 링크로 분할'],
    ['경사 가중치', '링크 양 끝 고도차로 오르막·내리막 방향별 가중'],
    ['건물별 접근성', '주거 건물에서 의료시설·정류장·지하철역·노유자시설까지 왕복 시간 계산'],
    ['우선순위', '언덕 부담 지수와 고령인구를 교차해 개입 지점 도출'],
  ];
  st.forEach((t, i) => {
    const x = 0.5 + i*1.83;
    card(s, x, 1.55, 1.65, 2.7, i==4 ? C.paleO : C.tint);
    circleNum(s, x+0.2, 1.72, i+1, i==4?C.orange:C.dark);
    T(s, t[0], { x:x+0.2, y:2.28, w:1.35, h:0.55, fontSize:12, bold:true });
    T(s, t[1], { x:x+0.2, y:2.85, w:1.33, h:1.3, fontSize:9.8, color:C.muted, lineSpacingMultiple:1.15 });
  });
  T(s, '도구: QGIS 3.32 내장 Python · numpy + GDAL/OGR · 자체 다익스트라(방향 그래프, scipy 있으면 사용) 최단시간 경로 탐색', { x:0.5, y:4.5, w:9, h:0.4, fontSize:10.5, color:C.dark, bold:true });
  s.addNotes('오르막과 내리막을 구분하는 방향 그래프가 기술적 핵심입니다. 같은 길이라도 가는 길과 오는 길의 비용이 다릅니다.');
}

// 11 MODEL
{
  const s = base('09  경사 가중 모델', '경사가 1% 오를 때마다, 길은 조금씩 길어집니다');
  const slopes = [0,2,4,6,8,10,12,14,16,18,20];
  const ratio = [1.00,1.07,1.15,1.23,1.32,1.42,1.52,1.63,1.75,1.88,2.01];
  s.addChart(pres.charts.LINE, [{ name:'평지 대비 소요시간 배수', labels:slopes.map(v=>v+'%'), values:ratio }], {
    x:0.4, y:1.3, w:5.3, h:3.6, fontFace:F, chartColors:[C.orange], lineSize:3, lineDataSymbol:'circle', lineDataSymbolSize:6,
    showTitle:true, title:'오르막 경사별 소요시간 배수 (Tobler 보행함수)', titleFontSize:11, titleColor:C.ink, titleFontFace:F,
    showValue:false, showLegend:false, catAxisLabelColor:C.muted, valAxisLabelColor:C.muted, catAxisLabelFontSize:9, valAxisLabelFontSize:9,
    valAxisMinVal:1, valAxisMaxVal:2.2, valAxisMajorUnit:0.2, valGridLine:{ color:'E5E9E6', size:0.5 }, catGridLine:{ style:'none' },
    showCatAxisTitle:true, catAxisTitle:'오르막 경사', catAxisTitleFontSize:9, catAxisTitleColor:C.muted,
  });
  card(s, 5.95, 1.35, 3.55, 1.65);
  T(s, '고령자 모델', { x:6.15, y:1.47, w:3.2, h:0.3, fontSize:13, bold:true, color:C.dark });
  T(s, '평지 기준속도 0.8m/s에 Tobler 보행함수로 경사를 반영. 12% 오르막이면 1.5배, 20%면 2배가 걸린다. 내리막은 낙상 위험 가중치를 별도로 둔다.', { x:6.15, y:1.8, w:3.2, h:1.15, fontSize:10, color:C.ink, lineSpacingMultiple:1.12 });
  card(s, 5.95, 3.15, 3.55, 1.75, C.paleO);
  T(s, '휠체어 모델', { x:6.15, y:3.27, w:3.2, h:0.3, fontSize:13, bold:true, color:C.orange });
  T(s, '경사로 법정 기준인 1/12(약 8.3%)을 넘는 구간은 자력 통행 한계로 보고 큰 패널티를 준다. 계단은 통행 불가로 처리해 실제 우회 경로를 찾는다.', { x:6.15, y:3.6, w:3.2, h:1.25, fontSize:10, color:C.ink, lineSpacingMultiple:1.12 });
  src(s, 'Tobler 보행함수 v = 6·exp(−3.5·|s+0.05|) km/h (s: 경사) / 휠체어 기준: 장애인등편의법 시행규칙 경사로 기울기');
  s.addNotes('검증된 보행함수를 사용해 자의적인 가중치가 아님을 보여줍니다. 고령자와 휠체어 사용자는 서로 다른 모델이 필요합니다.');
}

// 12 HBI
{
  const s = base('10  핵심 지표', '언덕 부담 지수 (HBI, Hill Burden Index)');
  card(s, 0.5, 1.4, 9, 0.95, C.dark);
  T(s, [
    { text:'HBI  =  ', options:{ bold:true, color:C.orange } },
    { text:'경사 반영 왕복 시간  ÷  평지 가정 왕복 시간', options:{ bold:true, color:C.white } },
  ], { x:0.8, y:1.4, w:8.4, h:0.62, fontSize:17, valign:'middle' });
  T(s, '집 → 시설 → 집 왕복 기준이라 언덕 위·아래 어디에 살든 같은 잣대. 1.0이면 평지와 같고, 2.0이면 두 배', { x:0.8, y:1.95, w:8.4, h:0.3, fontSize:10, color:'CFE0D4' });
  const bands = [['1.0 ~ 1.3', '평지 수준', C.sage], ['1.3 ~ 1.8', '체감 부담', 'E0A33B'], ['1.8 이상', '고립 위험', C.orange]];
  bands.forEach((b, i) => {
    const y = 2.6 + i*0.78;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.5, y, w:1.5, h:0.62, fill:{color:b[2]}, line:{color:b[2]}, rectRadius:0.08 });
    T(s, b[0], { x:0.5, y, w:1.5, h:0.62, fontSize:12.5, bold:true, color:C.white, align:'center', valign:'middle' });
    T(s, b[1], { x:2.15, y, w:1.6, h:0.62, fontSize:13, bold:true, valign:'middle' });
  });
  card(s, 4.3, 2.6, 5.2, 2.2, C.paleO);
  T(s, '예시: 김순자 할머니의 귀갓길 (편도 배수)', { x:4.55, y:2.75, w:4.8, h:0.3, fontSize:12, bold:true, color:C.dark });
  T(s, [
    { text:'14.3분', options:{ bold:true, color:C.orange } },
    { text:'  ÷  ', options:{ color:C.muted } },
    { text:'9.4분', options:{ bold:true, color:C.dark } },
    { text:'  =  ', options:{ color:C.muted } },
    { text:'1.52배', options:{ bold:true, color:C.orange } },
  ], { x:4.55, y:3.1, w:4.8, h:0.6, fontSize:22, valign:'middle' });
  T(s, '약국 → 집, 오르막 귀갓길만 본 "귀갓길 편도 배수"입니다. HBI는 가는 내리막 부담까지 더한 왕복으로 계산해 더 보수적입니다. "분" 단위라 누구나 이해할 수 있고, 설치 전후 효과도 같은 지표로 비교합니다.', { x:4.55, y:3.75, w:4.75, h:0.95, fontSize:10, color:C.ink });
  T(s, '구간 경계값은 파일럿 분석과 현장 실측으로 보정 예정', { x:0.5, y:5.0, w:4, h:0.25, fontSize:8.5, color:C.muted });
  s.addNotes('복잡한 모델을 한 숫자로 요약합니다. HBI는 왕복 기준(집 위치가 언덕 위든 아래든 공정), 1.52는 귀갓길 편도만 본 예시 배수입니다. 반출 결과의 summary.csv 에는 두 값(HBI 중앙값, 귀갓길 편도 배수 중앙값)이 모두 있습니다.');
}

B.RES1();
B.VALID();
B.ABL();
B.CROSS();
// 14 MATRIX
{
  const s = base('12  우선순위 도출', '어디에 먼저, 무엇을 할 것인가');
  const ox = 0.9, oy = 1.4, qw = 2.3, qh = 1.6;
  const q = [
    [0,0,'생활권 돌봄 강화','평지지만 고령자 밀집. 방문 돌봄, 쉼터', C.tint, C.ink],
    [1,0,'1순위 즉시 개입','경사형 엘리베이터, 모노레일, 마을버스', C.orange, C.white],
    [0,1,'모니터링','정기 재산출로 변화 추적', 'F4F6F4', C.muted],
    [1,1,'예방적 정비','계단 난간, 미끄럼 방지, 겨울철 제설', C.paleO, C.ink],
  ];
  q.forEach(v => {
    const x = ox + v[0]*(qw+0.1), y = oy + v[1]*(qh+0.1);
    card(s, x, y, qw, qh, v[4]);
    T(s, v[2], { x:x+0.2, y:y+0.25, w:qw-0.4, h:0.35, fontSize:13, bold:true, color:v[5] });
    T(s, v[3], { x:x+0.2, y:y+0.7, w:qw-0.4, h:0.75, fontSize:10, color:v[5] });
  });
  T(s, '↑ 고령인구 밀도', { x:0.5, y:1.12, w:2.5, h:0.25, fontSize:10, bold:true, color:C.muted });
  T(s, '언덕 부담 지수(HBI)  →', { x:ox, y:4.78, w:4.7, h:0.28, fontSize:10, bold:true, color:C.muted, align:'center' });
  card(s, 6.1, 1.4, 3.4, 3.3, C.dark);
  T(s, '후보지를 기다리지 않고,\n처음부터 찾습니다', { x:6.35, y:1.6, w:3.0, h:0.8, fontSize:14, bold:true, color:C.white });
  T(s, '2025년에는 후보지 25곳 중 5곳이 선정되었습니다. 이 지도는 서울 전역에서 같은 기준으로 후보지를 먼저 제시하고, 각 후보지의 예상 수혜 인원과 단축 시간을 함께 보여줍니다.', { x:6.35, y:2.5, w:2.95, h:2.1, fontSize:10.5, color:'CFE0D4', lineSpacingMultiple:1.2 });
  s.addNotes('두 축으로 개입 유형을 나눕니다. 모든 곳에 엘리베이터가 필요한 것은 아니며, 사분면별로 다른 처방을 제안합니다.');
}

// 15 USES
{
  const s = base('13  활용 방안', '누가, 어디에 쓰는가');
  const u = [
    ['이동편의시설 입지', '경사형 엘리베이터·모노레일 후보지를 수혜 인원 × 단축 시간으로 순위화', '서울시·자치구 균형발전 부서'],
    ['마을버스·정류장', '언덕 부담 지수가 높은 필지 밀집지로 노선·정류장 위치 조정', '자치구 교통 부서'],
    ['방문 의료·약 배송', '이동 부담이 큰 고령 가구를 방문간호·약 배송 우선 대상으로 선정', '보건소·복지관'],
    ['겨울철 제설·열선 계단', '결빙 시 부담이 급증하는 경사 구간에 제설·열선 우선 배치', '자치구 도로관리 부서'],
  ];
  u.forEach((v, i) => {
    const x = 0.5 + (i%2)*4.6, y = 1.4 + Math.floor(i/2)*1.8;
    card(s, x, y, 4.4, 1.6);
    circleNum(s, x+0.22, y+0.22, i+1, i==0?C.orange:C.dark);
    T(s, v[0], { x:x+0.8, y:y+0.24, w:3.4, h:0.38, fontSize:13.5, bold:true, valign:'middle' });
    T(s, v[1], { x:x+0.8, y:y+0.68, w:3.4, h:0.55, fontSize:10.2, color:C.ink });
    T(s, '활용 주체: ' + v[2], { x:x+0.8, y:y+1.22, w:3.4, h:0.25, fontSize:9, bold:true, color:C.orange });
  });
  s.addNotes('하나의 지도가 네 가지 정책에 바로 쓰일 수 있음을 보여줍니다. 활용 주체를 명시해 실현 가능성을 높입니다.');
}

// 16 ONE PERSON
{
  const iv = Q('ONE.mode', 'example') === 'intervention';
  const s = base('14  한 사람에게 돌아가는 변화', iv ? '선정지 시설 1기가 바꾸는 귀갓길' : '엘리베이터 한 대가 바꾸는 김순자 할머니의 귀갓길');
  if (!iv) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:7.95, y:0.3, w:1.55, h:0.3, fill:{color:C.paleO}, line:{color:C.orange, width:1}, rectRadius:0.15 });
    T(s, '예시 · 가정 시뮬레이션', { x:7.95, y:0.3, w:1.55, h:0.3, fontSize:8.5, bold:true, color:C.orange, align:'center', valign:'middle' });
    notes.push('참고: 22장 "한 사람의 변화"는 실측 구간(validation_routes.csv measured_min)과 선정지 개입 결과(intervention_summary.csv, v5)가 함께 있어야 계산됨 → 기존 예시(14분 → 약 10분)를 "예시" 배지와 함께 유지');
  }
  card(s, 0.5, 1.4, 3.9, 2.55);
  T(s, iv ? '지금 (수혜 주거 건물 평균)' : '지금', { x:0.75, y:1.55, w:3.4, h:0.3, fontSize:12, bold:true, color:C.muted });
  T(s, iv ? `HBI ${V('ONE.hbi_before')}` : '14분', { x:0.75, y:1.9, w:3.5, h:0.7, fontSize:iv?32:36, bold:true, color:C.orange });
  T(s, iv ? `실측 구간 ${V('ONE.route')}: 팀 실측 ${V('ONE.measured')}\n모델 예측 ${V('ONE.route_model')} (성인 1.1m/s)` : '귀갓길 배수 1.52 · 오르막에서 두 번 휴식\n궂은 날에는 약 받는 날을 미룸',
    { x:0.75, y:2.7, w:3.5, h:0.9, fontSize:11, color:C.ink, lineSpacingMultiple:1.2 });
  s.addShape(pres.shapes.RIGHT_ARROW, { x:4.55, y:2.4, w:0.6, h:0.5, fill:{color:C.orange}, line:{color:C.orange} });
  card(s, 5.3, 1.4, 4.2, 2.55, C.dark);
  T(s, iv ? `${V('ONE.facility')} 설치 후` : '가장 가파른 150m 구간에 경사형 엘리베이터 1기', { x:5.55, y:1.55, w:3.8, h:0.3, fontSize:11, bold:true, color:'CFE0D4' });
  T(s, iv ? `HBI ${V('ONE.hbi_after')}` : '약 10분', { x:5.55, y:1.9, w:3.7, h:0.7, fontSize:iv?32:36, bold:true, color:C.white });
  T(s, iv ? `왕복 평균 ${V('ONE.saved')}분 단축 (최대 ${V('ONE.saved_max')}분)\n수혜 주거 건물 ${V('ONE.n_benefit')}동` : '배수 약 1.0 · 평지와 같은 부담\n쉬지 않고 집에 도착',
    { x:5.55, y:2.7, w:3.7, h:0.9, fontSize:11, color:C.white, lineSpacingMultiple:1.2 });
  card(s, 0.5, 4.15, 9, 0.9, C.paleO);
  T(s, [
    { text:'이 계산을 집집마다 반복하면, ', options:{ color:C.ink } },
    { text:'"엘리베이터 1기가 몇 명의 하루에서 몇 분을 돌려주는가"', options:{ bold:true, color:C.dark } },
    { text:'를 설치 전에 알 수 있습니다.', options:{ color:C.ink } },
  ], { x:0.75, y:4.15, w:8.5, h:0.9, fontSize:12.5, valign:'middle' });
  src(s, iv
    ? '모델 산출: intervention_summary.csv 선정지 행(설치 전·후 HBI, 왕복 단축 분) / 실측 구간은 모델 검증용 (validation_routes.csv)'
    : '예시(가정 시뮬레이션): 엘리베이터가 경사 20% 구간 150m(고도 30m)를 대체, 대기·탑승 1.5분 / 잔여 300m는 평균 경사 8% / 팀 자체 산출');
  s.addNotes(iv ? '선정지에 시설을 설치했을 때 그 시설의 수혜 주거 건물 평균이 어떻게 바뀌는지(분석 코드 v5 개입 시뮬레이션). 실측 구간은 모델이 현장 시간을 잘 맞히는지 보여 주는 근거입니다.'
    : '제안의 효능감을 한 사람의 변화로 보여주는 장표. 14분이 10분이 되는 것, 그리고 쉬지 않고 집에 갈 수 있다는 것. (v5 개입 결과와 실측 구간이 들어오면 자동으로 실제 값으로 바뀝니다)');
}

B.IMPACT();
B.PLAN();
// 18 CLOSING
{
  const s = pres.addSlide(); page++;
  s.background = { color: C.dark };
  s.addImage({ path: img('contour_dark.png'), x:0, y:0, w:10, h:5.625 });
  T(s, '어디에 살든,', { x:0.6, y:1.35, w:8.8, h:0.7, fontSize:30, color:C.white });
  T(s, '7분은 7분이어야 합니다.', { x:0.6, y:2.05, w:8.8, h:0.8, fontSize:38, bold:true, color:C.orange });
  // evenly 워드마크 (소문자) — 23장의 서비스명 소개와 수미상관
  T(s, [ { text:'even', options:{ color:C.white } }, { text:'ly', options:{ color:C.sage } } ], { x:0.6, y:3.0, w:3, h:0.7, fontSize:34, bold:true, valign:'middle', charSpacing:1 });
  s.addShape(pres.shapes.LINE, { x:0.63, y:3.72, w:1.28, h:0, line:{ color:C.orange, width:2 } });
  T(s, '이븐리 · 평평하고 공평한 길', { x:0.6, y:3.82, w:6, h:0.3, fontSize:11, color:'B9CFC0' });
  T(s, '언덕 위 우리동네 · 경사 반영 이동약자 접근성 지도', { x:0.6, y:4.3, w:8.8, h:0.3, fontSize:12, color:C.white });
  T(s, `팀명 ${V('team_name', '○○○')}  |  한국국토정보공사 데이터 활용`, { x:0.6, y:4.75, w:6, h:0.3, fontSize:11, color:'B9CFC0' });
  wm(s);
  s.addNotes('마무리. 첫 장의 7분으로 돌아와 메시지를 닫고, 서비스명 evenly(even = 평평한 + 공평한)로 맺습니다.');
}


B.AP1();
B.AP2();
B.AP3();
B.AP4();

// ── 저장 + 누락 목록 ────────────────────────────────────────
if (pending.length) { console.error('!! 빈칸으로 그려지지 않은 누락 key: ' + pending.map(p => p.page + '장 ' + p.key).join(', ')); process.exitCode = 1; }
if (page > 30) { console.error(`!! 슬라이드 ${page}장 — 30장 제한 초과`); process.exit(1); }
const OUT = R.source === 'real' ? '../deliverables/언덕위우리동네_기획서_final.pptx'
          : R.source === 'fake' ? '../deliverables/_test_기획서.pptx'
          : '../deliverables/_blank_기획서.pptx';
const lines = [`# 기획서 누락 목록 — source=${R.source}${R.src ? ', src=' + R.src : ''}, ${new Date().toISOString().slice(0, 19)}`,
  `# 출력: ${OUT.replace('../', '')} (${page}장)`,
  ...missing.map(m => `누락: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}  [${m.key}]`), ...notes];
fs.mkdirSync('data', { recursive:true });
fs.writeFileSync(path.join('data', 'missing.txt'), lines.join('\n') + '\n');
if (R.source === 'none') console.warn('!! data/results.json 없음 → 빈칸 버전으로 생성합니다 (npm run build:fake 또는 build:real 을 쓰세요)');
if (FAKE) console.warn('!! 가짜(테스트) 데이터 — 모든 장에 "테스트 데이터 — 제출 금지" 워터마크');
console.log(`슬라이드 ${page}장, 누락 ${missing.length}건 → deck/data/missing.txt`);
missing.forEach(m => console.log(`  누락: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}`));
notes.forEach(n => console.log('  ' + n));
pres.writeFile({ fileName: OUT }).then(f => console.log('wrote', f));
