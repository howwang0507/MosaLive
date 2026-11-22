'use strict';
// Environment checks shown on the first-run screen. Each check says what is wrong and which
// setup step fixes it; nothing here installs or downloads anything.
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const P = require('./paths');
const { run } = require('./run');

const MIN_VRAM_MIB = 7500; // 8 GB cards report about 8188 MiB.

function parseGpus(text) {
  return String(text || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean).map(line => {
    const i = line.lastIndexOf(',');
    return { name: line.slice(0, i).trim(), memoryMiB: Number(line.slice(i + 1).trim()) };
  }).filter(g => g.name && Number.isFinite(g.memoryMiB));
}

function hasModel(tags, name) {
  const names = new Set((tags?.models || []).map(m => m.name));
  return names.has(name) || names.has(name + ':latest');
}

function findOnPath(name, env, exists = fs.existsSync) {
  const key = Object.keys(env).find(k => k.toUpperCase() === 'PATH');
  const dirs = String(key ? env[key] : '').split(path.delimiter).filter(Boolean);
  for (const dir of dirs) for (const ext of ['.exe', '.cmd', '']) {
    const file = path.join(dir, name + ext);
    if (exists(file)) return file;
  }
  return null;
}

function findExecutable(name, env, exists = fs.existsSync) {
  return findOnPath(name, env, exists) || P.knownExecutable(name, env).find(p => p && exists(p)) || null;
}

async function fetchJson(url, timeoutMs = 2500) {
  const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!response.ok) throw new Error('HTTP ' + response.status);
  return response.json();
}

// ctx: { root, data, packaged, env, home, platform }
async function runChecks(ctx, deps = {}) {
  const exists = deps.exists || fs.existsSync;
  const runCmd = deps.run || run;
  const getJson = deps.fetchJson || fetchJson;
  const env = ctx.env, results = [];
  const add = (id, label, ok, detail, fix = null, level = ok ? 'ok' : 'error') => results.push({ id, label, ok, level, detail, fix });

  const windows = ctx.platform === 'win32';
  add('os', 'Windows 10／11（64 位元）', windows && (ctx.arch || 'x64') === 'x64',
    windows ? 'Windows ' + (ctx.release || os.release()) : '目前不是 Windows，只能測試介面');

  const smi = findExecutable('nvidia-smi', env, exists) || (windows ? 'nvidia-smi' : null);
  let gpus = [];
  if (smi) {
    const r = await runCmd(smi, ['--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], { timeoutMs: 8000 });
    if (r.code === 0) gpus = parseGpus(r.output);
  }
  const best = gpus.sort((a, b) => b.memoryMiB - a.memoryMiB)[0];
  if (!best) add('gpu', 'NVIDIA 顯示卡', false, '找不到 NVIDIA 顯示卡或驅動程式（nvidia-smi）', 'gpu-driver');
  else add('gpu', 'NVIDIA 顯示卡', best.memoryMiB >= MIN_VRAM_MIB,
    `${best.name}，${(best.memoryMiB / 1024).toFixed(1)} GB` + (best.memoryMiB >= MIN_VRAM_MIB ? '' : '；建議 8 GB 以上，可能跑不動預設模型'),
    null, best.memoryMiB >= MIN_VRAM_MIB ? 'ok' : 'warn');

  const python = P.findPython(ctx, exists);
  const pyLauncher = findExecutable('py', env, exists) || P.knownExecutable('python311', env).find(p => exists(p));
  if (python) add('python-env', 'Python 執行環境', true, python);
  else add('python-env', 'Python 執行環境', false,
    pyLauncher ? '尚未建立，按「安裝」建立（需下載約數 GB 套件）' : '需要先安裝 Python 3.11', pyLauncher ? 'create-env' : 'install-python');

  if (python) {
    const dirs = P.cudaWheelDirs(python);
    const wheels = dirs.every(d => exists(d));
    const system = Boolean(findOnPath('cublas64_12.dll', env, exists) && findOnPath('cudnn64_9.dll', env, exists));
    add('cuda', 'GPU 語音辨識元件（CUDA）', wheels || system,
      wheels ? '已安裝在 Python 環境中' : system ? '使用系統安裝的 CUDA' : '缺少 cuBLAS／cuDNN，語音辨識無法用 GPU', wheels || system ? null : 'cuda-wheels');
  }

  const ollama = findExecutable('ollama', env, exists);
  let tags = null;
  try { tags = await getJson('http://127.0.0.1:11434/api/tags'); } catch {}
  if (!ollama && !tags) add('ollama', 'Ollama（翻譯引擎）', false, '尚未安裝', 'install-ollama');
  else add('ollama', 'Ollama（翻譯引擎）', true, tags ? '執行中' : '已安裝，啟動字幕服務時會自動開啟');

  if (tags) add('translation-model', '翻譯模型 ' + P.TRANSLATION_MODEL, hasModel(tags, P.TRANSLATION_MODEL),
    hasModel(tags, P.TRANSLATION_MODEL) ? '已下載' : '尚未下載（約 3.3 GB）', hasModel(tags, P.TRANSLATION_MODEL) ? null : 'pull-translation');
  else if (ollama) add('translation-model', '翻譯模型 ' + P.TRANSLATION_MODEL, false, 'Ollama 尚未執行，無法確認', 'pull-translation', 'warn');

  const asr = P.findAsrModel({ root: ctx.root, env, home: ctx.home }, deps.fs || fs);
  add('asr-model', '語音辨識模型 large-v3-turbo', Boolean(asr),
    asr ? '已下載' : '尚未下載（約 1.6 GB）；沒有時會改用較不準的 small', asr ? null : 'download-asr', asr ? 'ok' : 'warn');

  return { results, python, ollama, tags, gpus, ready: results.every(r => r.level !== 'error') };
}

module.exports = { runChecks, parseGpus, hasModel, findOnPath, findExecutable, fetchJson, MIN_VRAM_MIB };
