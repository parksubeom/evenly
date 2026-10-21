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
// [10/13→10/20] 대비책 판: 반출(10/19) 없이 = 1차 반출(10/2) + 10/20 현장 메모 + 공개 자료 계산 (tools/prepare_fallback_deck.py). 제출 후보라 검토 표시 없음.
//   반출이 있어야 채워지는 칸은 장마다 FALLBACK 갈래에서 빼고 배치를 맞춤. FB_TEXT 는 빠뜨린 칸을 잡는 표지라 장에 한 번이라도 나오면 빌드 실패 (FBHIT).
//   팀명·방문일이 비면 그대로 누락
const FALLBACK = R.source === 'fallback';
// [10/21 C안] build_final_c.js: A·B안 장점 합침 (B안 틀: 남색 상단 띠·진행 표시, 간지 없음, 2장 목차 겸 한 장 요약). 같은 결과 키·검사. 실제판(real)으로만
if (R.source !== 'real') { console.error('!! C안(build_final_c.js)은 실제판(real) 결과로만 만듭니다'); process.exit(1); }
const FB_TEXT = '2차 분석 결과 반영 예정', FBHIT = new Set();
// [10/21] 모든 판에 쓰지 않는 말 (장 글자·표·노트). 한 곳이라도 나오면 파일을 쓰지 않고 멈춤 (BANHIT)
const BANNED = ['본선', '85곳', '100곳', '실측', '반영 예정'], BANHIT = [];   // [10/21 B안] 실측은 하지 않았으므로 B안에 쓰지 않음   // [10/21] 85곳·100곳 = 7장 예전 계획 표현
const banScan = t => { const f = flat(t); if (/가상(?! 인물)/.test(f)) BANHIT.push(`${page}장 "가상" (가상 인물만)`); for (const w of BANNED) if (f.includes(w)) BANHIT.push(`${page}장 "${w}"`); };
// [10/13] 청사진 판 (npm run build:blueprint): 공개 대역 리허설 결과로 만드는 보관·발전용 (제출용 build:real 과 섞이지 않게 리허설 결과로만, --out 필수).
//   오른쪽 위 표시·출처 줄의 '공개 대역' 문구·표지 안내를 빼고(v9 청사진처럼), 결과 장 발표자 노트에 BP_NOTE. 값이 없는 칸(실측·SKT 등)은 리허설 판 표기 그대로
const BP = argv.includes('--blueprint');
if (BP && R.source !== 'rehearsal') { console.error("!! --blueprint 는 공개 대역 리허설 결과(source = rehearsal)로만 만듭니다 → 제출용은 build:real"); process.exit(1); }
if (BP && !arg('--out')) { console.error('!! --blueprint 는 --out 으로 출력 파일을 정해야 합니다 (deliverables 의 제출 파일 이름과 섞이지 않게)'); process.exit(1); }
const BP_NOTE = '[청사진 메모] 공개 자료 리허설 값. 실제 결과로 교체할 것';
// 결과 장 = 결과 키를 읽은 장 (값이 있든 없든). 범위·문턱·속도·팀명·방문일 같은 틀 값은 세지 않음
const BP_FRAME = new Set(['V6.scope', 'V6.hb', 'V6.rmin', 'V6.speed', 'V6.bands', 'team_name', 'team_display', 'V6.13.n_visits', 'V6.16.speed_src']);
const TOUCH = new Set(), SLIDES = {};
const touch = key => { if (!BP_FRAME.has(key)) { TOUCH.add(page); if (process.env.BP_DEBUG) console.error('touch', page, key); } };
const INPUT_KEYS = new Set(['team_name', 'team_display', 'V6.13.n_visits', 'V6.16.speed_src']);   // [10/14 v14] 방문일 = visits 의 일수   // [v6.3] 어르신 속도 출처도 입력 칸
// [10/13] 실제 판 --later-ok (22일 판정용, docs/22일_기획서_절차.md): 자료가 원래 없을 수 있는 칸(관악 실측·상호제공)만
//   ___ 대신 결과 키의 later 문구 ("실측 후"·"자료 확보 시", missing 에 '대체'). 그 밖의 누락은 그대로 ___
const LATER_OK = R.source === 'real' && argv.includes('--later-ok');
const LATER_OK_RE = /^V6\.15\.\d\.(app|meas|model|slow)$|^V6\.15\.date$|^V6\.16\.meas_r$|^V6\.21\.(skt|kcb)$|^V6\.22\.acc$/;
const BANDS = R.bands || 'mix', MINB = BANDS === 'min';
const HB = () => Q('V6.hb', '1.3'), RMIN = () => Q('V6.rmin', '10');   // 체감 부담 HBI 문턱, 고립 위험 왕복 추가 분 (결과의 run_meta = mapping 한 곳)
const SPD = () => Number(Q('V6.speed', '0.7'));   // [10/13 판정] 어르신 평지 보행속도 m/s (결과의 run_meta elder_speed, 대비책 판 = 1차 v5 의 0.8)
// [10/14 v15] 3·12장 예시 길(450m·평균 경사 12%)의 배수를 분석 모델 식으로 (analysis/hbi/lib/model.py tobler·elder_time, 속도와 무관)
//   편도 오르막 = tobler(0) ÷ tobler(0.12) = exp(3.5 × 0.12) ≈ 1.52 (예전 14.3/9.4 와 같음), 내리막 = 1 + 0.5 × (오르막 − 1) (config DOWNHILL_WEIGHT = 0.5, 부록 3),
//   왕복 = (오르막 + 내리막) ÷ 2 (HBI 정의가 왕복). 그림(profile.png)의 S자 곡선을 그대로 넣으면 편도 1.56·왕복 1.42 (가운데가 더 가팔라서)
const TOB = sl => 6 * Math.exp(-3.5 * Math.abs(sl + 0.05)), EX_GRADE = 0.12, DOWN_W = 0.5;
const PF = TOB(0) / TOB(EX_GRADE), PF_DOWN = 1 + DOWN_W * (PF - 1), PF_RT = (PF + PF_DOWN) / 2;
const EX = () => { const a = 450 / 1.1 / 60, f = 450 / SPD() / 60; return { adult:a, flat:f, slope:f * PF, down:f * PF_DOWN, rt:f * (PF + PF_DOWN) }; };   // 예시 분: 성인 1.1m/s, 어르신 SPD

const pres = new pptxgen(); pres.layout = 'LAYOUT_16x9';
pres.title = (FAKE ? '[가상 수치 · 검토용] ' : BP ? '[청사진] ' : REH ? '[공개 대역 · 제출 금지] ' : '') + '언덕 위 우리동네: 경사 반영 이동편의시설 입지 지도';   // [10/20]
const F = 'Malgun Gothic';
const C = { ink:'14284B', text:'26303D', muted:'5E6B80', line:'D5DDEA', soft:'EEF3FA', acc:'E8711A', accD:'B4520C', teal:'2F6FD6', white:'FFFFFF',
  r1:'8CB8A0', r2:'F2B134', r3:'E4572E', r4:'9E2A2B', onDark:'C5D3EA', reh:'1F5FA8' };   // [10/21 B안] 남색·파랑 + 강조색 하나 (주황)
const NAVY = '14284B', TINT = 'E8F0FC', DIM = '8FA3C7';
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
  touch(key);
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
const has = key => { touch(key); const f = R.fields[key]; return !!(f && f.value !== null && f.value !== undefined && f.value !== ''); };
const hasR = key => { const f = R.fields[key]; return !!(f && f.value !== null && f.value !== undefined && f.value !== ''); };   // [10/14 v14] 청사진 메모를 남기지 않는 확인 (출처 줄·부록 조건용)
// [10/20] 실제판 (10/19 반출 all 방식 + 10/20 현장 메모 + 공개 자료 계산): 모든 건물 기준 표기, 목적지 약국, 출처 줄 표기
const ALLM = () => hasR('V6.allmode');
const BLDL = () => ALLM() ? '건물(모든 건물 기준)' : '주거 건물';   // 장마다 처음
const BLDS = () => ALLM() ? '건물' : '주거 건물';                   // 표 머리·되풀이
const DEST = () => ALLM() ? '약국' : '병원·약국';
const MIX17 = () => !!(R.tables['V6.17.cand'] && (R.tables['V6.17.cand'].rows || []).some(r => r.src));   // [10/20] 17장 = 부담 LX 격자 + 시설 효과 공개 보행망
// [10/21] 2·17장 LX 결과 중심: 반출 격자로 본 후보 고립 위험 상위 두 곳이 같은 동이고, 나머지 후보가 그 10% 미만일 때만 {dong, n:[두 수], names}
const LXTOP = (() => { const rows = (R.tables['V6.17.cand'] && R.tables['V6.17.cand'].rows) || [];
  if (!(REAL && rows.some(r => r.src) && hasR('V6.17.lx_ranks'))) return null;
  const nr = r => Number(r.n_risk) || 0, cs = rows.filter(r => r.kind === '후보'), t2 = [...cs].sort((a, b) => nr(b) - nr(a)).slice(0, 2);
  const dg = t2.map(r => String(r.loc || '').split(' ').pop()), rest = cs.filter(r => !t2.includes(r));
  if (!(t2.length === 2 && dg[0] && dg[0] === dg[1] && rest.every(r => nr(r) < 0.1 * Math.min(...t2.map(nr))))) return null;
  return { dong: dg[0], n: t2.map(nr), names: t2.map(r => r.name), offSite: hasR('V6.14.top_name') && R.fields['V6.14.top_name'].value === dg[0] && hasR('V6.14.top_no_site') && R.fields['V6.14.top_no_site'].value === 'yes' }; })();
// [10/20] 11·28장 과정 그림 메타 (tools/make_process_figs.py). contour = 연속수치지형도 등고선으로 그렸는지 → 출처 줄
const PFM = (() => { try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'v6_source', 'proc_figs_meta.json'), 'utf8')); } catch (e) { return {}; } })();
const PFC = !!PFM.contour, PFB = !!PFM.contour_bg;   // PFB = 등고선은 배경·터널 단면에만 (경사는 공개 지형)
// [10/21] 서울균형발전포털 「서울 오르락」 공식 값 (deck/seoul_orak.json, 원문 그대로): 5장 통계·7장 단계·15장 봉천 계단·16장 서울시 고저차
const OR = (() => { try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'seoul_orak.json'), 'utf8')); }
                    catch (e) { console.error('!! deck/seoul_orak.json 을 읽지 못함 (서울 오르락 공식 값)'); process.exit(1); } })();
const LXS = 'LX 분석', PUBS = '공개 자료 보행망으로 계산 (같은 모델·같은 좌표)', ANAS = '해석적 계산';
const Q = (key, dflt) => { touch(key); if (has(key)) return String(R.fields[key].value); fb(key, dflt); return dflt; };   // 기본 문구로 말이 되는 보조 값
function IMG(key) {
  touch(key);
  const m = R.images[key];
  if (m && m.path && fs.existsSync(m.path)) return m.path;
  if (REH && m && m.later) { fb('img:' + key, m.later); return null; }
  if (FALLBACK) { fb('img:' + key, FB_TEXT); return null; }
  miss('img:' + key, m || { label:key, need:[] }); pending.push({ key:'img:' + key, page });
  return null;
}
function TBL(key) {
  touch(key);
  const t = R.tables[key];
  if (t && t.rows && t.rows.length) return t.rows;
  if (FALLBACK) { fb('tbl:' + key, FB_TEXT); return null; }
  miss('tbl:' + key, t || { label:key, need:[] });
  return null;
}
const isLater = t => LATER.has(String(t));

const T = (s, text, o = {}) => {
  if (FALLBACK && flat(text).includes(FB_TEXT)) FBHIT.add(page);   // [10/20] 대비책 판에 남은 표지
  banScan(text);
  const tag = ('_keys' in o) ? o._keys : (runs(text) ? take(runs(text)) : undefined);
  const opt = Object.assign({ fontFace:F, color:C.text, isTextBox:true, margin:0, valign:'top' }, o);
  delete opt._keys; if (tag) opt.objectName = tag;
  return s.addText(text, opt);
};
const hr = (s, x, y, w, color, pt) => s.addShape(pres.shapes.LINE, { x, y, w, h:0, line:{ color:color||C.line, width:pt||0.75 } });
const vr = (s, x, y, h, color, pt) => s.addShape(pres.shapes.LINE, { x, y, w:0, h, line:{ color:color||C.line, width:pt||0.75 } });
const bar = (s, x, y, h, color) => s.addShape(pres.shapes.RECTANGLE, { x, y, w:0.06, h, fill:{color:color||C.teal}, line:{color:color||C.teal} });   // [B안] 기본 파랑
const box = (s, x, y, w, h, fill, line) => s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill:{color:fill||C.white}, line:{color:line||fill||C.white, width:0.75} });
function tag(s, x, y, text, w, color) {
  color = color || C.acc;
  s.addShape(pres.shapes.RECTANGLE, { x, y, w, h:0.27, fill:{color:C.white}, line:{color, width:1} });
  T(s, text, { x, y, w, h:0.27, fontSize:10, bold:true, color, align:'center', valign:'middle' });
}
function reviewTag(s, dark) {
  if ((!FAKE && !REH) || BP) return;   // [10/13] 청사진 판은 표시 없음
  const col = 'C0392B', txt = FAKE ? '가상 수치 · 검토용' : '공개 대역 · 제출 금지';   // [10/12 판정] 두 표시 모두 빨강 테두리 (청사진)
  s.addShape(pres.shapes.RECTANGLE, { x:7.90, y:0.16, w:1.60, h:0.25, fill:{color: dark ? C.ink : C.white}, line:{color:col, width:1} });
  T(s, txt, { x:7.90, y:0.16, w:1.60, h:0.25, fontSize:9, bold:true, color:col, align:'center', valign:'middle' });
}
const tsize = t => t.length > 34 ? 19 : t.length > 27 ? 21 : 24;
const SCOPE = REH ? (BP ? Q('V6.scope', '관악구') : `${Q('V6.scope', '관악구')}(공개 대역)`) : FALLBACK ? '관악 일대(1차 반출)' : '5개 구';      // 14·17 장의 범위 표현 (공개 대역·대비책 판에서만 바뀜)
const TG20 = () => Q('V6.20.tgt', '지하철역').replace(/\(.*\)/, '').replace('지하철역', '역').trim();   // [10/14 v11] 2·17·20장 봉천 숫자의 기준
const SFX = () => ((REH && !BP) || FALLBACK) ? ' · ' + SCOPE : '';   // 머리말 꼬리 (청사진 판은 v9 처럼 없음)
// title 에 결과 값(V)이 들어가면 함수로 넘김: 장 번호를 올린 뒤에 값을 읽어야 누락이 이 장에 적힘
// [10/21 B안] 장 묶음(SEC)·진행 표시·상단 띠. 띠 = "0N. 장 이름 · 쪽 이름", 오른쪽 위 01~04 (지금 장 강조)
let SEC = { n:0, name:'' };
const setSec = (n, name) => { SEC = { n, name }; };
const PNAME = {};   // 쪽 번호 → 띠의 쪽 이름 (없으면 base 의 kicker)
function prog(s, n) {
  ['01', '02', '03', '04'].forEach((t, i) => { const on = n === i + 1, x = 7.66 + i * 0.54;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:0.075, w:0.46, h:0.19, rectRadius:0.09, fill:{ color: on ? 'FFFFFF' : NAVY }, line:{ color: on ? 'FFFFFF' : '4A5F8A', width:0.75 } });
    T(s, t, { x, y:0.075, w:0.46, h:0.19, fontSize:7.5, bold:on, color: on ? NAVY : DIM, align:'center', valign:'middle' }); });
}
function base(kicker, title, o={}) {
  const s = pres.addSlide(); page++;
  if (typeof title === 'function') title = title();
  s.background = { color: C.white };
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:10, h:0.34, fill:{ color:NAVY }, line:{ color:NAVY } });
  const pn = PNAME[page] || kicker;
  T(s, (SEC.n ? `${String(SEC.n).padStart(2, '0')}. ${SEC.name}` : SEC.name) + (pn ? `  ·  ${pn}` : ''), { x:0.35, y:0.04, w:7.0, h:0.26, fontSize:9.5, bold:true, color:'FFFFFF', valign:'middle' });
  prog(s, SEC.n);
  T(s, title, { x:0.6, y:0.48, w:8.8, h:0.74, fontSize:o.tsize||tsize(flat(title)), bold:true, color:NAVY, valign:'middle' });
  s.addShape(pres.shapes.RECTANGLE, { x:0.6, y:1.24, w:0.5, h:0.035, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, String(page), { x:9.0, y:5.25, w:0.45, h:0.22, fontSize:9, color:C.muted, align:'right' });
  SLIDES[page] = s;
  return s;
}
// 단순한 아이콘 (사진 대신): 파란 원 안에 흰 도형
function icon(s, kind, x, y, d = 0.5, bg = C.teal) {
  s.addShape(pres.shapes.OVAL, { x, y, w:d, h:d, fill:{ color:bg }, line:{ color:bg } });
  const W = 'FFFFFF', u = d / 10, cx = x + d / 2, cy = y + d / 2, sh = pres.shapes;
  const P = (t, x0, y0, w, h, c = W) => s.addShape(t, { x:x0, y:y0, w, h, fill:{ color:c }, line:{ color:c } });
  if (kind === 'house') { P(sh.ISOSCELES_TRIANGLE, cx - 3.2*u, cy - 3.2*u, 6.4*u, 2.8*u); P(sh.RECTANGLE, cx - 2.3*u, cy - 0.5*u, 4.6*u, 3.2*u); P(sh.RECTANGLE, cx - 0.6*u, cy + 0.9*u, 1.2*u, 1.8*u, bg); }
  else if (kind === 'bus') { P(sh.ROUNDED_RECTANGLE, cx - 3*u, cy - 2.8*u, 6*u, 4.6*u); P(sh.RECTANGLE, cx - 2.3*u, cy - 2.1*u, 4.6*u, 1.7*u, bg); P(sh.OVAL, cx - 2.4*u, cy + 1.3*u, 1.5*u, 1.5*u, bg); P(sh.OVAL, cx + 0.9*u, cy + 1.3*u, 1.5*u, 1.5*u, bg); }
  else if (kind === 'stairs') { P(sh.RECTANGLE, cx - 3*u, cy + 1*u, 6*u, 1.6*u); P(sh.RECTANGLE, cx - 1*u, cy - 0.6*u, 4*u, 1.6*u); P(sh.RECTANGLE, cx + 1*u, cy - 2.2*u, 2*u, 1.6*u); }
  else if (kind === 'chart') { P(sh.RECTANGLE, cx - 2.8*u, cy + 0.2*u, 1.4*u, 2.4*u); P(sh.RECTANGLE, cx - 0.7*u, cy - 1.2*u, 1.4*u, 3.8*u); P(sh.RECTANGLE, cx + 1.4*u, cy - 2.6*u, 1.4*u, 5.2*u); }
  else if (kind === 'grid') { [0, 1, 2].forEach(i => [0, 1, 2].forEach(j => P(sh.RECTANGLE, cx - 2.9*u + i*2*u, cy - 2.9*u + j*2*u, 1.6*u, 1.6*u))); }
  else if (kind === 'people') { P(sh.OVAL, cx - 1.3*u, cy - 3*u, 2.6*u, 2.6*u); P(sh.ROUNDED_RECTANGLE, cx - 2.6*u, cy - 0.1*u, 5.2*u, 3*u); }
}
// 장 간지 (면 색): 큰 장 번호 + 장 이름 + 쪽 목록
function divider(n, name, items) {
  setSec(n, name);
  const s = pres.addSlide(); page++; s.background = { color:NAVY };
  s.addImage({ path:img('contour_dark.png'), x:0, y:0, w:10, h:5.625, transparency:78 });
  prog(s, n);
  T(s, String(n).padStart(2, '0'), { x:0.8, y:1.05, w:3, h:1.2, fontSize:72, bold:true, color:C.acc });
  T(s, name, { x:0.8, y:2.25, w:8.4, h:0.8, fontSize:36, bold:true, color:'FFFFFF' });
  s.addShape(pres.shapes.RECTANGLE, { x:0.8, y:3.15, w:1.0, h:0.05, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, items.map(([p, t]) => `${p}  ${t}`).join('\n'), { x:0.8, y:3.35, w:8.4, h:1.7, fontSize:13, color:C.onDark, lineSpacingMultiple:1.3 });
  T(s, String(page), { x:9.0, y:5.25, w:0.45, h:0.22, fontSize:9, color:DIM, align:'right' });
  SLIDES[page] = s;
}
const src = (s, t) => T(s, BP ? String(t).replace(/공개 대역\(리허설\) 값 · /g, '') : t, { x:0.6, y:5.22, w:8.2, h:0.28, fontSize:8.5, color:C.muted });   // [10/13] 청사진 판: 출처 줄의 '공개 대역' 문구 뺌
function takeaway(s, text, y) { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.6, y, w:8.8, h:0.42, rectRadius:0.2, fill:{ color:TINT }, line:{ color:TINT } }); T(s, text, { x:0.85, y, w:8.4, h:0.42, fontSize:13, bold:true, color:NAVY, valign:'middle' }); }   // [B안] 둥근 띠 한 줄
function stat(s, x, y, w, label, value, o={}) {
  T(s, label, { x, y, w, h:0.26, fontSize:11, color:C.muted });
  const v = String(value), later = isLater(v);
  // [10/12 청사진] 대체 문구도 값과 같은 크기·굵기 (색은 회색, laterInk 면 검정)
  T(s, o.suffix ? [{ text:v, options:{} }, { text:o.suffix, options:{ fontSize:o.suffixSize || 11, bold:false, color:C.muted } }] : v,   // [10/21] 값 뒤 작은 글자 (16장 서울시 공식)
    { x, y:y+0.26, w, h:0.46, fontSize:(o.size||20), bold:true, color: later ? (o.laterInk ? C.ink : C.muted) : (o.color||(v.includes('___') ? C.accD : C.ink)), valign:'top' });
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
  if (FALLBACK && rows.some(r => r.some(c => flat(c && c.text !== undefined ? c.text : c).includes(FB_TEXT)))) FBHIT.add(page);   // [10/20]
  rows.forEach(r => r.forEach(c => banScan(c && c.text !== undefined ? c.text : c)));   // [10/21]
  const n = explicit ? 0 : rows.reduce((a, r) => a + r.reduce((b2, c) => b2 + runs(c && c.text !== undefined ? c.text : c), 0), 0);
  const t = (explicit || n) ? take(n, explicit ? [explicit] : []) : undefined;
  s.addTable(body, Object.assign({}, opt, t ? { objectName:t } : {}));
}
const B = (t, o={}) => ({ text:t, options:Object.assign({ bold:true }, o) });
const team = () => has('team_display') ? String(R.fields['team_display'].value) : V('team_name', '○○○');   // [10/12 판정] 1·26장은 표시 이름 (inputs.json team_display, 없으면 team_name)

PNAME[3] = '같은 길, 다른 시간'; PNAME[4] = '김순자 할머니'; PNAME[5] = '문제의 규모'; PNAME[6] = '현장 사례'; PNAME[7] = '서울시 사업';
PNAME[11] = '분석 과정'; PNAME[12] = '언덕 부담 지수'; PNAME[13] = '안심구역 분석';
PNAME[14] = '숨은 부담'; PNAME[15] = '네 자료 대조'; PNAME[16] = '검증·LX 필요성'; PNAME[17] = '우선 검토 후보'; PNAME[18] = '시설 효과 과정'; PNAME[19] = '시설 하나의 효과';
PNAME[20] = '행정 결정 다섯 가지'; PNAME[21] = '방문돌봄'; PNAME[22] = '정류장·사고다발지'; PNAME[23] = '도시계획 연계'; PNAME[24] = '담당자 화면'; PNAME[25] = '도입 단계';
PNAME[27] = '부록 1 · 전처리와 경사 모델'; PNAME[28] = '부록 2 · 가정과 민감도'; PNAME[29] = '부록 3 · 코드 발췌';
// ── B1 표지 ──
{ const s = pres.addSlide(); page++; s.background = { color:NAVY };
  s.addImage({ path:img('contour_dark.png'), x:0, y:0, w:10, h:5.625, transparency:62 });
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:0.22, h:5.625, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, '2026 데이터+AI 혁신 챌린지 · 데이터안심구역 경진대회 (한국국토정보공사)', { x:0.8, y:0.7, w:8.6, h:0.3, fontSize:12, color:C.onDark });
  T(s, '언덕 위 우리동네', { x:0.8, y:1.4, w:8.6, h:0.95, fontSize:46, bold:true, color:'FFFFFF' });
  T(s, '경사 반영 이동편의시설 입지 지도', { x:0.8, y:2.35, w:8.6, h:0.5, fontSize:22, color:C.onDark });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.8, y:3.2, w:6.4, h:0.5, rectRadius:0.2, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, `지도앱의 ${Math.round(EX().adult)}분이, 누군가에게는 ${Math.round(EX().slope)}분입니다.`, { x:1.05, y:3.2, w:6.1, h:0.5, fontSize:17, bold:true, color:'FFFFFF', valign:'middle' });
  T(s, `정책 도구 evenly   |   팀명 ${team()}   |   2026.10`, { x:0.8, y:4.8, w:7, h:0.3, fontSize:12, color:C.onDark });
  SLIDES[page] = s; }
// ── C2 목차 겸 한 장 요약 ──
setSec(0, '목차');
{ const s = base('한 장 요약', '높이까지 넣어 계산하면, 다음 시설을 어디에 놓을지 보입니다', { tsize:20 });
  [[1, '기획 배경', '3~8'], [2, '데이터와 방법', '9~13'], [3, '분석 결과', '14~19'], [4, '활용과 도입', '20~26']].forEach(([n, nm, pg], i) => { const y = 1.5 + i * 0.66;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:0.6, y, w:3.3, h:0.56, rectRadius:0.08, fill:{ color:C.soft }, line:{ color:C.soft } });
    T(s, String(n).padStart(2, '0'), { x:0.72, y, w:0.6, h:0.56, fontSize:20, bold:true, color:C.teal, valign:'middle' });
    T(s, nm, { x:1.3, y, w:1.8, h:0.56, fontSize:13, bold:true, color:C.ink, valign:'middle' });
    T(s, `${pg}쪽`, { x:3.05, y, w:0.75, h:0.56, fontSize:10, color:C.muted, align:'right', valign:'middle' }); });
  T(s, '부록 27~29쪽 · 질의응답 30쪽', { x:0.6, y:4.16, w:3.3, h:0.26, fontSize:10, color:C.muted });
  vr(s, 4.2, 1.5, 2.94);
  T(s, '찾은 것 세 가지', { x:4.5, y:1.45, w:4.9, h:0.3, fontSize:12.5, bold:true, color:C.ink });
  [[V('V6.14.risk_n'), `왕복 ${RMIN()}분 넘게 잃는 ${BLDS()} (${Q('V6.scope', '관악구')}, 고립 위험)`, C.acc],
   [LXTOP ? `${LXTOP.n.map(v => v.toLocaleString('en-US')).join('·')}개` : V('V6.17.n_facility'), LXTOP ? `고립 위험 건물이 몰린 ${LXTOP.dong} 두 곳` + (LXTOP.offSite ? ', 2025 선정지 밖' : '') : '같은 예산으로 더 많은 집을 돕는 곳', C.ink],
   [`${V('V6.20.before')} → ${V('V6.20.after')}`, `봉천 엘리베이터 하나로 휠체어 길이 줄고, ${Q('V6.20.tgt', '약국')} 가는 건물 ${V('V6.20.any')}가 혜택`, C.ink]].forEach(([v, t, c], i) => { const y = 1.85 + i * 0.86;
    if (i) hr(s, 4.5, y - 0.06, 4.9);
    T(s, v, { x:4.5, y, w:2.3, h:0.7, fontSize: flat(v).length > 8 ? 22 : 28, bold:true, color:c, valign:'middle' });
    T(s, t, { x:6.85, y, w:2.55, h:0.7, fontSize:11, color:C.text, valign:'middle', lineSpacingMultiple:1.08 }); });
  takeaway(s, '이동편의시설을 어디에 놓을지가 핵심이고, 같은 지도로 예산 순위·방문돌봄·정류장·보행 정비까지 정합니다.', 4.62);
  src(s, `${LXS} (10/19 반출, 모든 건물 기준) · ${Q('V6.scope', '관악구')} 분석 기준 · 행정 도입 단계는 25장`); }
setSec(1, '기획 배경');
// ── 3 같은 길, 다른 시간 ──
{ const s = base('한 사람의 귀갓길', '같은 450m, 다른 시간'); tag(s, 4.85, 0.82, '예시 계산', 1.0);
  s.addImage({ path:img('profile.png'), x:0.5, y:1.4, w:5.7, h:2.76 });
  const ex3 = EX();   // [10/13] 예시 분을 어르신 속도에서 계산
  [[`${Math.round(ex3.adult)}분`,'지도앱 도보 안내','평지, 성인 걸음 기준',C.muted],[`${Math.round(ex3.flat)}분`,'어르신 걸음으로','아직 언덕은 빼고',C.ink],[`${Math.round(ex3.slope)}분`,'오르막까지 넣으면',`지도앱이 말한 시간의 ${(ex3.slope / ex3.adult).toFixed(1)}배`,C.acc]].forEach((r, i) => {
    const y = 1.45 + i*0.93; if (i) hr(s, 6.5, y-0.06, 2.9);
    T(s, r[0], { x:6.5, y, w:1.25, h:0.7, fontSize:i==2?32:28, bold:true, color:r[3], valign:'middle' });
    T(s, r[1], { x:7.8, y:y+0.08, w:1.7, h:0.3, fontSize:12.5, bold:true, color:C.ink });
    T(s, r[2], { x:7.8, y:y+0.38, w:1.7, h:0.28, fontSize:11, color:C.muted }); });
  takeaway(s, '집은 언덕 위, 약국은 언덕 아래. 돌아오는 길은 고도 54m를 올라야 합니다.', 4.5);
  const meas3 = [0, 1, 2, 3].some(i => hasR(`V6.15.${i}.meas`));   // [10/14 v14] 실측값이 들어오면 '교체 예정' 이 빠짐
  src(s, `그림은 개념도 · ${ANAS}: 성인 1.1m/s, 고령자 ${SPD()}m/s, 평균 경사 12%, Tobler 보행함수` + (meas3 ? ' · 실측 비교는 15장' : '')); }   // [10/20] '교체 예정' 삭제   // [10/14] 숫자는 평균 경사 12% 고르게 (그림의 S자 곡선이 아님)

// ── 4 페르소나 ── [10/13 v9 청사진] 한 사람의 한 달: 지도앱 왕복(3장 예시 길) + 가장 급한 동 고립 위험 격자의 왕복 추가 중앙값 × 일주일 네 번
{ let dong4, add4, map4, flat4, up4, mon4;   // 값은 장을 만든 뒤에 읽음 (빈칸·노트가 이 장에 적히게)
  // [10/14 v14→v15] 할머니 길 = 동 언덕 위 집에서 450m (3장 예시 길과 다른 길, 거리·속도만 같음): 지도앱 왕복 = 450m 성인 × 2, 평지 왕복 = 450m 어르신 × 2,
  //   오르막 왕복 = 평지 왕복 + 동 고립 위험 격자 왕복 추가 중앙값(언덕 몫). 언덕 몫(반올림)이 3장 숫자와 같으면 빌드 경고 (뜻이 다름)
  const s = base('한 사람의 한 달', () => {
    dong4 = has('V6.4.dong') ? R.fields['V6.4.dong'].value : '언덕 위 동네';
    add4 = has('V6.4.add') ? Number(R.fields['V6.4.add'].value) : (FALLBACK ? EX().rt - EX().flat * 2 : null);   // [10/20] 대비책 판: 3장 예시 길로 해석적 계산
    map4 = Math.round(EX().adult * 2); flat4 = Math.round(EX().flat * 2); up4 = add4 !== null ? Math.round(EX().flat * 2 + add4) : null; mon4 = add4 !== null ? add4 * 4 * 52 / 12 / 60 : null;
    return mon4 !== null ? `김순자 할머니의 한 달은 ${Math.floor(mon4)}시간 더 깁니다` : '김순자 할머니의 한 달은 더 깁니다'; }); tag(s, 6.6, 0.82, '가상 인물', 1.0);
  T(s, [
    { text:`${has('V6.4.dong') ? dong4 + ' ' : ''}언덕 위에 사는 김순자 할머니(78)는 약국과 시장, 동네 의원에 일주일에 네 번 다닙니다.`, options:{ breakLine:true } },
    { text:' ', options:{ breakLine:true, fontSize:6 } },
    { text: add4 !== null ? `지도앱은 왕복 ${map4}분이라고 하지만, 할머니 걸음으로 평지라면 ${flat4}분, 오르막까지 넣으면 ${up4}분이 걸립니다. 언덕 때문에 한 번에 ${Math.round(add4)}분, 한 달이면 ${Math.floor(mon4)}시간 넘게 더 씁니다.`
                          : `지도앱은 왕복 ${map4}분이라고 하지만, 할머니 걸음으로 평지라면 ${flat4}분, 오르막까지 넣으면 더 걸립니다. 언덕 때문에 잃는 시간은 ${V('V6.4.add')}`, options:{ breakLine:true } },
    { text:' ', options:{ breakLine:true, fontSize:6 } },
    { text:'그래서 할머니는 볼일을 모아 한 번에 나가고, 비가 오거나 더운 날은 거릅니다.', options:{} },
  ], { x:0.6, y:1.5, w:4.9, h:2.6, fontSize:13.5, color:C.text, lineSpacingMultiple:1.2 });
  [[`왕복 ${map4}분`,'지도앱',C.muted],[up4 !== null ? `왕복 ${up4}분` : (FALLBACK ? FB_TEXT : '-'),'할머니 걸음 + 오르막',C.ink],[mon4 !== null ? `한 달 +${Math.floor(mon4)}시간` : (FALLBACK ? FB_TEXT : '-'),'언덕 몫 (일주일 네 번 외출)',C.acc]].forEach((r, i) => {
    const y = 1.5 + i*0.88; if (i) hr(s, 5.95, y-0.08, 3.45);
    T(s, r[0], { x:5.95, y, w:3.45, h:0.5, fontSize:24, bold:true, color:r[2] });
    T(s, r[1], { x:5.95, y:y+0.48, w:3.45, h:0.28, fontSize:11, color:C.muted }); });
  takeaway(s, FALLBACK ? `같은 450m라도 오르막이 있으면 할머니에게는 한 번에 ${Math.round(add4)}분이 더 붙습니다.` : `이렇게 매번 ${RMIN()}분 넘게 잃는 ${BLDS()}이 ${Q('V6.scope', '관악구')}에만 ${V('V6.14.risk_n')} 있습니다.`, 4.4);
  if (add4 !== null && !FALLBACK) { const e3 = EX(), n3 = [e3.adult, e3.flat, e3.slope].map(Math.round);
    if (n3.includes(Math.round(add4))) console.error(`!! 4장 언덕 몫 ${Math.round(add4)}분이 3장 숫자(${n3.join('·')}분) 중 하나와 같음 — 뜻이 다르니 장별 확인 때 읽히는지 볼 것`); }
  src(s, FALLBACK ? `${ANAS}: 3장과 같은 450m·평균 경사 12% 예시 길 (성인 1.1m/s·어르신 ${SPD()}m/s), 언덕 몫 = 오르막 왕복 − 평지 왕복 · 일주일 네 번 외출은 가정 · 가상 인물`
    : (REH ? '공개 대역(리허설) 값 · ' : '') + `${LXS}${ALLM() ? ' (모든 건물 기준)' : ''} · ${dong4} 언덕 위 집에서 450m 거리 기준 (성인 1.1m/s·어르신 ${SPD()}m/s), 언덕 몫은 ${dong4} 고립 위험 격자의 왕복 추가 중앙값 · 일주일 네 번 외출은 가정 · 가상 인물`); }   // [10/14 v15]

// ── 5 규모 ──
{ const s = base('문제의 규모', '한 사람의 이야기가 아닙니다');
  // [10/21] 구릉지·이동약자는 서울 오르락 공식 값 (예전 31%·20.4% 자리, 65세 이상 20.4% 는 설명 줄에 나란히)
  [[OR.hill_share.value, `서울 ${OR.hill_share.def}`,'낡은 저층 주택이 많고 시설을 놓기 어려운 땅'],[OR.mobility_impaired.value, `서울 이동약자\n(${OR.mobility_impaired.year}, 인구의 ${OR.mobility_impaired.share})`,'65세 이상만 20.4%, 2025년 처음으로 20%를 넘었습니다'],['51곳','구릉지 고령자 이동취약지역','거주 고령인구 16,773명, 25개 구 중 17개 구'],['420m','후기고령자 평균 이동거리','75세 이상 어르신이 걷는 거리의 한계']].forEach((st, i) => {
    const x = 0.6 + (i%2)*4.5, y = 1.45 + Math.floor(i/2)*1.45;
    if (i%2) vr(s, x-0.25, y, 1.2); if (i>=2) hr(s, x, y-0.12, 4.2);
    T(s, st[0], { x, y, w:2.1, h:0.75, fontSize:st[0].length>5?30:36, bold:true, color: i<2 ? C.acc : C.ink, valign:'middle' });
    T(s, st[1], { x:x+2.15, y:y+0.08, w:2.0, h:0.62, fontSize:13, bold:true, color:C.ink, valign:'middle' });
    T(s, st[2], { x, y:y+0.8, w:4.1, h:0.32, fontSize:11.5, color:C.muted }); });
  takeaway(s, `서울의 ${OR.hill_share.value}가 구릉지이고, 시민 10명 중 3명이 이동약자입니다.`, 4.5);   // [10/21] 29.1% ≈ 10명 중 3명
  src(s, `출처: ${OR.source_short} (구릉지 비율·이동약자 수) / 행정안전부 2025 주민등록 인구통계 (65세 이상) / 구릉지 고령자 이동취약지역 분석 연구(한국공간디자인학회 논문집) / 이소민·오성훈(2025) 토지주택연구 16(1)`); }

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

// ── 7 정책 흐름 ── [10/21] 서울 오르락(서울균형발전포털, 2026-08-28): 30곳·4단계·사업기간. 3·4단계는 대상지 발표 전.
//   1·2단계 예산(200억·400억)은 단계마다 발표한 출처 (18·28장 비용 가정과 같음)
{ const ph7 = OR.phases, n34 = ph7.filter(p => p.open).reduce((a, p) => a + p.count, 0);
  const s = base('정책 흐름', `서울시는 2030년까지 ${OR.total}곳에 엘리베이터를 놓습니다.\n${ph7.filter(p => p.open).map(p => p.n).join('·')}단계 ${n34}곳은 아직 정해지지 않았습니다.`, { tsize:19 });
  T(s, [{ text:'사업기간  ', options:{ bold:true, color:C.muted } }, { text:OR.period, options:{ bold:true, color:C.ink } }, { text:`   ·   ${OR.total_note}`, options:{ color:C.muted } }],
    { x:0.6, y:1.42, w:8.8, h:0.28, fontSize:11 });
  hr(s, 0.6, 2.0, 8.8, C.ink, 1.25);
  const note7 = { 1:'봉천 비안어린이공원 포함\n총 200억 원', 2:'봉천초 인근 포함\n총 400억 원' };
  ph7.forEach((p, i) => { const x = 0.6 + i * 2.25, open = p.open;
    s.addShape(pres.shapes.RECTANGLE, { x, y:1.93, w:0.14, h:0.14, fill:{ color: open ? C.acc : C.ink }, line:{ color: open ? C.acc : C.ink } });
    T(s, `${p.n}단계`, { x, y:2.2, w:2.1, h:0.3, fontSize:13, bold:true, color: open ? C.acc : C.ink });
    T(s, `${p.count}곳`, { x, y:2.5, w:2.1, h:0.6, fontSize:30, bold:true, color: open ? C.acc : C.ink, valign:'middle' });
    T(s, p.when, { x, y:3.14, w:2.1, h:0.28, fontSize:11.5, bold:true, color:C.text });
    T(s, open ? '대상지 아직 정해지지 않음' : (note7[p.n] || ''), { x, y:3.44, w:2.1, h:0.5, fontSize:10.5, color: open ? C.accD : C.muted, lineSpacingMultiple:1.1 }); });
  takeaway(s, `다음 ${n34}곳을 같은 기준으로 비교하고, 효과를 미리 계산할 도구가 필요합니다.`, 4.3);
  src(s, `${OR.source_short} · 1단계 200억 원: 서울시 보도자료(2025.06) · 2단계 400억 원: 쿠키뉴스(2026.02.12)`); }

// ── B7 차별성 O/X (A안 8·9장) ──
{ const s = base('차별성', '서울시는 가파른 "계단"을 찾았고, 우리는 가파른 "일상"을 찾습니다', { tsize:20 });
  T(s, [{ text:'지금의 발굴 기준 (2024 서울시 전수조사)   ', options:{ bold:true, color:C.muted } }, { text:'경사 20도·폭 2.5m·길이 30m 이상 계단 + 민원', options:{ bold:true, color:C.ink } }], { x:0.6, y:1.36, w:8.8, h:0.28, fontSize:11 });
  const O = { text:'O', options:{ bold:true, color:C.teal, align:'center' } }, X = { text:'X', options:{ color:'A9B4C6', align:'center' } }, N = { text:'-', options:{ color:'A9B4C6', align:'center' } };
  const E = { text:'O', options:{ bold:true, color:C.acc, align:'center' } }, H = t => ({ text:t, options:{ align:'center' } });
  etable(s, [['구분', H('서울시 전수조사\n(2024)'), H('서울동행맵\n(2024.11~)'), H('선행연구'), H('2024 경진대회\n최우수상'), { text:'evenly', options:{ align:'center', color:C.acc } }],
    [B('계단 없는 급경사 길까지 봄'), X, O, O, N, E],
    [B('집집마다(건물 단위) 계산'), X, X, X, N, E],
    [B('집 → 필수시설 일상 경로 기준'), X, O, X, O, E],
    [B('시설을 놓기 전 효과를 계산'), X, X, X, N, E],
    [B('같은 예산으로 후보 비교 (1억 원당)'), X, X, X, N, E]],   // [B안] 최우수상 칸은 제목으로 분명한 '일상 경로 기준'만 O, 나머지 -
    { y:1.74, colW:[2.7, 1.25, 1.2, 1.1, 1.35, 1.2], rowH:[0.5, 0.4, 0.4, 0.4, 0.4, 0.4], fontSize:11 });
  takeaway(s, '동행맵이 "오늘 가는 길"을 안내한다면, evenly 는 "어디에 길을 새로 낼지"를 정합니다.', 4.4);
  src(s, 'O = 함 · X = 하지 않음 · - = 공개 자료로 확인하지 못함 / 전수조사: 서울시 보도자료(2025.06)·아주경제(2025.02.20) · 동행맵: 서울시 교통정보(2024.11) · 최우수상: 과기정통부 보도자료(2024.11.01) · evenly 는 서울시 방식을 대체하지 않고 보완'); }
setSec(2, '데이터와 방법');
// ── B9 데이터 융합: LX 미개방·공공 원천 → 가공 데이터 다섯 가지 ──
{ const s = base('데이터 융합', 'LX 미개방 자료와 공공데이터를 다섯 가지 분석 자료로 묶습니다', { tsize:20 });
  const col = (x, y, w, h, head, items, fill, hc) => { s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius:0.08, fill:{ color:fill }, line:{ color:fill } });
    T(s, head, { x:x + 0.15, y:y + 0.08, w:w - 0.3, h:0.28, fontSize:12, bold:true, color:hc });
    T(s, items.join('\n'), { x:x + 0.15, y:y + 0.4, w:w - 0.3, h:h - 0.46, fontSize:10, color: hc === 'FFFFFF' ? 'E3EAF6' : C.text, lineSpacingMultiple:1.15 }); };
  col(0.6, 1.45, 3.1, 1.5, 'LX 미개방 데이터', ['수치지형도 1:5,000 (길·계단·건물)', 'DEM 5m (높이) · DEM 1m (검증)', '국토정보필지 (건물 ↔ 대장 연결)'], C.ink, 'FFFFFF');
  col(0.6, 3.08, 3.1, 1.72, '공공데이터', ['건축물대장 (용도·층수)', '약국·지하철 엘리베이터·버스정류소', '독거노인·장애인 (동별)', '생활인구·보행노인 사고다발지', '서울 오르락 공식 값 (대조)'], C.soft, C.ink);
  s.addShape(pres.shapes.LINE, { x:3.78, y:3.1, w:0.5, h:0, line:{ color:C.teal, width:2.5, endArrowType:'triangle' } });
  T(s, '가공 데이터 다섯 가지', { x:4.4, y:1.45, w:5, h:0.3, fontSize:12.5, bold:true, color:C.ink });
  [['보행망', '걸을 수 있는 길만 잇고 (자동차전용 제외), 계단 링크를 따로 셈'], ['경사', '링크 양 끝 높이로 오르막·내리막, 다리·터널은 0'],
   ['출발점', ALLM() ? '건물 → 필지 → 대장 (이번에는 모든 건물)' : '건물 → 필지 → 대장 주용도 (주거 건물)'], ['목적지', '약국·지하철 엘리베이터·버스정류소'], ['동 지표', '돌봄·외출·사고 (보조 관찰)']].forEach(([k, v], i) => { const y = 1.82 + i * 0.6;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:4.4, y, w:5.0, h:0.5, rectRadius:0.08, fill:{ color:'FFFFFF' }, line:{ color:C.line, width:1 } });
    s.addShape(pres.shapes.OVAL, { x:4.5, y:y + 0.09, w:0.32, h:0.32, fill:{ color:C.teal }, line:{ color:C.teal } });
    T(s, String(i + 1), { x:4.5, y:y + 0.09, w:0.32, h:0.32, fontSize:10, bold:true, color:'FFFFFF', align:'center', valign:'middle' });
    T(s, k, { x:4.95, y, w:0.95, h:0.5, fontSize:12, bold:true, color:C.ink, valign:'middle' });
    T(s, v, { x:5.9, y, w:3.45, h:0.5, fontSize:10, color:C.text, valign:'middle' }); });
  src(s, '자료별 형식·주요 필드는 10장 · 상호제공데이터는 쓰지 않음 · 결과는 250m 격자·행정동으로 집계해 반출'); }
// ── B10 주요 사용 데이터 목록 (A안 부록 1, 6칸) ──
{ const s = base('주요 사용 데이터', '주요 사용 데이터 목록', { tsize:24 });
  const M = t => B(t, { color:C.acc }), P_ = t => B(t);
  const rows10 = [['구분', '데이터셋명', '출처', '형식·기준', '주요 필드', '활용 목적'],
    [M('LX 미개방'), '수치지형도 1:5,000', '한국국토정보공사', 'shp · 2024.11', '도로(도로구분·자동차전용) · 계단(구조) · 건물(용도·층수)', '걷는 길·계단·건물'],
    [M('LX 미개방'), 'DEM 5M (수도권)', '한국국토정보공사', 'img · 2024.11', '표고 (5m 격자)', '링크 경사'],
    [M('LX 미개방'), 'DEM 1m', '한국국토정보공사', 'img · 관악구', '표고 (1m 격자)', '5m 결과 검증'],
    [M('LX 미개방'), '국토정보필지', '한국국토정보공사', 'shp · 2026.06', 'pnu · 지목', '건물 ↔ 대장 연결'],
    [P_('공공'), '건축물대장 · 법정동 코드', '서울시 · 행정안전부', 'csv · 2026', '주용도 · 층수 · 법정동 코드', '건물 용도'],
    [P_('공공'), '약국 · 역 엘리베이터 · 도보망', '공공데이터포털 · 서울시', 'csv · 2026', '위치 좌표 · 링크·노드', '목적지 · 공개 대조군'],
    [P_('공공'), '버스정류소 위치정보', '서울시', 'xlsx · 2026.09', '정류소 좌표', '정류장 검토 (22장)'],
    [P_('공공'), '고령 · 장애인 · 독거노인 현황', '행정안전부 · 서울시', 'csv · 2025~26', '행정동별 인원', '돌봄 대상 (21장)'],
    [P_('공공'), '생활인구 · 보행노인 사고다발지', '서울시 · 도로교통공단', 'csv · 2026.7 / 2012~24', '동별 시간대 인구 · 다발지 위치', '외출 · 사고 (보조)'],
    [P_('공공'), '서울 오르락 (고지대 이동편의시설)', '서울균형발전포털', '웹 · 2026.08', '대상지 고저차 · 연장 · 단계', '공식 값 대조 (15장)'],
    [P_('지도'), 'OpenStreetMap', '© OSM contributors', 'OSM 자료', '길 · 건물 · 계단 · 다리·터널', '배경지도 · 과정 그림']];
  etable(s, rows10, { y:1.38, colW:[0.8, 1.88, 1.4, 1.27, 2.0, 1.45], rowH:[0.3].concat(rows10.slice(1).map(() => 0.275)), fontSize:8 });
  src(s, '선행연구: 이희연 외(2015) 서울도시연구 / 구릉지 고령자 이동취약지역 연구 / 이소민·오성훈(2025) / 강현미·박소현(2009) · 지도 = © OpenStreetMap contributors'); }
// ── 11 방법 ── [10/20] 다섯 단계를 그림 다섯 칸으로: 공개 자료로 그린 과정 예시 (봉천 선정지 둘레 750m, 같은 범위·같은 축척, 결과 숫자 없음)
//   그림 = tools/make_process_figs.py → v6_source/proc11_1~5.png (공개 리허설 보행망·v6.2 같은 코드)
{ const s = base('분석 방법', '다섯 단계로 "체감 거리"를 계산합니다');
  const r_ = (t, o = {}) => ({ text:t, options:o }), k_ = (t, c) => r_(t, { color:c, bold:true });
  const P11 = [
    ['수치지형도', [r_('도로중심선('), k_('회색', C.muted), r_(')과 계단('), k_('주황', C.acc), r_((PFC || PFB) ? ')을 꺼냅니다. 옅은 선 = 등고선, 점선 원 = 봉천 선정지' : ')을 꺼냅니다. 점선 원 = 봉천 선정지')]],
    ['30m 조각 보행망', [r_('길과 계단을 30m 조각(점 = 노드)으로 나눠 하나의 보행망으로 잇습니다')]],
    ['조각마다 경사', [r_('조각마다 오르막·내리막 경사를 붙입니다', { breakLine:true }), k_('■', C.teal), r_('평지 '), k_('■', 'E3B23C'), r_('완만 '), k_('■', C.acc), r_('1/12 넘음')]],
    ['경로 비교', [r_('같은 집(●)에서 약국('), k_('■', C.teal), r_(')까지, 평지 가정 길('), k_('회색', C.muted), r_(')과 경사 반영 길('), k_('주황', C.acc), r_(')이 갈립니다')]],
    ['250m 격자', [r_('평지보다 몇 배 걸리는지 250m 격자로 모읍니다. 진할수록 부담이 큽니다')]]];
  P11.forEach((p, i) => { const x = 0.6 + i*1.79;
    T(s, [r_(`${i+1}  `, { bold:true, color:C.acc }), r_(p[0], { bold:true, color:C.ink })], { x, y:1.36, w:1.72, h:0.3, fontSize:12.5 });
    s.addImage({ path:img(`proc11_${i+1}.png`), x, y:1.7, w:1.64, h:1.64 });
    if (i < 4) T(s, '›', { x:x+1.64, y:2.3, w:0.15, h:0.4, fontSize:15, bold:true, color:C.muted, align:'center', valign:'middle' });
    T(s, p[1], { x, y:3.42, w:1.64, h:0.98, fontSize:10, color:C.text, lineSpacingMultiple:1.1 }); });
  T(s, '안심구역 안에서 자동 점검 뒤 실행하고, 250m 격자·행정동 집계만 반출합니다. 경사 모델은 부록 1, 가정값과 민감도는 부록 2', { x:0.6, y:4.5, w:8.8, h:0.3, fontSize:10.5, color:C.muted });
  src(s, PFC ? '과정 예시: 공개 자료(연속수치지형도 등고선)로 그림 · 분석은 LX 자료 · 봉천 선정지 둘레 750m, 다섯 칸 같은 축척 (막대 100m) · 길 = 연속수치지형도 도로중심선, '
             + '계단 = © OpenStreetMap contributors, 격자 = 같은 등고선 경사로 계산 (약국)'
             : PFB ? '과정 예시: 길·등고선 = 연속수치지형도, 경사·격자 = 공개 지형 (분석은 LX 자료) · 계단 = © OpenStreetMap contributors'   // [10/20] (가) 사용자 문구 + OSM 표기(ODbL)
             : '과정 예시: 공개 자료로 그림 (분석은 LX 자료) · 봉천 선정지 둘레 750m, 다섯 칸 같은 축척 (막대 100m) · 길 = 국토지리정보원 연속수치지형도, 계단 = © OpenStreetMap contributors, '
             + '높이 = 공개 지형 타일, 격자 = 공개 자료 보행망 계산 (약국)'); }   // [10/20] 등고선 그림이면 출처 줄이 바뀜

// ── 12 HBI ──
{ const s = base('핵심 지표', '언덕 부담 지수는 "평지보다 몇 배 걸리는가"입니다', { tsize:22 });
  box(s, 0.6, 1.42, 8.8, 0.95, C.ink);
  T(s, [{ text:'HBI', options:{ color:C.acc } }, { text:'  =  경사 반영 왕복 시간  ÷  평지 가정 왕복 시간', options:{ color:C.white } }], { x:0.9, y:1.48, w:8.3, h:0.5, fontSize:21, bold:true, valign:'middle' });
  T(s, '같은 사람이, 같은 집에서, 같은 목적지까지. 1.0이면 평지와 같습니다.', { x:0.9, y:1.98, w:8.3, h:0.3, fontSize:11.5, color:C.onDark });
  [[`${HB()} 미만`,'평지 수준',C.r1],[`HBI ${HB()} 이상`,'체감 부담',C.r2],[`왕복 +${RMIN()}분`,'고립 위험',C.r3]].forEach((b, i) => {   // 10/12: 고립 위험은 HBI 가 아니라 왕복 추가 시간
    const x = 0.6 + i*1.42; s.addShape(pres.shapes.RECTANGLE, { x, y:2.65, w:1.38, h:0.14, fill:{color:b[2]}, line:{color:b[2]} });
    T(s, b[0], { x, y:2.85, w:1.38, h:0.32, fontSize:13.5, bold:true, color:C.ink });
    T(s, b[1], { x, y:3.17, w:1.38, h:0.3, fontSize:12, color:C.muted }); });
  vr(s, 5.05, 2.6, 2.3);
  T(s, '예시: 3장 예시 길 (450m, 평균 경사 12%)', { x:5.3, y:2.62, w:4.1, h:0.3, fontSize:11.5, bold:true, color:C.muted });   // [10/14 v15] 할머니 길과 다른 길
  const ex12 = EX();   // [10/14 v15] 편도 오르막 옆에 왕복 배수 (HBI 정의가 왕복)
  [['편도 오르막', ex12.slope, ex12.flat, PF, C.ink], ['왕복 = HBI', ex12.rt, ex12.flat * 2, PF_RT, C.acc]].forEach((r, i) =>
    T(s, [{ text:`${r[0]}  `, options:{ color:C.muted, fontSize:11, bold:true } }, { text:`${r[1].toFixed(1)}분`, options:{ color:r[4], bold:true } }, { text:`  ÷  ${r[2].toFixed(1)}분  =  `, options:{ color:C.ink } }, { text:`${r[3].toFixed(2)}배`, options:{ color:r[4], bold:true } }],
      { x:5.3, y:2.93 + i * 0.4, w:4.15, h:0.4, fontSize:15, valign:'middle' }));
  T(s, '"분"이라 누구나 이해하고, 시설 설치 전후를 같은 잣대로 비교할 수 있습니다. 비율이라 보행속도 가정에도 덜 흔들립니다.', { x:5.3, y:3.82, w:4.1, h:0.9, fontSize:11.5, color:C.text, lineSpacingMultiple:1.12 });
  // [v6.3] 고립 위험 문턱의 근거 (5장 420m 와 같은 출처). [10/13 판정] 어르신 속도 = 결과의 elder_speed (0.7 이면 420 ÷ 0.7 = 편도 10분 딱 맞음)
  const m12 = 420 / SPD() / 60, eq12 = Math.abs(m12 - Math.round(m12)) < 0.05 ? '=' : '≈';
  T(s, [{ text:`왕복 +${RMIN()}분의 근거  `, options:{ bold:true, color:C.ink } }, { text:`후기고령자 평균 이동거리 420m ÷ 어르신 걸음 ${SPD()}m/s ${eq12} 편도 ${eq12 === '=' ? '' : '약 '}${Math.round(m12)}분 → 왕복 ${RMIN()}분 추가 = 감당 거리 하나가 통째로 더 붙는 것입니다.`, options:{ color:C.text } }],   // [10/20] 0.8 이면 '≈ 편도 약 9분'
    { x:0.6, y:3.62, w:4.3, h:0.95, fontSize:11, lineSpacingMultiple:1.12 });
  src(s, `체감 부담은 HBI(배수), 고립 위험은 왕복 추가 시간(분)으로 판정 / 문턱(${HB()}·${RMIN()}분)은 실제 관악 결과로 확정`); }

// ── 13 안심구역 ──
{ const s = base('데이터안심구역 분석', '데이터안심구역에서 직접 분석했습니다');
  // [10/14 v14] 방문한 날을 모두 칸으로 (deck/inputs.json visits: 날짜·한 일·done·optional), 왼쪽에 '안심구역 방문 총 ○일' 크게.
  //   다녀오지 않은 날 = '예정' (일수 빈칸), 예비 날(optional)은 괄호·회색 (실제·대비책 판에는 다녀왔을 때만)
  const vis13 = ((R.tables['V6.13.visits'] && R.tables['V6.13.visits'].rows) || []).filter(r => !((REAL || FALLBACK) && r.optional && !r.done));   // 제출 후보 판(실제·대비책)에는 다녀온 예비 날만
  T(s, '안심구역 방문', { x:0.6, y:1.45, w:2.3, h:0.3, fontSize:12.5, bold:true, color:C.muted });
  T(s, [{ text:'총 ', options:{ fontSize:18, color:C.ink } }, { text:V('V6.13.n_visits', '___일'), options:{ fontSize:36, color:C.acc } }], { x:0.6, y:1.72, w:2.3, h:0.66, bold:true, valign:'bottom' });
  const n5_13 = hasR('V6.13.n_bld5') ? [{ text:'대상 5개 구 분석', options:{ bold:true, color:C.ink, breakLine:true } }, { text:`(${Q('V6.13.gus5', '종로·중구·관악·광진·강서')}, ${R.fields['V6.13.n_bld5'].value} 건물)`, options:{ color:C.muted } }] : null;   // [10/21] 갈래 A
  if (n5_13 && !hasR('V6.15.has_meas')) T(s, n5_13, { x:0.6, y:2.55, w:2.3, h:0.62, fontSize:10.5, lineSpacingMultiple:1.1 });
  if (!(REAL || FALLBACK) || hasR('V6.15.has_meas')) {   // [10/20] 실제판·대비책 판은 10/21 실측이 들어왔을 때만
    T(s, [{ text:'현장실측  ', options:{ bold:true, color:C.ink } }, { text:V('V6.15.date', '2026.10.___'), options:{ color:C.ink } }], { x:0.6, y:2.55, w:2.3, h:0.28, fontSize:11 });
    T(s, FALLBACK ? '관악 4구간을 직접 걸어 지도앱 시간과 비교' : '관악 4구간을 직접 걸어 모델 예측과 비교', { x:0.6, y:2.84, w:2.3, h:0.42, fontSize:10, color:C.muted }); }
  if (vis13.length) { const n = vis13.length, x0 = 3.1, W = 6.3, w = (W - (n - 1) * 0.1) / n;
    vis13.forEach((r, i) => { const x = x0 + i * (w + 0.1), dim = r.optional && !r.done, plan = !r.done && !r.optional;
      hr(s, x, 1.5, w, dim ? C.line : (r.done ? C.ink : C.acc), 2);
      T(s, dim ? `(${r.date})` : r.date, { x, y:1.6, w, h:0.4, fontSize:17, bold:true, color: dim ? C.muted : C.ink });
      T(s, `${r.wd}요일` + (plan ? ' · 예정' : dim ? ' · 예비' : ''), { x, y:2.0, w, h:0.26, fontSize:10, color: plan ? C.acc : C.muted });
      T(s, r.work, { x, y:2.32, w, h:0.9, fontSize:11.5, color: dim ? C.muted : C.text, lineSpacingMultiple:1.1 }); }); }
  else T(s, '방문일 자리 (deck/inputs.json 의 visits)', { x:3.1, y:1.6, w:6.3, h:0.4, fontSize:12, color:C.muted });
  hr(s, 0.6, 3.36, 8.8);   // [10/14 v11] 아래 네 칸: 사전 준비 · 반출 원칙 / 왜 관악구부터 · 1인 수행
  const cell13 = (x, y, w, title, body, col, h = 0.72) => { bar(s, x, y, h, col); T(s, title, { x:x+0.22, y, w:w-0.22, h:0.26, fontSize:12, bold:true, color:col });
    T(s, body, { x:x+0.22, y:y+0.28, w:w-0.22, h:h-0.26, fontSize:10.5, color:C.text, valign:'top', lineSpacingMultiple:1.05 }); };
  cell13(0.6, 3.46, 4.4, '안심구역 밖 사전 준비', '공개데이터로 코드를 미리 시험하고, 자료 구조가 달라도 스스로 맞추는 자동 점검 도구를 준비', C.ink);
  cell13(5.2, 3.46, 4.2, '반출 원칙', '250m 격자·행정동 집계만 반출, 건물 5개 미만 칸 제외. 건물·필지 단위 결과와 소유 정보는 반출하지 않음', C.acc);
  cell13(0.6, 4.28, 4.4, '왜 관악구부터', Q('V6.13.gwanak_reason', '서울시 2025 선정지(봉천동)가 있고, 1m 높이로 5m 결과를 검증할 수 있는 구') + (has('V6.13.hill') ? '\n' + R.fields['V6.13.hill'].value : ''), C.ink, 0.86);
  cell13(5.2, 4.28, 4.2, '1인 수행', hasR('V6.15.has_meas') ? '코드·현장실측·기획을 한 사람이 끝까지' : '코드·분석·기획을 한 사람이 끝까지', C.ink, 0.86);   // [10/21] 실측을 안 했으면 '분석'
  { const n13 = [has('V6.13.hill_area') ? R.fields['V6.13.hill_area'].value : '', (hasR('V6.13.n_visits') && (hasR('V6.15.date') || ((REAL || FALLBACK) && !hasR('V6.15.has_meas')))) ? '' : '방문일은 다녀온 날로 기입'].filter(x => x);   // [10/13 판정 3] 구 면적 비율은 출처 줄
    if (n13.length) src(s, n13.join(' / ')); } }

setSec(3, '분석 결과');
// ── 14 결과 ① 사각지대 ── [10/13 v9 청사진]
{ const s = base('관악구에서 찾은 것' + SFX(), () => FALLBACK
    ? `관악 일대 건물의 약 ${V('V6.fb.share13')}%가 평지보다 ${Math.round((Number(HB()) - 1) * 100)}% 넘게 더 걸립니다`   // [10/13] 대비책 판: 1차 HBI 1.3 이상 비율
    : `평지 지도에서 "가까운 동네"의 ${V('V6.14.near_burden')}%가 실제로는 ${Math.round((Number(HB()) - 1) * 100)}% 넘게 더 걸립니다`, { tsize:19 });
  if (FALLBACK) {   // [10/20] 대비책 판: 1차 반출(10/2) 값만. 지도·고립 위험·어르신·동은 반출(10/19)이 있어야 해서 빼고 구간 막대로
    const p13 = Number(V('V6.fb.share13')), p18 = Number(V('V6.fb.share18')), up14 = Math.round((Number(HB()) - 1) * 100);
    T(s, '1차 반출(10/2) · 관악 일대 건물의 언덕 부담', { x:0.6, y:1.45, w:4.75, h:0.3, fontSize:12.5, bold:true, color:C.ink });
    const W14 = 4.75, w18 = Math.max(0.04, W14 * p18 / 100), w13 = Math.max(0.08, W14 * p13 / 100 - w18);   // 비율 그대로 (1.3 미만 = 나머지)
    [[0.6, W14 - w13 - w18, C.r1], [0.6 + W14 - w13 - w18, w13, C.r2], [0.6 + W14 - w18, w18, C.r3]].forEach(([x, w, c]) =>
      s.addShape(pres.shapes.RECTANGLE, { x, y:1.85, w, h:0.5, fill:{ color:c }, line:{ color:c, width:0.5 } }));
    T(s, `HBI ${HB()} 이상 약 ${p13}% ↑`, { x:2.6, y:2.4, w:2.75, h:0.26, fontSize:11, bold:true, color:C.accD, align:'right' });
    [[C.r1, `평지 수준 (HBI ${HB()} 미만)`], [C.r2, `체감 부담 (${HB()} 이상)`], [C.r3, '1.8 이상']].forEach(([c, t], i) => { const x = 0.6 + [0, 1.75, 3.3][i];
      s.addShape(pres.shapes.RECTANGLE, { x, y:2.83, w:0.14, h:0.14, fill:{ color:c }, line:{ color:c } });
      T(s, t, { x:x + 0.19, y:2.77, w:1.55, h:0.26, fontSize:9.5, color:C.text, valign:'middle' }); });
    box(s, 0.6, 3.2, 4.75, 1.25, C.soft);
    T(s, [{ text:'HBI', options:{ bold:true, color:C.acc } }, { text:'  =  경사 반영 왕복 시간 ÷ 평지 가정 왕복 시간', options:{ bold:true, color:C.ink, breakLine:true } },
          { text:`${HB()} = 평지보다 ${up14}% 더 걸림 (체감 부담) · 1.8 = 80% 더`, options:{ color:C.text, breakLine:true } },
          { text:`어르신 ${SPD()}m/s · 목적지 약국 · 모든 건물을 집으로 봄`, options:{ color:C.muted } }],
      { x:0.8, y:3.2, w:4.45, h:1.25, fontSize:11, valign:'middle', lineSpacingMultiple:1.2 });
    stat(s, 6.25, 1.45, 3.2, `평지보다 ${up14}% 넘게 더 걸리는 건물`, `약 ${p13}%`, { size:24, color:C.acc });
    T(s, `HBI ${HB()} 이상 · 관악 일대 행정동 ${Q('V6.fb.n_dong', '52')}개 (옆 구 일부 포함)`, { x:6.25, y:2.2, w:3.2, h:0.35, fontSize:10, color:C.muted, lineSpacingMultiple:1.05 });
    hr(s, 6.25, 2.6, 3.2);
    stat(s, 6.25, 2.68, 3.2, '그중 80% 넘게 더 걸리는 건물 (HBI 1.8 이상)', `${V('V6.fb.share18')}%`, { size:17 });
    hr(s, 6.25, 3.45, 3.2);
    stat(s, 6.25, 3.55, 3.2, '건물 HBI 중앙값', V('V6.fb.hbi_median'), { size:17 });
    takeaway(s, `거리만 보는 지도에서는 이 ${p13}%가 평지와 같게 나옵니다.`, 4.68);
    src(s, Q('V6.fb.limits', '1차 반출(10/2) 값'));
  } else {
  const m = IMG('V6.map');
  if (m) s.addImage({ path:m, x:0.6, y:1.42, w:4.75, h:3.16 });
  else slot(s, 0.6, 1.42, 4.75, 3.16, `결과 지도 자리\n${SCOPE} 250m 격자 · 언덕 부담 지수`, 'V6.map');
  const rb14 = V('V6.14.risk_n'), pc14 = has('V6.14.risk_bld') ? (String(R.fields['V6.14.risk_bld'].value).split(' · ')[1] || '') : '';
  stat(s, 6.25, 1.45, 3.2, `왕복 ${RMIN()}분 넘게 잃는 ${BLDS()} (고립 위험)`, rb14, { size:24, color: isLater(rb14) ? undefined : C.acc });
  if (pc14) T(s, `${Q('V6.scope', '관악구')} ${ALLM() ? pc14.replace('주거의', '건물의') : pc14.replace('주거의', '주거 건물의')}` + (has('V6.14.risk_split') ? `\n${R.fields['V6.14.risk_split'].value.replace(', ', ' · ')}` : ''), { x:6.25, y:2.2, w:3.2, h:0.35, fontSize:10, color:C.muted, lineSpacingMultiple:1.05 });
  hr(s, 6.25, 2.6, 3.2);
  // [10/20] all 방식: 연면적 배분이 상가까지 들어가 어르신 추정은 뺌 → '가장 급한 동'을 올림
  const yTop14 = ALLM() ? 2.7 : 3.55;
  if (!ALLM()) { stat(s, 6.25, 2.68, 3.2, '그 집에 사는 어르신 (추정)', V('V6.14.elderly'), { size:17 }); hr(s, 6.25, 3.45, 3.2); }
  const top14 = has('V6.14.top_name') ? R.fields['V6.14.top_name'].value : V('V6.14.top_dong');
  stat(s, 6.25, yTop14, 3.2, '가장 급한 동', top14, { size:17 });
  if (has('V6.14.top_share')) T(s, R.fields['V6.14.top_share'].value, { x:6.25, y:yTop14 + 0.75, w:3.2, h:0.25, fontSize:11, color:C.muted });
  takeaway(s, (has('V6.14.top_name') && Q('V6.14.top_no_site', 'no') === 'yes') ? `가장 급한 ${top14}은 서울시 2025 선정지 5곳에 없습니다.` : '거리만 보는 지도에서는 이 동네들이 "가깝다"고 나옵니다.', 4.68);
  const nt = has('V6.14.elderly_note') ? ` (${R.fields['V6.14.elderly_note'].value})` : '';
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + (ALLM() ? `${LXS} (모든 건물 기준) · ` : '') + (has('V6.14.near_min') ? `가까운 동네 = 평지 기준 왕복 ${R.fields['V6.14.near_min'].value}분(격자 중앙값) 안에 ${DEST()}이 있는 250m 격자 · ` : '')
      + (ALLM() ? Q('V6.14.mode_note', '건물 용도 연결률이 낮아 모든 건물을 출발점으로 계산') : `어르신은 행정동 65세 이상 인구를 주거 연면적으로 나눈 추정${nt} (행정안전부 주민등록 인구통계)`)
      + (hasR('V6.14.basemap') ? ` · 배경지도: ${R.fields['V6.14.basemap'].value} 자료로 그림` : '')); } }   // [10/20] 저장된 배경지도 (tools/make_basemap.py)

// ── 15 현장실측 ── [10/20] 실측(10/21, inputs.json 보통·천천히·지도앱) 있으면 실측 vs 모델(반출 성인·어르신), 없으면 모델만 (대비 배치)
// [10/21] 실제판·대비책 판에서 실측이 없으면: 봉천 선정지 계단, 네 자료 대조 (서울 오르락 공식 · LX DEM 5m·1m · 공개 지형 30m) + 서울시 사진 두 장 (원본 비율, 바로 아래 출처)
if (!hasR('V6.15.has_meas') && (REAL || FALLBACK)) {
  const s = base('서울시 공식 자료와 대조', '봉천 선정지 계단, 네 자료 대조', { tsize:24 });
  const b1 = OR.bongcheon1;
  etable(s, [['자료', '높이 차', '길이'],
    [B('서울시 공식'), B(`${b1.rise_m}m`), `연장 ${b1.length_m}m (경사도 ${b1.slope}, 폭 ${b1.width_m}m)`],
    [B('LX DEM 5m'), B(V('V6.16.rise_lx'), { color:C.acc }), `양 끝 직선 ${V('V6.15.lx_straight')} (${hasR('V6.lxexp') ? '반출' : '10/20 메모'})`],   // [10/21] 반출 값이면 출처 반출
    [B('LX DEM 1m'), B(V('V6.16.rise_1m'), { color:C.acc }), '- (10/20 메모)'],
    [B('공개 지형 30m'), B(V('V6.16.rise_pub'), { color:C.muted }), '- (공개 계산)']],
    { x:0.6, y:1.45, w:4.75, colW:[1.3, 0.85, 2.6], rowH:[0.4, 0.55, 0.55, 0.55, 0.55], fontSize:11 });
  // 사진: 원본 비율 그대로 (자르기·덧씌우기 없음), 이름표·출처는 사진 아래. 두 장이 다 있을 때만 (없으면 표만)
  const pf = (OR.photos.files || []).map(f => path.join('..', f));
  if (pf.length === 2 && pf.every(f => fs.existsSync(f))) {
    const pw = 1.9, gp = 0.1, x0 = 5.5;   // 5.5~9.4
    let yb = 1.45;
    pf.forEach((f, i) => { const z = imgSize(f), ph = z && z.w ? pw * z.h / z.w : pw * 0.75, x = x0 + i * (pw + gp);
      s.addImage({ path:f, x, y:1.45, w:pw, h:ph });
      T(s, OR.photos.labels[i], { x, y:1.45 + ph + 0.04, w:pw, h:0.2, fontSize:9, color:C.ink });
      yb = Math.max(yb, 1.45 + ph + 0.26); });
    T(s, OR.photos.credit, { x:x0, y:yb, w:pw * 2 + gp, h:0.2, fontSize:8.5, color:C.muted });
    T(s, `서울시 ${b1.stage}단계 대상지 (${b1.name})\n${b1.type} 계획`, { x:x0, y:yb + 0.36, w:pw * 2 + gp, h:0.4, fontSize:9.5, color:C.text, lineSpacingMultiple:1.05 });
  } else console.error('!! 15장: 서울시 사진 두 장(deck/seoul_orak.json photos.files)이 없어 표만 넣음');
  takeaway(s, 'LX 자료는 서울시 공식 고저차와 1m 안쪽으로 맞고, 공개 지형은 절반으로 잡습니다.', 4.4);
  { const n_ = k => Number(String(hasR(k) ? R.fields[k].value : '').replace(/[^0-9.]/g, '')), r0 = b1.rise_m;   // 결론 문장이 값과 맞는지 (값이 바뀌면 멈춤)
    const ok = [n_('V6.16.rise_lx'), n_('V6.16.rise_1m')].every(v => v && Math.abs(v - r0) < 1) && n_('V6.16.rise_pub') && Math.abs(n_('V6.16.rise_pub') / r0 - 0.5) < 0.05;
    if (!ok) { console.error('!! 15장 결론 문장("1m 안쪽"·"절반")이 값과 맞지 않음 — 문장을 고칠 것'); process.exitCode = 1; } }
  src(s, `서울시 공식 = ${OR.source_short} · ` + (hasR('V6.lxexp') ? `LX DEM 5m = ${LXS} (반출) · DEM 1m = ${LXS} (10/20 현장 메모)` : `LX DEM 5m·1m = ${LXS} (10/20 현장 메모)`) + ' · 공개 지형 30m = 공개 자료 계산');
} else { const meas15 = hasR('V6.15.has_meas');
  const s = base('직접 걸어 본 관악구', FALLBACK ? (meas15 ? '관악 네 구간을 직접 걸어서 확인했습니다' : '관악 네 구간을 직접 걸어서 확인합니다')   // [10/20] 대비책 판: 모델(10/19 반출) 없이
                                       : meas15 ? '모델이 말한 시간을 직접 걸어서 확인했습니다' : '관악 네 구간, 성인과 어르신의 걸음 차이', { tsize:22 });
  // [10/13] 사진: tools/prep_photos.py 가 docs/photos/15_1~15_4 를 바로 세우고 촬영 정보(GPS)를 지운 사본 docs/photos/_deck/15_N.jpg 가 있으면 넣고
  //   (가운데를 잘라 칸에 맞춤), 없으면 자리 표시 (실제판은 자리 상자 없이 표를 넓힘). 원본(EXIF 남음)은 읽지 않음. 사진은 git 에 넣지 않음
  const phs = ['봉천동 선정지 계단','봉천역 → 언덕 오르막','도림천 산책로 (평지)','낙성대역 → 언덕'].map((p, i) => [p, [`../docs/photos/_deck/15_${i+1}.jpg`].find(f => fs.existsSync(f))]);
  const photos = phs.some(p => p[1]) || !(REAL || FALLBACK);   // [10/20] 대비책 판도 사진이 없으면 자리 상자 없이 표를 넓힘
  if (photos) phs.forEach(([p, ph], i) => { const x = 0.6 + (i%2)*2.25, y = 1.45 + Math.floor(i/2)*1.6;
    if (!ph) return slot(s, x, y, 2.1, 1.45, '사진 자리\n' + p);
    s.addImage(Object.assign({ path:ph, x, y }, photoCover(ph, 2.1, 1.45)));
    box(s, x, y+1.17, 2.1, 0.28, C.white); T(s, p, { x:x+0.08, y:y+1.17, w:1.94, h:0.28, fontSize:9.5, color:C.ink, valign:'middle' }); });
  const rn = ['계단 · 봉천 선정지','오르막 · 봉천역','평지 · 도림천','오르막 · 낙성대'];   // 10/12 청사진: prepare 의 V6.15.<i> 도 관악 네 구간 (현장실측①~④)
  const tx = photos ? 5.25 : 0.6, tw = photos ? 4.15 : 8.8;
  // [10/20] 대비책 판: 모델 칸(10/19 반출)을 빼고, 실측이 있으면 지도앱·실측만, 없으면 구간마다 보는 것
  const FB15 = ['계단을 오르내리는 시간 (휠체어는 못 지남)', '역에서 언덕 위로 오르는 길', '경사가 거의 없는 길 (평지 기준)', '역에서 언덕 위로 오르는 길'];
  const head = FALLBACK ? (meas15 ? ['구간','지도앱','보통 걸음\n(실측)','천천히\n(실측)'] : ['구간','무엇을 보나'])
             : meas15 ? ['구간','지도앱','보통 걸음\n(실측)','모델\n성인','천천히\n(실측)',`모델\n어르신`] : ['구간','모델 성인 (1.1m/s)',`모델 어르신 (${SPD()}m/s, 경사 반영)`];
  const r15 = rn.map((n, i) => FALLBACK ? (meas15 ? [V(`V6.15.${i}.app`), V(`V6.15.${i}.meas`), Q(`V6.15.${i}.slow`, '-')] : [FB15[i]])
            : meas15 ? [V(`V6.15.${i}.app`), V(`V6.15.${i}.meas`), V(`V6.15.${i}.model`), Q(`V6.15.${i}.slow`, '-'), V(`V6.15.${i}.elder`)]
                     : [V(`V6.15.${i}.model`), V(`V6.15.${i}.elder`)]);
  const cw15 = FALLBACK ? (meas15 ? (photos ? [1.45, 0.9, 0.9, 0.9] : [3.2, 1.86, 1.87, 1.87]) : (photos ? [1.55, 2.6] : [3.2, 5.6]))
             : meas15 ? (photos ? [1.15, 0.6, 0.6, 0.6, 0.6, 0.6] : [2.6, 1.24, 1.24, 1.24, 1.24, 1.24]) : (photos ? [1.75, 1.2, 1.2] : [3.2, 2.8, 2.8]);
  etable(s, [head].concat(rn.map((n, i) => [B(n)].concat(r15[i]))), { x:tx, w:tw, colW:cw15, rowH:[0.42,0.42,0.42,0.42,0.42], fontSize: meas15 && photos && !FALLBACK ? 9 : 10.5 });
  bar(s, tx, 3.95, 0.95);
  T(s, meas15 ? [{ text:'봉천 선정지 계단: 오름 3회 · 내림 1회', options:{ bold:true, color:C.ink, breakLine:true } }, { text:'성인이 평소 걸음으로 한 번, 어르신 걸음을 흉내 내 천천히 한 번', options:{ color:C.muted } }]
              : FALLBACK ? [{ text:'같은 출발·도착을 지도앱 도보 안내와 비교', options:{ bold:true, color:C.ink, breakLine:true } }, { text:'성인이 평소 걸음으로 한 번, 어르신 걸음을 흉내 내 천천히 한 번', options:{ color:C.muted } }]
              : [{ text:'LX 5m 높이로 계산한 네 구간', options:{ bold:true, color:C.ink, breakLine:true } }, { text:`성인 1.1m/s · 어르신 ${SPD()}m/s, 오르막·계단 부담 반영`, options:{ color:C.muted } }],
    { x:tx + 0.22, y:3.95, w:tw - 0.2, h:0.95, fontSize:12, valign:'middle' });
  src(s, FALLBACK ? (meas15 ? `측정 ${V('V6.15.date', '2026.10.___')} · 실측 = 현장 실측 (10/21) · 지도앱은 같은 출발·도착의 도보 안내 시간 / 사람 얼굴·집 안·번지 표지는 찍지 않음`
                             : '현장 실측 구간 = 관악 검증 경로 네 줄 / 사람 얼굴·집 안·번지 표지는 찍지 않음')
       : meas15 ? `측정 ${V('V6.15.date', '2026.10.___')} · 실측 = 현장 실측 (10/21) · 모델 = ${LXS} (10/19 반출) · 지도앱은 같은 출발·도착의 도보 안내 시간 / 사람 얼굴·집 안·번지 표지는 찍지 않음`
                : `모델 = ${LXS} (10/19 반출, 관악 검증 경로 네 줄) · 현장 실측은 이 장의 대비 배치에 넣지 않음`); }

// ── 16 결과 ② 신뢰 ── [10/13 v9 청사진]
{ const s = base('관악구에서 찾은 것', () => {   // [10/14 v14] 봉천(관악만) 결과면 "서울시가 고른 봉천은 모델에서도 상위 n%였고, …"
    if (FALLBACK) { const f16 = /상위\s*([0-9.]+)%/.exec(String(V('V6.16.site')));   // [10/20] 대비책 판: 1차 반출 백분위 + 봉천 계단 높이 차 (공개 계산·10/20 메모)
      return `서울시가 고른 봉천은 1차 분석에서도 상위 ${f16 ? Math.round(Number(f16[1])) : V('V6.16.site')}%였고,\n`
           + (has('V6.16.rise_pub') ? `봉천 계단 높이를 공개 지형은 ${R.fields['V6.16.rise_pub'].value}, LX 는 ${R.fields['V6.16.rise_lx'].value}로 잡습니다` : '이 계산에는 LX 의 5m 높이가 필요합니다'); }
    if (hasR('V6.16.sites_n') && Q('V6.16.sites_top3', 'no') === 'yes')   // [10/21] 갈래 A (5개 구): 서울시 1단계 선정지 계산된 곳 모두 상위 3분의 1
      return `서울시 1단계 선정지 ${['', '한', '두', '세', '네'][Number(R.fields['V6.16.sites_n'].value)] || R.fields['V6.16.sites_n'].value} 곳 모두 우리 모델에서 상위 3분의 1 안`;
    const m16 = hasR('V6.16.site') ? /상위\s*([0-9.]+)%/.exec(String(R.fields['V6.16.site'].value)) : null;
    return (m16 && /봉천/.test(Q('V6.16.site_label', ''))) ? `서울시가 고른 봉천은 모델에서도 상위 ${Math.round(Number(m16[1]))}%였고,\n높이를 빼면 ${V('V6.16.dem_top10')}가 바뀝니다`
                                                         : `서울시의 선택을 다시 찾아냈고, 높이를 빼면 ${V('V6.16.dem_top10')}가 바뀝니다`; }, { tsize:19 });
  T(s, '이 결과를 믿어도 되나', { x:0.6, y:1.45, w:4, h:0.32, fontSize:13.5, bold:true, color:C.ink }); hr(s, 0.6, 1.82, 4.1, C.ink, 1.25);
  const sl16 = Q('V6.16.site_label', '서울시 2025 선정지 5곳 중 상위 10%'), wl16 = Q('V6.16.wheel_label', '대현산 휠체어 우회 (서울시: 약 770m)');
  const g16 = FALLBACK ? 1.0 : 0.8;   // [10/20] 대비책 판: 휠체어 우회·높이 뺀 변화·공개 놓침(10/19 반출)을 빼고 두 줄씩
  // [10/21] 첫 줄 끝: 서울시 2단계 대상지(봉천초 인근)가 든 250m 격자의 백분위 (반출 격자). 반출 전(미리 빌드) = 빈칸, 대비책 판 = 없음
  //   값을 먼저 읽어야 빈칸 짝(선정지 → 2단계)이 같은 줄에 맞음
  const site16 = V('V6.16.site');
  const s2v16 = (FALLBACK || hasR('V6.16.sites_n')) ? '' : hasR('V6.16.site2') ? String(R.fields['V6.16.site2'].value) : ((REAL && !hasR('V6.24.grid')) ? V('V6.16.site2') : '');
  const n16 = Number((/상위\s*([0-9.]+)%/.exec(s2v16) || [])[1]);   // "도" 는 상위 30% 안일 때만, 아니면 받침에 맞춰 은/는
  const jb16 = (w => { const c = w.charCodeAt(w.length - 1) - 0xAC00; return c >= 0 && c <= 11171 && c % 28 !== 0; })(OR.bongcheon2.name);
  const pt16 = (isNaN(n16) || n16 <= 30) ? '도' : (jb16 ? '은' : '는');
  (FALLBACK ? [['서울시가 고른 봉천동은 관악 일대 격자 중 (1차 반출)', site16], ['DEM 1m 로 다시 계산해도 (1m 범위 안 집)', `순위상관 ${V('V6.16.dem1m')}`]]
   : [[/봉천/.test(sl16) ? `서울시가 고른 봉천동은 ${Q('V6.scope', '관악구')} 격자 중` : sl16, site16],
   [/봉천/.test(wl16) ? '봉천 계단을 피하는 휠체어 길 (서울시 발표 200m 이상)' : wl16, V('V6.16.wheel')],
   hasR('V6.16.dem1m') ? ['DEM 1m 로 다시 계산해도 (1m 범위 안 집)', `순위상관 ${R.fields['V6.16.dem1m'].value}`] : ['직접 걸은 4구간, 모델 예측과 실측의 상관', V('V6.16.meas_r')]])
    .forEach((r, i) => stat(s, 0.6, 1.95+i*g16, 4.1, r[0], r[1], Object.assign({ size:(i === 0 && hasR('V6.16.sites_n')) ? 14 : 18, color:C.ink }, (i === 0 && s2v16) ? { suffix:`  · 2단계 ${OR.bongcheon2.name}${pt16} ${s2v16}` } : {})));   // [10/20] 실측 상관 대신 DEM 1m (현장 메모)
  T(s, '왜 LX 자료여야 하나', { x:5.3, y:1.45, w:4, h:0.32, fontSize:13.5, bold:true, color:C.ink }); hr(s, 5.3, 1.82, 4.1, C.ink, 1.25);
  const rz16 = has('V6.16.rise_pub') ? [`같은 봉천 계단 높이 차: 공개 지형 → LX${has('V6.16.rise_1m') ? ` (DEM 1m ${R.fields['V6.16.rise_1m'].value})` : ''}`, `${R.fields['V6.16.rise_pub'].value} → ${R.fields['V6.16.rise_lx'].value}`, FALLBACK ? C.acc : C.ink, 18] : null;   // [10/20] LX 필요성 근거
  const np16 = ['자동차전용도로·단독/공동주택 구분', '공개 자료에는 없음', C.ink, 15];
  (FALLBACK ? [rz16, np16].filter(Boolean) : (() => { const d16 = V('V6.16.dem_top10');
    return [[`5m 높이를 빼면, 가장 급한 상위 10% 중 바뀌는 ${BLDS()}${hasR('V6.13.n_bld5') ? ' (5개 구)' : ''}`, has('V6.16.dem_missed') ? `${d16} (${R.fields['V6.16.dem_missed'].value})` : d16, C.acc, 18],
            ['500m로 묶어 평균 내면 가려지는 부담 큰 건물 (HBI 1.8 이상)', V('V6.16.agg500'), C.ink, 18], rz16 || np16]; })())   // [10/21] 공개 대조 줄 대신 500m 집계 (validation_ablation)
    .forEach((r, i) => stat(s, 5.3, 1.95+i*g16, 4.1, r[0], r[1], Object.assign({ size:r[3], color:r[2] },
      r === rz16 ? { suffix:`  (서울시 공식 ${OR.bongcheon1.rise_m}m)` } : (i === 1 && REAL) ? { suffix: hasR('V6.13.n_bld5') ? '  (LX, 5개 구)' : '  (LX)' } : {})));   // [10/21] 서울 오르락 고저차 · 500m 집계 출처
  takeaway(s, '그래서 이 결과는 믿을 만하고, 이 계산에는 LX의 5m 높이가 꼭 필요합니다.', 4.55);
  const notes16 = [has('V6.16.wheel_note') ? R.fields['V6.16.wheel_note'].value : null, has('V6.16.daehyun_note') ? R.fields['V6.16.daehyun_note'].value : null].filter(Boolean).join(' · ');
  src(s, FALLBACK ? `선정지 백분위 = 1차 반출(10/2) 값 · DEM 1m 순위상관·봉천 높이 차 LX = ${LXS} (10/20 현장 메모) · 공개 지형 높이 차 = 공개 자료 계산 · 서울시 공식 = 서울 오르락 · 보행속도 출처는 부록 1`
    : (REH ? '공개 대역(리허설) 값 · ' : '') + (ALLM() ? `${LXS} (${hasR('V6.lxexp') ? '반출' : '10/19 반출·10/20 현장 메모 DEM 1m'}) · `
      + (has('V6.16.rise_pub') ? `봉천 높이 차: 공개 = 공개 자료 계산, LX = ${hasR('V6.lxexp') ? '반출(09)·DEM 1m = 현장 메모' : '현장 메모(09)'}, 서울시 = 서울 오르락 · ` : '') : '') + '선정지 백분위 = 반경 300m 원 평균'
      + (hasR('V6.16.sites_n') ? ` (5개 구${hasR('V6.16.sites_na') ? `, ${R.fields['V6.16.sites_na'].value}은 자료 가장자리라 계산 안 됨` : ''})` : '')
    + (s2v16 ? `, 2단계 = 그 250m 격자 (위치: 국토정보필지 공개판)` : '') + ' · 대조군·계단·보행속도 출처는 부록 1'); }   // [10/14 v11] 한 줄만, 나머지는 부록 1   // [10/21] 2단계 대상지

// ── 17 우선 검토 후보 ──
const NCAND = () => V('V6.17.n_cand');
// [v6.3] 09 후보 자동 결과(intervention_candidates.csv)가 있으면 후보·선정지 비교표 (후보별 수혜·1억 원당·규모별 처방), 없으면 v6.2 격자 표
const CANDT = (R.tables['V6.17.cand'] && R.tables['V6.17.cand'].rows && R.tables['V6.17.cand'].rows.length) ? R.tables['V6.17.cand'].rows : null;
if (CANDT) {
  const s = base('관악구에서 찾은 것' + (FALLBACK ? '' : SFX()), () => LXTOP   // [10/21] 실제판: LX 고립 위험 중심 제목
    ? [{ text:`${LXTOP.dong} 두 곳`, options:{ color:C.acc } }, { text:'에 고립 위험 건물이 몰려 있습니다', options:{ color:C.ink } }]
    : [{ text:'같은 예산으로 더 많은 집을 돕는 곳이 ', options:{ color:C.ink } }, { text:V('V6.17.n_facility'), options:{ color:C.acc } }, { text:' 있습니다', options:{ color:C.ink } }]);   // [10/14 v11]   // [10/13 v9] 표는 A1 (후보 자동, 1억 원당 5)
  // [10/13 판정] 단위 '개', 수혜를 고령자(왕복 30초 이상)·휠체어(왕복 1분 이상)로 나눔. 1억 원당 = 둘 중 하나라도 해당하는 건물 ÷ 40
  // [10/20] 실제판(mixed): 부담(고립 위험·왕복 추가) = LX 반출 격자, 시설 효과 = 공개 자료 보행망, 봉천 = LX 현장 메모 → 8칸, 시설 칸 짧게
  const mixed = CANDT.some(r => r.src), noLx = FALLBACK;   // [10/20] 대비책 판: 부담 칸(고립 위험·왕복 추가 = 10/19 반출)을 뺌
  const unit = v => (v === '' || v === null || v === undefined) ? '-' : (/^[0-9.]+$/.test(String(v)) ? `${v}개` : String(v).replace('채', '개'));
  const mins = v => (v === '' || v === null || v === undefined || isNaN(Number(v))) ? '-' : `${Number(v).toFixed(1)}분`;
  const per = r => r.ramp ? { text:'소규모\n(경사로)', options:{ fontSize:9 } }   // [10/14 v12] 경사로는 1억 원당 숫자를 내지 않음
                          : { text:(r.per100m === '' || r.per100m === null) ? '-' : isNaN(Number(r.per100m)) ? String(r.per100m) : (Number(r.per100m) >= 100 ? `${Math.round(Number(r.per100m)).toLocaleString('en-US')}개` : `${Number(r.per100m).toFixed(1)}개`), options:{} };
  const rxc = r => { const fac = r.rx === '큰 시설 검토' || r.rx === '바로 정비';
    if (mixed && r.kind !== '후보' && r.alt && r.alt.wheel) return B(`휠체어 접근 효과 (${r.alt.tgt} ${r.alt.wheel})`, { color:C.ink, fontSize:9 });   // [10/20] 봉천 = 공개 계산, 역 기준 휠체어
    return B({ '난간·쉼터·계단 정비 + 방문돌봄':'정비 + 방문돌봄' }[r.rx] || r.rx, fac ? { color:C.teal } : (/휠체어 접근/.test(r.rx) ? { color:C.ink, fontSize:9 } : { color:C.muted, bold:false })); };
  const rows = mixed ? [['위치', ...(noLx ? [] : [`고립 위험\n${BLDS()}`, '왕복 추가\n(중앙값)']), '시설', '고령자\n30초', '휠체어\n1분', '1억 원당', '처방']]
                     : [['위치', '고립 위험\n주거 건물', '시설 (자동 배치)', '고령자\n30초', '휠체어\n1분', '1억 원당', '처방']];
  const cw = mixed ? (noLx ? [1.6, 1.85, 0.95, 0.95, 1.0, 2.45] : [1.35, 0.9, 0.85, 1.4, 0.8, 0.8, 0.85, 1.85]) : [1.5, 1.05, 1.9, 1.0, 1.0, 0.75, 1.6];
  CANDT.forEach(r => {
    const site = r.kind !== '후보';
    const o = site ? { color:C.muted } : {};
    const loc = B(site ? `선정지 · ${r.name.split(' ')[0]}` : `${r.name.replace('후보', '후보 ')} · ${r.loc.split(' ').pop()}`, o);
    const p_ = per(r); Object.assign(p_.options, o);
    if (mixed) {
      const eff = r.memo ? [{ text:`약국 ${unit(r.benefit)}` + (r.alt && r.alt.any ? ` · 역 ${r.alt.any}` : ''), options:{ colspan:2, fontSize:9, color:C.ink } }]   // [10/20] 봉천 = 현장 메모 (둘 중 하나 수혜)
                         : [{ text:unit(r.elder30), options:o }, { text:unit(r.wheel), options:o }];
      rows.push([loc, ...(noLx ? [] : [{ text:unit(r.n_risk), options:o }, { text:mins(r.addmed), options:o }]), { text:r.fac, options:Object.assign({ fontSize:9 }, o) }, ...eff, p_, rxc(r)]);
    } else
      rows.push([loc, { text:unit(r.n_risk), options:o }, { text:r.fac, options:Object.assign({ fontSize:9.5 }, o) }, { text:unit(r.elder30), options:o },
                 { text:unit(r.wheel) + (r.alt ? ` (${r.alt.tgt} 기준 ${r.alt.wheel})` : ''), options:Object.assign(r.alt ? { fontSize:9.5 } : {}, o) }, p_, rxc(r)]);   // [10/14 v11] 봉천: 19장과 같은 기준을 옆에
  });
  const memoRow = CANDT.some(r => r.memo);
  // [10/21] 표 위: 후보 고르는 순서 (24장 '후보 고르는 기준' 칸과 같은 순서)
  // [C안] 과정 네 단계는 18장에 따로
  if (mixed) T(s, memoRow ? '시설 효과(고령자·휠체어·1억 원당)는 후보 = 공개 자료 보행망 시뮬레이션 · 봉천 = LX 현장 메모'
                          : '시설 효과는 봉천·후보 모두 공개 자료 보행망으로 같은 방식으로 계산',   // [10/20] 한 출처 안에서만 비교
               { x:0.6, y:1.36, w:8.8, h:0.22, fontSize:9, bold:true, color:C.ink });
  rows[0] = rows[0].map(t => typeof t === 'string' ? { text:t, options:{ fontSize:9 } } : t);   // [B안] 머리 글자 9
  etable(s, rows, { y: mixed ? 1.64 : 1.55, colW:cw, rowH:[0.36].concat(CANDT.map(() => 0.255)), fontSize:9 });   // [10/14 v14] 맑은 고딕(줄 높이 큼)에서도 막대와 띄움   // [10/21] 순서 줄만큼 내림
  const lxb = mixed && !memoRow && hasR('V6.17.lx_bong');   // [10/20] 각주 (LX 봉천) 자리
  // [10/21] 표 아래 한 줄: LX 반출로 본 고립 위험 = 후보 1·2(은천동)가 크고 3~5 는 작음. 반출 값이 이 문장과 맞을 때만 (안 맞으면 빌드 멈춤)
  const lx17 = (() => { if (!(REAL && mixed && !noLx && hasR('V6.17.lx_ranks'))) return false;
    const nr = r => Number(r.n_risk) || 0, cs = CANDT.filter(r => r.kind === '후보'), t2 = cs.filter(r => ['후보1', '후보2'].includes(r.name)), rest = cs.filter(r => !t2.includes(r));
    const ok = t2.length === 2 && t2.every(r => /은천/.test(r.loc)) && rest.every(r => nr(r) < 0.1 * Math.min(...t2.map(nr)));
    if (!ok) { console.error('!! 17장 "후보 1·2(은천동)" 한 줄이 반출 값과 맞지 않음 — 문장을 고칠 것'); process.exitCode = 1; }
    return ok; })();
  const yb17 = 4.04;   // [C안] 표 아래 막대 = 남길 두 문장만 (처방 규칙은 각주로)
  bar(s, 0.6, yb17, 0.48);
  T(s, [...(lx17 ? [{ text:'LX 자료로 다시 보면 고립 위험이 큰 곳은 후보 1·2(은천동)이고, 후보 3~5는 시설보다 작은 정비가 맞을 수 있습니다.', options:{ color:C.accD, bold:true, breakLine:true } }] : []),
        { text: (mixed && !memoRow) ? '이 표는 서울시 선정(봉천)을 뒤집자는 것이 아니라, 같은 예산의 비교 근거를 더합니다. 봉천의 시설 효과는 19장(LX 자료)에서 봅니다.'
              : hasR('V6.20.memo') ? '서울시 선정지(봉천)는 휠체어가 약국 가는 길을 크게 줄여 주는 곳입니다. 이 표는 선정을 뒤집자는 것이 아니라, 같은 예산의 비교 근거를 더합니다.'
                                   : '서울시 선정지(봉천)는 역까지 가는 휠체어 접근 효과가 큰 곳입니다. 이 표는 선정을 뒤집자는 것이 아니라, 같은 예산의 비교 근거를 더합니다.', options:{ color:C.ink, bold:true } }],
    { x:0.82, y:yb17, w:8.6, h:0.48, fontSize:9.5, valign:'middle', lineSpacingMultiple:1.05 });
  const rule17 = '처방 규칙: ' + Q('V6.17.cand_rule', '500m 안 기존 시설 → 기존 시설 연계 / 높이 차 3m 이하 → 바로 정비 (경사로) / 엘리베이터 1억 원당 수혜 건물 5개 이상 → 큰 시설 검토 / 미만 → 정비 + 방문돌봄 (엘리베이터 1곳 40억 원)');
  const src17 = (REH ? '공개 대역(리허설) 값 · ' : '') + (mixed
      ? '후보 = 공개 자료로 미리 고른 구간' + (noLx ? '' : ` · 부담 = ${LXS} (10/19 반출 ${V('V6.17.lx_burden')})`) + ` · 효과 = ${PUBS}` + (memoRow ? ` · 봉천 = ${LXS} (10/20 메모)` : '') + ' · 1억 원당 = 수혜 ÷ 40억'
      : (hasR('V6.v62') ? '후보 = 공개 자료로 미리 고른 구간을 안심구역 자료로 계산'   // [10/20] v17 검수
                        : '후보 = 고립 위험 주거 건물이 가장 많은 250m 격자에서 그 건물들의 길이 가장 많이 지나는 가파른 구간에 자동 배치')
        + ' · 수혜(의료) = 고령자 왕복 30초·휠체어 1분 이상 단축(새로 도달 포함) · 1억 원당 = 수혜 ÷ 40억 (엘리베이터만) · 시설 양 끝 좌표는 반출하지 않음');   // [10/14 v14] 두 줄 안에
  const rz17 = has('V6.16.rise_pub') ? ` 봉천 계단에서 공개 지형은 높이 차를 ${R.fields['V6.16.rise_pub'].value}, LX DEM 은 ${R.fields['V6.16.rise_lx'].value} 로 잡아 시설 효과가 크게 달랐음 (16장). 후보의 LX 기준 효과도 다를 수 있음` : '';   // [10/20]
  // [10/21] 각주: 후보 번호 = 공개 자료 기준 고립 위험 순서 (공개 리허설 v6.3 후보 자동), LX 기준 순위 = 반출 격자 순위 (22일 반출로 채움, 대비책 판은 앞 문장만)
  const fn17 = mixed ? [rule17, lxb ? `※ ${R.fields['V6.17.lx_bong'].value}.${rz17}` : '',
                        '※ 후보 번호는 공개 자료 기준 고립 위험 순서.' + (noLx ? '' : ` LX 기준 순위: ${V('V6.17.lx_ranks')}`)].filter(Boolean) : [];
  if (fn17.length) T(s, fn17.join('\n') + '\n' + src17,
             { x:0.6, y:4.58, w:8.25, h:0.97, fontSize:8, color:C.muted, valign:'bottom', lineSpacingMultiple:1.0 });   // [B안] 처방 규칙 + 각주 + 출처   // [10/20] 각주 + 출처 (다섯 줄까지)
  else src(s, src17);
} else { const s = base('정책 제안' + SFX(), () => FALLBACK ? '어디부터 무엇을: 우선 검토 후보' : `어디부터 무엇을: 우선 검토 후보 ${NCAND()}곳`);
  // 10/12: 열 = 위치, 고립 위험 건물 수, 왕복 추가 시간 중앙값, 500m 안 기존 시설, 처방 방향 (규칙). 1억 원당 수혜는 19장(시뮬레이션한 시설)만
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
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + '후보 = 250m 격자 · 시설 효과는 실제로 시뮬레이션한 선정지(19장)에서만 계산'); }

// ── 19 활용 ① 시설 입지 ──
{ const s = base('어디에 쓰나', '이동편의시설, 후보 발굴부터 예산 효과까지 한 번에 비교합니다', { tsize:20 });   // [10/13 v9]
  const sc19 = (sc => /^[가-힣]{1,3}구$/.test(sc) ? sc.slice(0, -1) : sc)(Q('V6.scope', '관악구'));
  [['후보 발굴', (CANDT ? `계단 기준 밖까지 넓혀 부담이 큰 곳을 찾습니다. ${CANDT.some(r => r.src) ? '공개 자료로 미리 고른' : '자동으로 찾은'} 후보 ${CANDT.filter(r => r.kind === '후보').length}곳 중 ${V('V6.17.n_facility')}이 앞섭니다.`   // [10/14 v14]
                          : `계단 기준 밖까지 넓혀 부담이 큰 곳을 찾습니다. ${sc19}에서는 ${NCAND()}곳입니다.`)],['설치 여지','주변 필지에 도로·공원이 얼마나 있는지로 놓을 자리부터 봅니다.'],['효과 비교',`시설 하나로 ${BLDS()} 몇 개가, 몇 분씩 편해지는지 계산합니다.`],['예산 검토','1억 원당 혜택 보는 건물 수로 순서를 정합니다.']].forEach((t, i) => {
    const y = 1.45 + i*0.78; if (i) hr(s, 0.6, y-0.07, 4.7);
    T(s, String(i+1), { x:0.6, y, w:0.4, h:0.62, fontSize:20, bold:true, color:C.ink, valign:'middle' });
    T(s, t[0], { x:1.05, y, w:1.25, h:0.62, fontSize:13, bold:true, color:C.ink, valign:'middle' });
    T(s, t[1], { x:2.3, y, w:3.0, h:0.62, fontSize:11.5, color:C.text, valign:'middle' }); });
  const iso = IMG('V6.iso');
  if (iso && /iso_one/.test(iso)) {   // [10/14 v11] 봉천 하나만 크게: 제목은 글자로, 그림은 칸을 꽉 채움
    T(s, '봉천 선정지에서 10분 안에 닿는 범위 (★ 시설)' + (hasR('V6.iso_src') ? ' · 공개 보행망' : ''), { x:5.5, y:1.38, w:3.95, h:0.28, fontSize:10, bold:true, color:C.ink });   // [10/20] 글자 8% 키워도 한 줄
    s.addImage({ path:iso, x:5.5, y:1.7, w:3.95, h:2.8, sizing:{ type:'contain', w:3.95, h:2.8 } }); }
  else if (iso) s.addImage({ path:iso, x:5.6, y:1.42, w:3.85, h:3.05, sizing:{ type:'contain', w:3.85, h:3.05 } });
  else slot(s, 5.6, 1.42, 3.85, 3.05, '등시선 그림 자리\n선정지에서 10분 안에 걸어 닿는 범위\n평지 가정 vs 경사 반영 vs 휠체어', 'V6.iso');
  takeaway(s, '"민원이 많은 곳"이 아니라 "효과가 큰 곳"부터 설치할 근거를 줍니다.', 4.62);
  src(s, '비용 가정: 엘리베이터 1곳 약 40억 원 (서울시 5곳 200억 원, 무악동 1곳 40억 원), 높이 차 3m 이하는 경사로로 바로 정비 (부록 2)' + (iso ? ` / 등시선: ${Q('V6.iso_src', '12_isochrone 결과')}` : '') + (hasR('V6.19.basemap') ? ` · 배경지도: ${R.fields['V6.19.basemap'].value}` : '')); }   // [10/20]

// ── 20 한 사람에게 돌아가는 변화 ──
if (Q('V6.20.mode', 'example') === 'wheel') {
  const s = base('관악구에서 찾은 것', () => FALLBACK ? `엘리베이터 한 대가 높이 ${V('V6.20.rise')} 계단 양 끝을 ${V('V6.20.after')}로 잇습니다`   // [10/20] 대비책 판: 설치 전 길(10/19 반출)을 뺌
    : `엘리베이터 한 대가 휠체어 길을 ${V('V6.20.before')}에서 ${V('V6.20.after')}로 줄입니다`, { tsize:19 });   // [10/13 v9]
  tag(s, 0.6, 1.42, BP ? '시설 시뮬레이션' : REH ? '리허설 시뮬레이션' : '모델 시뮬레이션', 1.55);
  const memo20 = hasR('V6.20.memo');   // [10/20] 현장 메모 (09 봉천, 약국 기준)
  T(s, FALLBACK ? '지금 (휠체어는 계단을 못 지남)' : '지금 (휠체어)', { x:0.6, y:1.85, w:3.6, h:0.3, fontSize:12.5, bold:true, color:C.muted });
  T(s, FALLBACK ? `높이 ${V('V6.20.rise')}` : V('V6.20.before'), { x:0.6, y:2.12, w:3.6, h:0.85, fontSize: FALLBACK ? 40 : 46, bold:true, color:C.acc });   // [10/20] 대비책 판: 설치 전 길 자리에 계단 높이
  T(s, FALLBACK ? '계단을 피해 비탈길로 우회\n서울시 발표: 200m 이상 우회' : `높이 ${V('V6.20.rise')} 계단을 피해 비탈길로 우회\n서울시 발표: 200m 이상 우회`, { x:0.6, y:2.98, w:3.6, h:0.6, fontSize:11.5, color:C.text, lineSpacingMultiple:1.12 });   // 높이 = DEM 5m
  T(s, '→', { x:4.3, y:2.2, w:0.8, h:0.8, fontSize:36, color:C.muted, align:'center', valign:'middle' });
  box(s, 5.25, 1.42, 4.2, 2.2, C.ink);
  T(s, '계단 아래·위를 잇는 수직 엘리베이터 1기', { x:5.5, y:1.55, w:3.8, h:0.3, fontSize:12, bold:true, color:C.white });
  T(s, V('V6.20.after'), { x:5.5, y:2.05, w:3.8, h:0.85, fontSize:46, bold:true, color:C.white });
  T(s, (FALLBACK ? '계단 양 끝 사이 길 · ' : '') + `엘리베이터 통과 약 ${V('V6.20.pass')} (대기 포함)`, { x:5.5, y:2.95, w:3.8, h:0.4, fontSize:12, color:C.onDark });
  if (memo20) {   // [10/20] 약국 기준 192개·1억 원당 4.8, 역 기준 34 괄호 (현장 메모)
    stat(s, 0.6, 3.82, 2.8, '고령자 30초·휠체어 1분 이상 단축 (약국)', `${V('V6.20.any')}` + (hasR('V6.20.any_st') ? ` (역 ${R.fields['V6.20.any_st'].value})` : ''), { size:17 });
    vr(s, 3.45, 3.85, 0.7);
    stat(s, 3.6, 3.82, 2.8, '휠체어 길이 준 건물 (약국' + (hasR('V6.20.wheelcut_med') ? `, 중앙값 −${R.fields['V6.20.wheelcut_med'].value})` : ')'), Q('V6.20.wheelcut', '-'), { size:17 });
    vr(s, 6.45, 3.85, 0.7);
    stat(s, 6.6, 3.82, 2.8, '1억 원당 수혜 건물 (약국)', V('V6.20.per100m'), { size:17 });
  } else {
  stat(s, 0.6, 3.82, 2.8, '휠체어 1분 이상 단축 건물', `${V('V6.20.wheel_n')} (${TG20()} 기준)`, { size:17 });
  vr(s, 3.45, 3.85, 0.7);
  stat(s, 3.6, 3.82, 2.8, '고령자 30초 이상 단축 건물', V('V6.20.elder30'), { size:17 });
  vr(s, 6.45, 3.85, 0.7);
  stat(s, 6.6, 3.82, 2.8, `1억 원당 수혜 건물 (${TG20()} 기준)`, V('V6.20.per100m'), { size:17 });   // [v6.3] 17장(병원·약국 기준)과 목적지가 다름을 밝힘
  }
  takeaway(s, memo20 ? '서울시 선정지는 휠체어가 약국 가는 길을 크게 줄여 주는 곳입니다. 선정 기준에 휠체어 우회 거리를 더하자고 제안합니다.'   // [10/20]
    : has('V6.20.before') && has('V6.20.after')   // [v6.3] 정책 발견: 선정지도 고령자 시간 단축은 작고 휠체어 접근 효과가 큼 → 선정 기준에 휠체어 우회 거리
    ? `짧은 계단 하나가 휠체어에게는 ${R.fields['V6.20.before'].value} 우회입니다. 같은 예산을 비교할 때 '휠체어 우회 거리'를 더하자고 제안합니다.`   // [10/13 v9] 첫 문장은 v9, 둘째는 v6.3 지시 (v9 의 '5개 구에서는 고령자 단축이 더해짐'은 계산 전이라 넣지 않음)
    : '짧은 계단 하나가 휠체어에게는 먼 길 우회입니다. 선정 기준에 \'휠체어 우회 거리\'를 넣자고 제안합니다.', memo20 ? 4.56 : 4.68);
  src(s, (REH ? '공개 대역(리허설) 값 · ' : '') + (memo20 ? (hasR('V6.lxexp') ? `${LXS} (반출: 설치 전 길·높이·통과·수혜, 높이는 DEM 5m) · ` : `${LXS} (${FALLBACK ? '높이·설치 후 길·통과·수혜' : '설치 전 길 = 10/19 반출, 높이·통과·수혜'} = 10/20 현장 메모, 높이는 DEM 5m) · `) : '') + '수혜 = 고령자 30초 이상 또는 휠체어 1분 이상 단축(새 도달 포함) · 1곳 40억 원 가정 · 위치는 서울시 사업대상지 위치도 기준'
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

setSec(4, '활용과 도입');

// ── 18 활용 개요 ──
{ const s = base('활용 방안', '언덕 부담 지도 하나로, 다섯 가지 행정 결정을 돕습니다');   // [10/20] 공공 입지 판단 도구: 행정 결정 다섯 가지 (길안내는 표 밖 한 줄)
  etable(s, [['결정','누가','무엇을 보고','결과물'],
    [B('핵심 · 이동편의시설 입지',{color:C.acc}),'서울시·자치구 균형발전·도시계획','부담 상위 지역 + 설치 여지 + 시설 효과','우선 후보지 (18·19장)'],
    [B('예산 우선순위'),'서울시·자치구 사업·예산','1억 원당 수혜, 처방 단계','같은 예산의 사업 순서 (17장)'],
    [B('돌봄 거점·방문 대상'),'자치구 복지·보건소','고립 위험 × 독거노인·장애인','방문 우선 동 (21장)'],
    [B('마을버스 정류장 입지'),'자치구 교통','정류장까지 부담이 큰 주거지','정류장 신설·이전 검토 (22장)'],
    [B('보행환경 정비 계획'),'자치구 도로·건설','부담 큰 경로 위 계단·급경사 + 사고다발지','계단·난간·쉼터 정비 순위 (22장)']],
    { colW:[2.1,1.95,2.45,2.3], rowH:[0.36,0.5,0.5,0.5,0.5,0.5] });
  T(s, '같은 지표는 길안내(서울동행맵·2024 수상작)에도 연계할 수 있습니다.', { x:0.6, y:4.55, w:8.8, h:0.32, fontSize:12, bold:true, color:C.ink });
  src(s, '2024 수상작 = 데이터안심구역 활용 공동 경진대회 최우수상 「보행약자를 위한 안전보행거리 검색 및 인공지능 기반 길안내 서비스」(과기정통부 보도자료, 2024.11.01 시상식)');
  }

// ── 21 활용 ② 방문돌봄 ──
{ const s = base('어디에 쓰나', '언덕 위 혼자 사는 어르신을 먼저 찾아갑니다', { tsize:22 });   // [10/13 v9]
  const q = [[0.6,1.45,'일반 돌봄','언덕 부담은 낮고 혼자 사는 분은 많은 동',false],[2.75,1.45,'최우선 방문','언덕 부담도 높고 혼자 사는 분도 많은 동',true],[0.6,2.95,'지켜보기','언덕 부담도 낮고 혼자 사는 분도 적은 동',false],[2.75,2.95,'이동 지원','언덕 부담은 높고 혼자 사는 분은 적은 동',false]];
  q.forEach(v => { if (v[4]) box(s, v[0], v[1], 2.1, 1.42, C.acc); else box(s, v[0], v[1], 2.1, 1.42, C.white, C.line);
    T(s, v[2], { x:v[0]+0.15, y:v[1]+0.15, w:1.85, h:0.38, fontSize:14, bold:true, color: v[4] ? C.white : C.ink });
    T(s, v[3], { x:v[0]+0.15, y:v[1]+0.6, w:1.85, h:0.7, fontSize:11.5, color: v[4] ? C.white : C.muted }); });
  T(s, '돌봄 수요(독거노인·장애인) ↑', { x:0.6, y:4.43, w:2.2, h:0.25, fontSize:10, color:C.muted });
  T(s, '언덕 부담(HBI) →', { x:2.75, y:4.43, w:2.1, h:0.25, fontSize:10, color:C.muted, align:'right' });
  const pub21 = has('V6.21.outing_diff');   // [10/13 판정 B5] 외출은 주장하지 않음: 부담 높은/낮은 동 두 묶음 비교 결과만 (SKT 가 있으면 SKT, 없으면 공개 생활인구 평일)
  const sk21 = (pub21 || (ALLM() && !hasR('V6.21.skt'))) ? '' : V('V6.21.skt'), kc21 = ((pub21 || ALLM()) && !has('V6.21.kcb')) ? '' : V('V6.21.kcb');   // [10/20] 실제판(상호제공 꺼짐)은 SKT·KCB 칸을 요청하지 않음   // 장에 안 쓰는 칸은 대체 목록에도 넣지 않음      // 10/12 청사진: 외출(SKT)·소득(KCB)을 한 칸에 (둘 다 같은 대체 문구면 하나만. 둘 다 ___ 면 빈칸 둘: 누락 key 가 둘)
  const rk21 = has('V6.21.risk_dongs') ? R.fields['V6.21.risk_dongs'].value + '곳' : '-';   // 선택 키 (고위험 동 = 값이 0 보다 큰 동 중 상위 25%)
  // [10/14 v11] 큰 숫자 = 최우선 방문 동 (주황 하나), 외출 결과는 아래 작은 글씨 한 줄
  // [10/14] v6.2 출력(또는 대비책 판)은 '격자 안 혼자 사는 어르신 추정'이 없음 → 그 칸을 빼고 두 칸으로 (간격 넓힘)
  const no21 = !hasR('V6.21.alone_cells') && (hasR('V6.v62') || FALLBACK || ALLM());   // [10/20] all 방식 실제판도 (격자 안 추정은 v6.3 에만)
  const st21 = FALLBACK ? [] : [has('V6.21.alone_top3_dongs') ? [`고립 위험 ${BLDS()}이 가장 많은 동`, R.fields['V6.21.alone_top3_dongs'].value, C.ink] : [`고립 위험(왕복 +${RMIN()}분) 건물이 많은 동`, rk21, C.ink],
   no21 ? null : ((has('V6.21.alone_cells') || !has('V6.21.alone_top3')) ? ['고립 위험 격자 안 혼자 사는 어르신 (추정)', V('V6.21.alone_cells'), C.ink] : ['고립 위험 상위 3개 동의 독거노인 수 (합, 공개 통계)', V('V6.21.alone_top3'), C.ink]),
   ['최우선 방문 동 (언덕 부담·혼자 사는 분 모두 많은 동)', V('V6.21.priority'), C.acc]].filter(x => x);
  const gap21 = st21.length === 3 ? 0.8 : 1.0;   // [10/14 v14] 간격 0.88 → 0.8
  st21.forEach((r, i) => { if (i) hr(s, 5.3, 1.45+i*gap21-0.07, 4.1); stat(s, 5.3, 1.45+i*gap21, 4.1, r[0], r[1], { size:18, laterInk:true, color:r[2] }); });
  if (FALLBACK) {   // [10/20] 대비책 판: 동 결과(10/19 반출)를 빼고 고르는 법만
    T(s, '최우선 방문 동을 고르는 법', { x:5.3, y:1.45, w:4.1, h:0.32, fontSize:13.5, bold:true, color:C.ink }); hr(s, 5.3, 1.82, 4.1, C.ink, 1.25);
    [[`동마다 고립 위험(왕복 +${RMIN()}분) 건물 비율`, `${LXS} (동 단위 집계)`], ['동마다 혼자 사는 어르신 수', '서울시 동별 독거노인 통계'], ['두 값이 모두 동 중앙값 이상인 동', '= 최우선 방문 동 (왼쪽 그림의 주황 칸)']].forEach(([a, b], i) => { const y = 1.95 + i * 0.62;
      T(s, String(i + 1), { x:5.3, y, w:0.3, h:0.5, fontSize:16, bold:true, color: i == 2 ? C.acc : C.ink, valign:'middle' });
      T(s, [{ text:a, options:{ bold:true, color:C.ink, breakLine:true } }, { text:b, options:{ color:C.muted } }], { x:5.65, y, w:3.75, h:0.5, fontSize:11, valign:'middle' }); });
  }
  const sm21 = [has('V6.21.priority_dongs') ? `최우선 방문 동: ${R.fields['V6.21.priority_dongs'].value}` : '',
                pub21 && has('V6.21.outing_note') ? `외출: ${R.fields['V6.21.outing_note'].value}` : (has('V6.21.skt') ? `외출(SKT)이 적은 고위험 동 ${sk21}` : ''),
                has('V6.21.kcb') ? `저소득(KCB) 겹침 ${kc21}` : ''].filter(x => x).slice(0, 2);   // [10/14 v14] 두 줄까지
  const ysm21 = 1.45 + st21.length * gap21 - 0.13;
  if (sm21.length) T(s, sm21.join('\n'), { x:5.3, y:ysm21, w:4.1, h:0.36, fontSize:8.5, color:C.muted, valign:'top' });
  if (has('V6.21.priority_rule')) T(s, R.fields['V6.21.priority_rule'].value, { x:0.6, y:4.8, w:8.8, h:0.24, fontSize:9, color:C.text });   // [10/14 v12] 장 아래 한 줄 (v14: 축 글자 아래로 올림)
  const yb21 = Math.max(ysm21 + 0.44, 3.9);   // 세 칸이면 4.16 (v14 그대로)
  bar(s, 5.3, yb21, 0.5); T(s, '보건소 방문건강관리, 돌봄SOS, 방문 약료의 대상 선정에 씁니다', { x:5.52, y:yb21, w:3.9, h:0.5, fontSize:11.5, bold:true, color:C.ink, valign:'middle' });
  src(s, (ALLM() ? `${LXS} (동 단위 고립 위험) + 공개 자료 · ` : '') + (has('V6.21.alone_cells') ? `혼자 사는 어르신 = 서울시 동별 독거노인 × 고립 위험 격자 안 주거 연면적 비율 (${Q('V6.21.alone_cells_n', '추정을 낸 동')}) / `
         : (has('V6.21.alone_top3_dongs') ? `고립 위험 상위 3개 동: ${R.fields['V6.21.alone_top3_dongs'].value} (독거노인: 서울시 동별 통계) / ` : '')) + (pub21 ? `${has('V6.21.kcb') ? '외출·소득은' : '외출은'} 동 단위 보조 지표 (상관 관찰) / ${R.fields['V6.21.outing_src'].value}`
                : (ALLM() ? '독거노인 = 서울시 동별 공개 통계' : '외출·소득은 동 단위 보조 지표 (상관 관찰) / SKT는 60세 이상 기준'))); }   // [10/20] 실제판은 SKT·KCB 를 쓰지 않음

// ── 22 활용 ③ 교통·보행 ──
{ const s = base('어디에 쓰나', '정류장과 계단, 어디부터 손볼지 정합니다', { tsize:22 });
  const pub22 = !has('V6.22.acc') && has('V6.22.acc_pub') && has('V6.22.acc_pub_txt');   // [10/13 판정 B6] 상호제공 교통사고가 없으면 '사고 통계가 놓치는 곳' (공개 보행노인 사고다발지, 최근 5년 대표)
  [[0.6,'마을버스 정류장','정류장까지 부담이 큰 주거지를 찾아 정류장 신설·이전 검토 지역으로 제시합니다.','정류장 검토 지역 (버스정류소 기준)',FALLBACK ? '' : V('V6.22.bus'),'도로 폭·회차 공간은 교통 부서가 함께 확인',C.ink],[5.3, pub22 ? '사고다발지가 놓치는 곳' : '보행로·계단 정비', pub22 ? R.fields['V6.22.acc_pub_txt'].value : '부담 큰 경로가 지나는 계단·급경사 구간에 난간·쉼터·미끄럼 방지·열선 순위를 매깁니다.',...(pub22 ? [`체감 부담 격자 (사고다발지 ${Q('V6.22.acc_pub_yr', '최근 5년')}, 반경 200m)`, V('V6.22.acc_pub'), R.fields['V6.22.acc_pub_src'].value] : ['사고가 겹치는 고부담 법정동',FALLBACK ? '' : V('V6.22.acc'),FALLBACK ? '' : '사고 자료: 도로교통공단 (법정동 단위)']),C.acc]].forEach(c => {   // [10/20] 대비책 판: 정류장·사고 칸(10/19 반출)을 뺌
    hr(s, c[0], 1.5, 4.1, c[6], 2);
    T(s, c[1], { x:c[0], y:1.62, w:4.1, h:0.36, fontSize:15, bold:true, color:c[6] });
    T(s, c[2], { x:c[0], y:2.05, w:4.1, h:0.75, fontSize:12, color:C.text, lineSpacingMultiple:1.12 });
    if (!FALLBACK) stat(s, c[0], 2.95, 4.1, c[3], c[4], { size: flat(c[4]).length > 10 ? 18 : 22, laterInk:true, color:C.ink });
    if (c[5]) T(s, c[5], { x:c[0], y: FALLBACK ? 2.95 : 3.75, w:4.1, h:0.6, fontSize:11, color:C.muted, valign:'top' }); });
  vr(s, 4.95, 1.5, FALLBACK ? 2.05 : 2.6);
  takeaway(s, '큰 공사 전에, 작은 개선으로 줄일 수 있는 부담부터 찾습니다.', FALLBACK ? 3.85 : 4.45);   // [10/20] 대비책 판: 숫자 칸을 뺀 만큼 올림
  const ft22 = pub22 && hasR('V6.22.acc_pub_foot') ? `※ ${R.fields['V6.22.acc_pub_foot'].value}` : '';   // [10/20] 문장은 짧게, 이유는 각주
  if (ALLM() && !FALLBACK) src(s, (ft22 ? ft22 + ' / ' : '') + `${LXS} (정류장 검토 지역 = 10/19 반출 격자) · 사고다발지 = 공개 자료 (도로교통공단 보행노인 사고다발지, 반경 200m)`);   // [10/20]
  else if (ft22) src(s, ft22); }

// ── 23 도시계획 연계 ── [10/20] 법정계획(교통약자법)과 서울시 고지대 사업 단계에 넣는 법. 법·계획 이름·주기는 법령·서울시 원문으로 확인한 것만
{ const s = base('도시계획 연계', '도시계획에 넣는 법');
  T(s, '① 법정계획에 넣기', { x:0.6, y:1.4, w:8.8, h:0.28, fontSize:12.5, bold:true, color:C.acc });
  etable(s, [['계획·조사','근거 (「교통약자의 이동편의 증진법」)','evenly 가 넣는 것'],
    [B('지방교통약자 이동편의 증진계획'),'제7조 · 시장 등이 5년 단위로 수립 (서울 제4차 2023~2027)','포함 사항 "보행환경 실태"·"지역적 특성"에 언덕 부담 지표'],
    [B('실태조사'),'제25조② · 지방계획 수립의 기초자료 (시기·방법은 조례)','보행환경 실태 항목에 언덕 부담·고립 위험 건물'],
    [B('연차별 시행계획'),'제8조 · 지방계획을 집행하는 해마다의 계획','우선 후보지와 예산 대비 효과']],
    { y:1.7, colW:[2.4,3.4,3.0], rowH:[0.32,0.46,0.42,0.42], fontSize:10 });
  T(s, [{ text:'② 서울시 고지대 이동편의 사업에서 쓰는 칸  ', options:{ bold:true, color:C.acc, fontSize:12.5 } }, { text:'단계는 서울시 발표 (2025.06), 설치 후 효과 점검은 evenly 제안', options:{ color:C.muted, fontSize:9.5 } }],
    { x:0.6, y:3.42, w:8.8, h:0.28 });
  [['후보 발굴','계단 기준 밖 급경사까지 후보 목록',1],['대상지 선정','같은 기준 비교, 1억 원당 수혜',1],['타당성 조사·기본계획','시설 1기 효과, 높이 차, 휠체어 우회',1],
   ['투자심사','예산 대비 수혜 근거',1],['착공·설치','현장 공사',0],['설치 후 효과 점검\n(evenly 제안)','같은 계산으로 설치 전후 비교',1]].forEach((c, i) => {
    const x = 0.6 + i*1.48, y = 3.74;
    box(s, x, y, 1.38, 0.92, c[2] ? C.soft : C.white, c[2] ? C.acc : C.line);
    T(s, c[0], { x:x+0.06, y:y+0.04, w:1.28, h:0.4, fontSize:10, bold:true, color: c[2] ? C.ink : C.muted, valign:'top' });
    T(s, c[1], { x:x+0.06, y:y+0.44, w:1.28, h:0.44, fontSize:9, color: c[2] ? C.accD : C.muted, valign:'top' }); });
  T(s, '주황 테두리 = evenly 가 쓰이는 칸', { x:0.6, y:4.7, w:4, h:0.22, fontSize:8.5, color:C.muted });
  src(s, '출처: 교통약자의 이동편의 증진법(법률 제20756호, 2026.02.01 시행) 제7·8·25조 / 서울특별시고시 제2023-543호(2023.12.14, 제4차 계획) / '
       + '서울시 균형발전정책과 보도(2025.06.16: 전수조사 후보 25곳·선정위원회·타당성 조사 및 기본계획 용역·투자심사·착공)'); }

// ── 24 화면 ──
// [10/20] 관악 결과로 돌아가는 화면: 지도 = prepare 의 V6.24.map (배경지도 + 반투명 격자는 반출 격자만, 반출 전·대비책 판은 격자 없이),
//   설치 효과 숫자 = 19장과 같은 키, 후보 목록 = 17장 표(V6.17.cand)의 후보 (LX 고립 위험 많은 순). "가상 수치" 없음 (숫자가 본문 값과 같음)
{ const s = base('evenly 화면', '담당자는 이렇게 씁니다', { tsize:24 });
  T(s, '동을 고르고, 후보를 보고, 시설을 놓아 보면 효과가 바로 나옵니다', { x:4.9, y:0.64, w:4.55, h:0.62, fontSize:12, color:C.muted, valign:'middle', align:'right' });
  const r_ = (t, o = {}) => ({ text:t, options:o });
  box(s, 0.6, 1.38, 8.8, 3.72, C.white, C.line);                                     // 화면 틀
  T(s, [r_('evenly', { bold:true, color:C.acc }), r_('   고지대 이동편의시설 후보 검토', { color:C.muted })], { x:0.75, y:1.45, w:3.6, h:0.28, fontSize:11, valign:'middle' });
  T(s, '지역', { x:4.35, y:1.47, w:0.4, h:0.24, fontSize:8.5, color:C.muted, valign:'middle', align:'right' });
  ['관악구', '광진구', '강서구', '종로구', '중구'].forEach((g, i) => { const x = 4.82 + i * 0.6, on = i === 0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:1.47, w:0.55, h:0.24, rectRadius:0.04, fill:{ color: on ? C.acc : C.soft }, line:{ color: on ? C.acc : C.line, width:0.5 } });
    T(s, g, { x, y:1.47, w:0.55, h:0.24, fontSize:8.5, bold:on, color: on ? C.white : 'A9AFAD', align:'center', valign:'middle' }); });
  T(s, '다음 단계', { x:7.85, y:1.47, w:0.75, h:0.24, fontSize:8, color:'A9AFAD', valign:'middle' });
  hr(s, 0.6, 1.8, 8.8);
  const m24 = IMG('V6.24.map');
  if (m24) s.addImage({ path:m24, x:0.72, y:1.9, w:5.0, h:2.62 });
  else slot(s, 0.72, 1.9, 5.0, 2.62, '화면 지도 자리\n관악구 250m 격자 · 배경지도', 'V6.24.map');
  if (hasR('V6.24.grid')) [[0, `평지 수준 (HBI ${HB()} 미만)`], [1, `체감 부담 (${HB()} 이상)`], [2, `고립 위험 (왕복 +${RMIN()}분)`]].forEach(([k, t], i) => { const x = 0.75 + i * 1.68;   // [10/21] 범례는 격자를 그렸을 때만 (반출 격자, 시험 판은 그 결과 격자)
    s.addShape(pres.shapes.RECTANGLE, { x, y:4.66, w:0.14, h:0.14, fill:{ color:['8CB8A0', 'F2B134', 'E4572E'][k], transparency:28 }, line:{ color:['8CB8A0', 'F2B134', 'E4572E'][k], transparency:28 } });
    T(s, t, { x:x + 0.19, y:4.6, w:1.48, h:0.26, fontSize:8.5, color:C.text, valign:'middle' }); });
  vr(s, 5.88, 1.92, 3.08);
  const X = 6.02, Wr = 3.28;
  T(s, '선택한 곳', { x:X, y:1.9, w:Wr, h:0.18, fontSize:8.5, color:C.muted });
  T(s, '봉천동 비안어린이공원 인근 계단', { x:X, y:2.06, w:Wr, h:0.26, fontSize:11.5, bold:true, color:C.ink });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x:X, y:2.36, w:Wr, h:0.3, rectRadius:0.06, fill:{ color:C.acc }, line:{ color:C.acc } });
  T(s, '수직 엘리베이터 놓아 보기  ▶', { x:X, y:2.36, w:Wr, h:0.3, fontSize:10.5, bold:true, color:C.white, align:'center', valign:'middle' });
  // [10/21] 설치 효과는 한 줄 세 칸 (기준 칸 자리를 만들려고), 숫자는 19장과 같은 키
  T(s, '설치하면', { x:X, y:2.72, w:Wr, h:0.18, fontSize:8.5, color:C.muted });
  const ew24 = [1.15, 1.13, 1.0];
  [FALLBACK ? ['설치 후 길', V('V6.20.after')] : ['휠체어 우회', `${V('V6.20.before')} → ${V('V6.20.after')}`],   // [10/20] 대비책 판: 설치 전 길(10/19 반출)을 뺌
   hasR('V6.20.memo') ? ['약국 수혜 건물', V('V6.20.any')] : [`휠체어 1분 단축 (${TG20()})`, V('V6.20.wheel_n')],   // 19장과 같은 갈래
   ['1억 원당 수혜', V('V6.20.per100m')]].forEach(([k, v], i) => { const x = X + ew24.slice(0, i).reduce((a, b) => a + b, 0);
    T(s, k, { x, y:2.9, w:ew24[i], h:0.16, fontSize:7.5, color:C.text });
    T(s, v, { x, y:3.05, w:ew24[i], h:0.26, fontSize:12, bold:true, color:C.acc }); });
  hr(s, X, 3.37, Wr);
  // [10/21] 후보 고르는 기준 (17장 표 위 한 줄과 같은 순서)
  box(s, X, 3.42, Wr, 0.62, C.soft);
  T(s, '후보 고르는 기준', { x:X + 0.08, y:3.44, w:Wr - 0.16, h:0.16, fontSize:8, bold:true, color:C.ink });
  T(s, [`① 고립 위험(왕복 +${RMIN()}분) 건물이 많은 250m 격자`, '② 그 안에서 경로가 가장 많이 지나는 가파른 구간', '③ 시설을 놓아 효과·1억 원당 비교 (17장)'].join('\n'),
    { x:X + 0.08, y:3.6, w:Wr - 0.16, h:0.42, fontSize:7.5, color:C.text });
  // [10/21] 후보 목록: 봉천 선정지 맨 위 고정, 후보는 LX 고립 위험 건물 많은 순 3곳 (prepare 의 V6.24.cands = 지도에 그린 3곳, 번호는 17장 후보 번호)
  //   줄마다 이름 · 고립 위험 건물 수(LX) · 처방 글자 (17장, 숫자 없이). 반출 전(미리 빌드)은 17장 순서 + 숫자 칸 빈칸, 대비책 판은 이름·처방만
  const cn24 = CANDT ? CANDT.filter(r => r.kind === '후보') : [];
  const nr24 = r => (r.n_risk === '' || r.n_risk === null || r.n_risk === undefined || isNaN(Number(r.n_risk))) ? null : Number(r.n_risk);
  const lx24 = cn24.some(r => nr24(r) !== null);
  const pk24 = hasR('V6.24.cands') ? String(R.fields['V6.24.cands'].value).split('|').map(n => cn24.find(r => r.name === n)).filter(Boolean)
             : (lx24 ? cn24.map((r, i) => [r, i]).sort((a, b) => ((nr24(b[0]) ?? -1) - (nr24(a[0]) ?? -1)) || (a[1] - b[1])).map(x => x[0]) : cn24).slice(0, 3);
  const c24 = CANDT ? [CANDT.find(r => r.kind !== '후보'), ...pk24].filter(Boolean) : [];
  T(s, FALLBACK ? '후보 목록' : '후보 목록 · 정렬: 고립 위험 건물 많은 순', { x:X, y:4.08, w:Wr, h:0.17, fontSize:8, color:C.muted });
  if (!c24.length) T(s, '-', { x:X, y:4.26, w:Wr, h:0.2, fontSize:10, color:C.muted });
  const u24 = v => (v === '' || v === null || v === undefined) ? '-' : (/^[0-9.,]+$/.test(String(v)) ? `${v}개` : String(v).replace('채', '개'));
  const rx24 = r => ({ '난간·쉼터·계단 정비 + 방문돌봄':'정비+방문돌봄', '정비 + 방문돌봄':'정비+방문돌봄' }[r.rx] || r.rx || '');
  c24.forEach((r, i) => { const y = 4.26 + i * 0.2, site = r.kind !== '후보';
    const nm = site ? `★ 선정지 · ${r.name.split(' ')[0]}` : `${r.name.replace('후보', '후보 ')} · ${r.loc.split(' ').pop()}`;
    T(s, nm, { x:X, y, w:1.15, h:0.2, fontSize:9, bold:true, color:C.ink, valign:'middle' });
    if (site) {   // 봉천 = LX 값 (메모 약국 192개, 메모 방식이 아니면 19장과 같은 휠체어 단축)
      T(s, hasR('V6.20.memo') ? `약국 ${V('V6.20.any')}` : `${TG20()} ${V('V6.20.wheel_n')}`, { x:X + 1.15, y, w:Wr - 1.15, h:0.2, fontSize:8.5, bold:true, color:C.acc, align:'right', valign:'middle' });
      return; }
    if (!FALLBACK) { T(s, `고립 위험 건물 ${lx24 ? u24(r.n_risk) : V('V6.17.lx_burden')}(LX)`, { x:X + 1.15, y, w:Wr - 1.15, h:0.2, fontSize:8, color:C.text, align:'right', valign:'middle' }); return; }   // 반출 전 = 빈칸   // [10/21] 처방 글자 뺌
    const big = /큰 시설 검토|바로 정비/.test(r.rx || '');
    T(s, rx24(r), { x:X + 2.48, y, w:0.8, h:0.2, fontSize:8, bold:big, color: big ? C.teal : C.muted, align:'right', valign:'middle' }); });
  src(s, '화면 예시(구상)' + (hasR('V6.24.basemap') ? ` · 배경지도: ${R.fields['V6.24.basemap'].value}` : '') + (FALLBACK ? ' · 봉천 시설 효과는 19장과 같은 값' : ' · 격자·고립 위험은 14장, 봉천 시설 효과는 19장과 같은 값')); }   // [10/21] 여기까지만

// ── 25 확산·한계 ──
{ const s = base('행정 도입 단계', '관악구 시범에서 서울시 사업과 법정계획으로 넓힙니다', { tsize:21 });   // [10/20]
  hr(s, 0.6, 1.62, 8.8, C.ink, 1.25);
  [hasR('V6.13.n_bld5') ? '관악구 시범 · 5개 구 분석' : '관악구 시범','자치구 후보 검토','서울시 사업 선정 기준 반영','교통약자 이동편의 증진계획 연계','전국 구릉지'].forEach((t, i) => { const x = 0.6 + i*1.78, hot = i==4;   // [10/20] 행정 도입 단계
    s.addShape(pres.shapes.RECTANGLE, { x, y:1.55, w:0.14, h:0.14, fill:{color: hot?C.acc:C.ink}, line:{color: hot?C.acc:C.ink} });
    T(s, String(i+1) + '단계', { x, y:1.8, w:1.6, h:0.25, fontSize:10.5, color:C.muted });
    T(s, t, { x, y:2.05, w:1.65, h:0.6, fontSize:12, bold:true, color: hot?C.acc:C.ink, valign:'top' }); });
  [['사업','후보 선정의 공통 기준, 예산 효과의 사전 근거'],['계획','증진계획의 보행환경 실태·지역 특성 자료 (23장)'],['확산','같은 LX 데이터로 부산 산복도로 등 전국 구릉지']].forEach((e, i) => { const x = 0.6 + i*2.97;
    bar(s, x, 2.75, 0.75, i==0 ? C.acc : C.ink); T(s, e[0], { x:x+0.22, y:2.75, w:2.6, h:0.3, fontSize:13, bold:true, color: i==0 ? C.acc : C.ink });
    T(s, e[1], { x:x+0.22, y:3.07, w:2.55, h:0.5, fontSize:11.5, color:C.text }); });
  // [B안] 운영 구조도: 계산은 플랫폼 안, 밖으로는 집계와 후보 목록, 건물 단위는 권한을 받은 자치구만
  T(s, '운영 구조', { x:0.6, y:3.66, w:3, h:0.26, fontSize:12, bold:true, color:C.ink });
  [['LX·서울시 데이터 플랫폼', '경사 보행망·HBI·시설 효과 계산 (안심구역)', C.ink, 'FFFFFF'], ['반출 (집계만)', '250m 격자·행정동 지표, 후보 목록 (건물 5개 미만 칸 제외)', C.soft, C.ink], ['서울시·자치구', '후보 검토 → 사업 선정 → 법정계획 (건물 단위는 권한을 받아 열람)', C.soft, C.ink]].forEach(([k, v, f, c], i) => { const x = 0.6 + i * 3.0;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y:3.98, w:2.65, h:1.0, rectRadius:0.08, fill:{ color:f }, line:{ color: f === C.ink ? f : C.line, width:1 } });
    T(s, k, { x:x + 0.15, y:4.04, w:2.4, h:0.3, fontSize:11.5, bold:true, color:c });
    T(s, v, { x:x + 0.15, y:4.34, w:2.4, h:0.6, fontSize:9.5, color: c === 'FFFFFF' ? 'E3EAF6' : C.text, lineSpacingMultiple:1.08 });
    if (i < 2) s.addShape(pres.shapes.LINE, { x:x + 2.68, y:4.48, w:0.29, h:0, line:{ color:C.teal, width:2, endArrowType:'triangle' } }); });
  src(s, '단계 2~4 는 서울시 사업 절차(23장)와 교통약자 이동편의 증진계획에 맞춘 제안 · 한계와 다음 단계는 26장'); }
// ── B26 기대효과 3칸 + 한계·다음 단계 (A안 25장 한계) ──
{ const s = base('기대효과', '숨은 부담을 드러내고, 같은 기준으로 고르고, 전국으로 넓힙니다', { tsize:20 });
  [['people', '사회', '숨은 부담을 드러냅니다', '평지 지도가 "가깝다"던 동네의 오르막 부담을 보이게 하고, 언덕 위 혼자 사는 어르신을 돌봄 대상으로 먼저 찾습니다.'],
   ['chart', '행정', '같은 기준으로 고릅니다', '입지 근거(같은 잣대 비교), 예산 효율(1억 원당 수혜), 교통약자 이동편의 증진계획과 연계합니다.'],
   ['grid', '기술', '어디서나 다시 씁니다', '건물 단위 경사 보행망, 서울시 공식 고저차와 맞춘 LX 자료 검증, 같은 LX 자료로 전국 구릉지에 넓힙니다.']].forEach(([ic, k, h, b], i) => { const x = 0.6 + i * 3.0, y = 1.45, dk = i === 1;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w:2.8, h:2.3, rectRadius:0.1, fill:{ color: dk ? C.ink : C.soft }, line:{ color: dk ? C.ink : C.soft } });
    icon(s, ic, x + 0.2, y + 0.2, 0.5, dk ? C.teal : C.ink);
    T(s, k, { x:x + 0.82, y:y + 0.2, w:1.8, h:0.5, fontSize:17, bold:true, color: dk ? 'FFFFFF' : C.ink, valign:'middle' });
    T(s, h, { x:x + 0.2, y:y + 0.85, w:2.45, h:0.35, fontSize:12.5, bold:true, color: dk ? 'FFFFFF' : C.ink });
    T(s, b, { x:x + 0.2, y:y + 1.22, w:2.45, h:1.0, fontSize:10.5, color: dk ? 'E3EAF6' : C.text, lineSpacingMultiple:1.12 }); });
  hr(s, 0.6, 3.92, 8.8);
  T(s, '한계와 다음 단계', { x:0.6, y:3.98, w:4, h:0.26, fontSize:11.5, bold:true, color:C.muted });
  const nx26 = [ALLM() ? '건축물대장 연결 개선(주거 기준)' : '', '사고·유동인구 원자료 결합', SPD() > 0.75 ? '현행 보행속도 0.7m/s 적용' : ''].filter(Boolean).join(', ');
  [['후보 발굴까지가 역할', '지반·규제·보상은 다음 단계 현장 타당성 조사로'], ['1:5,000 지도·외출 자료의 한계', '작은 골목 일부 누락 가능, 외출은 보조 관찰로만 사용']]
    .concat(ALLM() ? [['이번 결과는 모든 건물 기준', '건물 용도 연결률이 낮아 모든 건물을 출발점으로 계산']] : []).concat([['다음 단계', nx26]]).forEach((l, i) => { const y = 4.26 + i * 0.24;
    T(s, l[0], { x:0.6, y, w:2.6, h:0.24, fontSize:10, bold:true, color:C.ink, valign:'middle' }); T(s, l[1], { x:3.3, y, w:6.1, h:0.24, fontSize:10, color:C.text, valign:'middle' }); }); }
setSec(0, '부록');
{ const s = base('부록 1', '전처리와 경사 모델');
  // [10/20] 왼쪽 = 전처리 과정 그림 네 칸 (전 → 후, 공개 자료로 그린 실제 예: tools/make_process_figs.py → v6_source/proc28_1~4.png)
  const tn28 = (PFM.p28_tunnel && PFM.p28_tunnel.name) ? ` (예: ${PFM.p28_tunnel.name})` : '';
  [['교차점 분할', '겹쳐 지나가는 선을 교차점에서 잘라 노드(주황 원)를 만듭니다'],
   ['끊긴 끝점 10m 연결', '막다른 끝을 10m 안의 다른 길과 이어 줍니다 (주황 점선)'],
   ['계단', '계단 면 안 링크 = 계단(주황). 고령자 1.2배, 휠체어는 못 지남'],
   ['다리·터널 경사 0', `땅 높이(주황 점선) 대신 경사 0으로 계산 (초록)${tn28}`]].forEach((c, i) => {
    const x = 0.6 + (i % 2) * 2.3, y = 1.4 + Math.floor(i / 2) * 1.58;
    T(s, c[0], { x, y, w:1.5, h:0.22, fontSize:10.5, bold:true, color:C.ink });
    T(s, '전 → 후', { x:x+1.3, y, w:0.8, h:0.22, fontSize:8, color:C.muted, align:'right' });
    s.addImage({ path:img(`proc28_${i+1}.png`), x, y:y+0.25, w:2.1, h:0.92 });
    T(s, c[1], { x, y:y+1.19, w:2.1, h:0.34, fontSize:8.5, color:C.text, lineSpacingMultiple:1.05 }); });
  T(s, PFC ? '과정 예시: 공개 자료(연속수치지형도 등고선)로 그림 · 분석은 LX 자료 · 길 = 연속수치지형도 도로중심선, 계단·터널 = © OpenStreetMap contributors'
            : PFB ? '과정 예시: 길·등고선 = 연속수치지형도, 경사·격자 = 공개 지형 (분석은 LX 자료) · 계단·터널 = © OpenStreetMap contributors'
            : '과정 예시: 공개 자료로 그림 (분석은 LX 자료) · 길 = 국토지리정보원 연속수치지형도, 계단·터널 = © OpenStreetMap contributors, 높이 = 공개 지형 타일',
    { x:0.6, y:4.54, w:4.45, h:0.36, fontSize:8, color:C.muted, lineSpacingMultiple:1.05 });   // [10/20] 그림 바로 아래 출처
  const xs = [0,2,4,6,8,10,12,14,16,18,20], tob = sl => 6*Math.exp(-3.5*Math.abs(sl+0.05)), flatv = tob(0);
  s.addChart(pres.charts.LINE, [{ name:'오르막 소요시간 배수', labels:xs.map(x=>x+'%'), values:xs.map(x => +(flatv/tob(x/100)).toFixed(2)) }], { x:5.25, y:1.4, w:4.2, h:2.2, chartColors:[C.acc], lineSize:2.5, lineDataSymbol:'circle', lineDataSymbolSize:5, showTitle:true, title:'오르막 경사별 소요시간 배수', titleFontSize:11, titleColor:C.ink, titleFontFace:F, catAxisLabelColor:C.muted, valAxisLabelColor:C.muted, catAxisLabelFontSize:9, valAxisLabelFontSize:9, valGridLine:{ color:'E8EAE9', size:0.5 }, catGridLine:{ style:'none' }, showLegend:false, valAxisMinVal:1 });
  T(s, [{ text:'고령자 ', options:{ bold:true, color:C.ink } }, { text:`${SPD()}m/s × Tobler 배수, 내리막은 오르막 부담의 50%, 계단 최소 25%·1.2배`, options:{ breakLine:true } }, { text:'휠체어 ', options:{ bold:true, color:C.teal } }, { text:'1.0m/s, 1/12 초과는 10배(회피), 계단 통행 불가', options:{} }], { x:5.25, y:3.66, w:4.2, h:0.66, fontSize:10.5, color:C.text, valign:'top' });
  T(s, [{ text:'DEM 5M  ', options:{ bold:true, color:C.ink } }, { text:'EPSG:5186 통일, 링크 양 끝 고도로 경사, ±40% 넘으면 자름', options:{ color:C.text, breakLine:true } },
        { text:'건물·필지·대장  ', options:{ bold:true, color:C.acc } }, { text:'건물 중심점 → 필지 → 대장 주용도, 연결률 보고', options:{ color:C.text } }],
    { x:5.25, y:4.36, w:4.2, h:0.54, fontSize:8.5, lineSpacingMultiple:1.05 });   // [10/20] 왼쪽 그림 자리에서 옮김
  T(s, [{ text:'출처·대조군 (16장)  ', options:{ bold:true, color:C.ink } }, { text:(FALLBACK ? '' : `공개 대조군: 서울 도보 네트워크 + 30m 공개 지형 · 계단 빼면 휠체어 시간 과소 ${V('V6.16.stairs')} · `) + `어르신 속도: ${V('V6.16.speed_src')}`, options:{ color:C.muted } }],
    { x:0.6, y:4.92, w:8.8, h:0.3, fontSize:8.5 });   // [10/14 v11] 16장 출처를 여기로   // [10/20] 속도 숫자 겹침 줄임 (출처 글에 이미 있음)
  src(s, 'Tobler 보행함수 v = 6·exp(−3.5·|s+0.05|) km/h / 휠체어 경사 기준: 장애인·노인·임산부 등의 편의증진 보장에 관한 법률 시행규칙'); }
{ const s = base('부록 2', '가정을 바꿔도 결론이 유지되는가');
  const r = (a,b,c2,d) => [B(a), b, c2, d];
  const eq29 = Math.abs(420 / SPD() / 60 - Math.round(420 / SPD() / 60)) < 0.05 ? '=' : '≈';
  const sm29 = t => ({ text:t, options:{ fontSize:8 } });   // [10/14 v11] 문턱·대기·비용 줄은 문장으로
  const band29 = FALLBACK ? '' : (ALLM() && !hasR('V6.29.band_top3')) ? V('V6.29.band_top3') : has('V6.29.band_top3') ? [R.fields['V6.29.band_top3'].value, has('V6.29.band_counts') ? R.fields['V6.29.band_counts'].value : '', has('V6.29.band_fix') ? R.fields['V6.29.band_fix'].value : ''].filter(x => x).join('\n') : Q('V6.29.band_rho_short', '실제 결과 후');
  const rows29 = [['가정','값','근거','바꿨을 때 (숫자 = 순위상관)'], r('고령자 보행속도',`${SPD()}m/s`, SPD() === 0.7 ? '경찰청 매뉴얼 (2020.11.30 개정)' : '경찰청 매뉴얼 개정 전 (현행 0.7m/s)', SPD() === 0.7 ? { text:`개정 전 0.8·1.0m/s: ${V('V6.29.speed')}`, options:{ fontSize:9.5 } }
       : sm29(`1.0m/s: ${V('V6.29.speed')} · 현행 0.7m/s 이면 왕복 추가 시간 ×8/7, HBI 는 같음 (${ANAS})`)),   // [10/20] 0.8 로 통일
    r('내리막 부담','오르막의 50%','가정 (0%·100% 비교)',V('V6.29.down')), r('계단','최소 25% 경사, 1.2배','가정 (1.5배 비교)',V('V6.29.stair')), r('휠체어 경사 한계','1/12 (8.3%)','법정 경사로 기준','해당 없음 (법정)'),   // [10/20] 윗줄 주석에 묻혀 빠졌던 세 줄
    FALLBACK ? null : r(`고립 위험 문턱`,`왕복 +${RMIN()}분`,`420m ÷ ${SPD()}m/s ${eq29} 편도 ${Math.round(420 / SPD() / 60)}분`, sm29(band29)),   // [10/20] 대비책 판: 문턱별 결과(10/19 반출)가 없어 줄을 뺌
    r('엘리베이터 대기',`${Q('V6.29.facility_w', '30·60·90초')} 비교`,'서울시 발표 + 가정', sm29(V('V6.29.facility_txt'))),   // [10/21] 대기는 재지 않음
    r('시설 비용','엘리베이터\n곳당 약 40억 원', sm29('서울시 무장애길 1단계 5곳 200억 원\n2단계 10곳 400억 원'), sm29('높이 차 3m 이하는 경사로로 바로 정비,\n경사로 사업비는 공개 자료 없음')),   // [10/14 v14] 짧게
    r('반출 최소 건물 수','5개','비식별 기준','해당 없음')];
  const rh29 = [0.3,0.3,0.28,0.28,0.28,0.52,0.36,0.4,0.28];
  etable(s, rows29.filter(Boolean), { colW:[1.6,1.75,2.65,2.8], rowH:rh29.filter((_, i) => rows29[i]), fontSize:10 });   // [10/14 v14] 맑은 고딕에서도 장 안에
  src(s, (ALLM() ? `${LXS} (${hasR('V6.lxexp') ? '반출, 민감도는 5개 구' : `민감도·대기 = 10/20 현장 메모${FALLBACK ? '' : ', 문턱 = 10/19 반출'}`}) · 보행속도 환산 = ${ANAS} · ` : '') + '순위상관이 0.9 이상이면 "누가 더 취약한가"의 순서가 가정에 크게 흔들리지 않는다는 뜻'); }
{ const s = base('부록 3', '경사 비용 계산 (발췌)');
  const code = ['def tobler(s):                       # 경사 s → 보행속도 km/h','    return 6.0 * np.exp(-3.5 * np.abs(s + 0.05))','FLAT = tobler(0.0)','','def elder_time(length, s, stair):    # 고령자 링크 통과 시간(초)','    s = np.where(stair, np.sign(s + 1e-9) * np.maximum(np.abs(s), 0.25), s)','    up = FLAT / tobler(np.abs(s))','    down = 1 + C.DOWNHILL_WEIGHT * (up - 1)   # 내리막은 오르막 부담의 일부','    factor = np.where(s >= 0, FLAT / tobler(s), down)','    t = length / C.ELDER_SPEED * factor','    return np.where(stair, t * C.STAIR_FACTOR, t)','','def wheel_time(length, s, stair):    # 휠체어: 1/12 초과는 사실상 회피, 계단 불가','    up = np.maximum(s, 0)','    t = length / (C.WHEEL_SPEED * np.maximum(0.4, 1 - 5 * up))','    t = np.where(np.abs(s) > C.WHEEL_LIMIT, t * C.WHEEL_STEEP_PENALTY, t)','    return np.where(stair, np.inf, t)'].join('\n');
  box(s, 0.6, 1.4, 8.8, 3.7, C.soft);
  T(s, code, { x:0.8, y:1.5, w:8.5, h:3.5, fontFace:'Consolas', fontSize:10.5, color:C.text });
  src(s, 'analysis/hbi/lib/model.py 발췌 / 실행 환경: QGIS 3.32 내장 Python, numpy·GDAL, 자체 다익스트라, 자동 점검(setup·check)'); }

// ── B30 질의응답 · 감사합니다 (A안 26장 마감 문장) ──
{ const s = pres.addSlide(); page++; s.background = { color:NAVY };
  s.addImage({ path:img('contour_dark.png'), x:0, y:0, w:10, h:5.625, transparency:62 });
  s.addShape(pres.shapes.RECTANGLE, { x:0, y:0, w:0.22, h:5.625, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, '질의응답', { x:0.8, y:0.95, w:8.4, h:0.85, fontSize:40, bold:true, color:'FFFFFF' });
  T(s, '감사합니다', { x:0.8, y:1.8, w:8.4, h:0.55, fontSize:22, color:C.onDark });
  s.addShape(pres.shapes.RECTANGLE, { x:0.8, y:2.62, w:1.0, h:0.05, fill:{ color:C.teal }, line:{ color:C.teal } });
  T(s, '어디에 살든,', { x:0.8, y:2.85, w:8.4, h:0.5, fontSize:22, color:'FFFFFF' });
  T(s, '7분은 7분이어야 합니다.', { x:0.8, y:3.35, w:8.4, h:0.7, fontSize:32, bold:true, color:C.acc });
  T(s, [{ text:'evenly', options:{ bold:true, color:'FFFFFF', fontSize:22 } }, { text:'   정책 도구 · even = 평평한 + 공평한', options:{ color:C.onDark, fontSize:13 } }], { x:0.8, y:4.15, w:8.4, h:0.45 });
  T(s, `${team()}   |   언덕 위 우리동네 · 경사 반영 이동편의시설 입지 지도   |   한국국토정보공사 데이터 활용`, { x:0.8, y:4.85, w:8.6, h:0.3, fontSize:11, color:C.onDark });
  SLIDES[page] = s; }

// ── 저장 + 누락 목록 ────────────────────────────────────────
if (BP) { banScan(BP_NOTE); for (const p_ of TOUCH) if (SLIDES[p_]) SLIDES[p_].addNotes(BP_NOTE); }   // [10/13] 청사진 판: 결과 장 발표자 노트 (쓰지 않는 말 검사)
if (pending.length) { console.error('!! 빈칸으로 그려지지 않은 누락 key: ' + pending.map(p => p.page + '장 ' + p.key).join(', ')); process.exitCode = 1; }
if (BANHIT.length) { console.error(`!! 쓰지 않는 말이 남음: ${[...new Set(BANHIT)].join(', ')} — 파일을 쓰지 않음`); process.exit(1); }   // [10/21]
if (FBHIT.size) {   // [10/20] 대비책 판에 "반영 예정" 표지가 남으면 파일을 쓰지 않음 (그 칸을 FALLBACK 갈래에서 빼야 함)
  console.error(`!! 대비책 판에 "${FB_TEXT}" 가 남은 장: ${[...FBHIT].join('·')} — ` + fallbacks.filter(m => m.used === FB_TEXT).map(m => m.page + '장 ' + m.key).join(', '));
  process.exit(1);
}
if (page !== 30) { console.error(`!! C안 슬라이드 ${page}장 — 30장이어야 함`); process.exit(1); }
const OUT = arg('--out') || '../deliverables/언덕위우리동네_기획서_final_C.pptx';   // [C안] A·B안 파일과 따로
const MISS = arg('--missing') || path.join('data', 'missing_final_c.txt');   // [C안]
const lines = [`# 기획서 v6 누락 목록 — source=${R.source}${R.src ? ', src=' + R.src : ''}, bands=${R.bands || 'hbi'}, ${new Date().toISOString().slice(0, 19)}`,
  `# 출력: ${OUT.replace('../', '')} (${page}장)`,
  ...missing.map(m => `누락: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}  [${m.key}]`),
  ...(fallbacks.length ? ['# 대체 (공개 대역 판에서 원래 채울 수 없는 칸·기본 문구로 바뀐 곳. 필수 빈칸이 아니라 check_deck N=M=K 에는 넣지 않음)',
    ...fallbacks.map(m => `대체: ${m.page}장, ${m.label}, ${m.need.join(' / ') || '-'}  [${m.key}] → "${String(m.used).replace(/\n/g, ' ').slice(0, 40)}"`)] : [])];
fs.mkdirSync(path.dirname(MISS), { recursive:true });
fs.writeFileSync(MISS, lines.join('\n') + '\n');
if (R.source === 'none') console.warn('!! data/results.json 없음 → 빈칸 판');
if (FAKE) console.warn('!! 가상 수치 — 모든 장 오른쪽 위에 "가상 수치 · 검토용"');
if (BP) console.warn(`!! 청사진 판 (공개 대역 리허설 값, 표시 없음) — 결과 장 노트 "${BP_NOTE}" · 보관·발전용, 제출하지 않음`);
else if (REH) console.warn('!! 공개 대역 — 모든 장 오른쪽 위에 "공개 대역 · 제출 금지"');
console.log(`슬라이드 ${page}장, 누락 ${missing.length}건, 대체 ${fallbacks.length}건 → ${MISS}`);
pres.writeFile({ fileName: OUT }).then(f => console.log('wrote', f));
