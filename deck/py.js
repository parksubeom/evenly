// deck/py.js ─ 기획서 빌드에 쓸 Python 을 골라 실행 (그림에 matplotlib 이 필요해서)
//   고르는 순서: (1) 환경변수 EVENLY_PY  (2) 이 맥의 QGIS 내장 Python (/Applications/QGIS*.app, matplotlib 포함)  (3) 시스템 python3
//   사용: node py.js ../tools/prepare_deck_data.py --src ...   (npm 스크립트가 부름)
//   QGIS Python 은 그냥 실행하면 라이브러리를 못 찾으므로 PYTHONHOME·PYTHONPATH·GDAL_DATA·PROJ_DATA 를 붙여 실행합니다.
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function qgisPython() {
  let apps = [];
  try { apps = fs.readdirSync('/Applications').filter(n => /^QGIS.*\.app$/.test(n)).sort().reverse(); } catch (e) { return null; }
  for (const app of apps) {
    const c = path.join('/Applications', app, 'Contents');
    let bins = [];
    try { bins = fs.readdirSync(path.join(c, 'MacOS')).filter(n => /^python3\.\d+$/.test(n)); } catch (e) { continue; }
    if (!bins.length) continue;
    const exe = path.join(c, 'MacOS', bins[0]);
    const r = path.join(c, 'Resources');
    const lib = path.join(r, bins[0]);
    return {
      exe, label: `QGIS Python (${exe})`,
      env: { PYTHONHOME: r, PYTHONPATH: [lib, path.join(lib, 'lib-dynload'), path.join(lib, 'site-packages')].join(':'),
             GDAL_DATA: path.join(r, 'qgis', 'gdal'), PROJ_DATA: path.join(r, 'qgis', 'proj') },
    };
  }
  return null;
}

function pick() {
  if (process.env.EVENLY_PY) return { exe: process.env.EVENLY_PY, label: `EVENLY_PY (${process.env.EVENLY_PY})`, env: {} };
  return qgisPython() || { exe: 'python3', label: '시스템 python3', env: {} };
}

const py = pick();
console.error(`[py.js] 파이썬: ${py.label}`);
const res = spawnSync(py.exe, process.argv.slice(2), { stdio: 'inherit', env: Object.assign({}, process.env, py.env) });
if (res.error) { console.error(`[py.js] 실행 실패: ${res.error.message}`); process.exit(1); }
process.exit(res.status === null ? 1 : res.status);
