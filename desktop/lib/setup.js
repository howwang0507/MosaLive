'use strict';
// Install steps. Each one runs only after the user presses its button (downloads are large).
const path = require('node:path');
const fs = require('node:fs');
const P = require('./paths');
const { run } = require('./run');
const { findExecutable, fetchJson } = require('./checks');

const STEPS = {
  'install-python': { label: '安裝 Python 3.11', size: '約 30 MB', winget: 'Python.Python.3.11', url: 'https://www.python.org/downloads/windows/' },
  'install-ollama': { label: '安裝 Ollama', size: '約 1 GB', winget: 'Ollama.Ollama', url: 'https://ollama.com/download/windows' },
  'create-env': { label: '建立 Python 環境並安裝套件', size: '約 3–4 GB（含 GPU 元件）' },
  'cuda-wheels': { label: '安裝 GPU 語音辨識元件', size: '約 1–2 GB' },
  'pull-translation': { label: '下載翻譯模型 ' + P.TRANSLATION_MODEL, size: '約 3.3 GB' },
  'download-asr': { label: '下載語音辨識模型 large-v3-turbo', size: '約 1.6 GB' },
  'gpu-driver': { label: '安裝 NVIDIA 驅動程式', size: '', url: 'https://www.nvidia.com/Download/index.aspx' },
};
// The order the "install everything missing" button follows.
const ORDER = ['install-python', 'install-ollama', 'create-env', 'cuda-wheels', 'pull-translation', 'download-asr'];

function planFor(checkResults) {
  const wanted = new Set(checkResults.filter(r => r.fix && r.level !== 'ok').map(r => r.fix));
  if (wanted.has('install-python')) wanted.add('create-env');
  if (wanted.has('create-env')) wanted.delete('cuda-wheels'); // create-env installs them too.
  if (wanted.has('install-ollama')) wanted.add('pull-translation');
  return ORDER.filter(id => wanted.has(id));
}

async function ensureOllamaRunning(env, log, deps = {}) {
  const getJson = deps.fetchJson || fetchJson;
  try { await getJson('http://127.0.0.1:11434/api/tags'); return true; } catch {}
  const exe = findExecutable('ollama', env);
  if (!exe) throw new Error('找不到 Ollama，請先安裝');
  log('啟動 Ollama…');
  const { spawn } = require('node:child_process');
  // Same low-VRAM settings windows/launch.py uses when it starts Ollama itself.
  const speed = { OLLAMA_FLASH_ATTENTION: '1', OLLAMA_KV_CACHE_TYPE: 'q8_0', OLLAMA_NUM_PARALLEL: '1', OLLAMA_MAX_LOADED_MODELS: '1' };
  const child = spawn(exe, ['serve'], { env: { ...speed, ...env }, detached: true, stdio: 'ignore', windowsHide: true });
  child.unref();
  for (let i = 0; i < 20; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try { await getJson('http://127.0.0.1:11434/api/tags'); return true; } catch {}
  }
  throw new Error('Ollama 沒有在 20 秒內啟動');
}

// ctx: { root, data, packaged, env, openExternal }
async function runStep(id, ctx, log, deps = {}) {
  const runCmd = deps.run || run;
  const step = STEPS[id];
  if (!step) throw new Error('未知的安裝步驟：' + id);
  const env = ctx.env;
  const must = async (cmd, args, options = {}) => {
    log('> ' + [path.basename(cmd), ...args].join(' '));
    const r = await runCmd(cmd, args, { env, onLine: log, ...options });
    if (r.code !== 0) throw new Error(`${step.label}失敗（代碼 ${r.code}）。請看下方紀錄。`);
    return r;
  };

  if (step.winget) {
    const winget = findExecutable('winget', env);
    if (!winget) { ctx.openExternal(step.url); throw new Error('這台電腦沒有 winget，已開啟官方下載頁，請手動安裝後按「重新檢查」'); }
    await must(winget, ['install', '-e', '--id', step.winget, '--silent', '--accept-package-agreements', '--accept-source-agreements']);
    return;
  }
  if (id === 'gpu-driver') { ctx.openExternal(step.url); return; }

  if (id === 'create-env' || id === 'cuda-wheels') {
    const dir = P.envDir(ctx);
    let python = P.findPython(ctx);
    if (id === 'create-env' && !python) {
      const py = findExecutable('py', env);
      const direct = P.knownExecutable('python311', env).find(p => fs.existsSync(p));
      if (py) await must(py, ['-3.11', '-m', 'venv', dir]);
      else if (direct) await must(direct, ['-m', 'venv', dir]);
      else throw new Error('找不到 Python 3.11，請先安裝');
      python = P.venvPython(dir);
    }
    if (!python) throw new Error('找不到 Python 環境，請先建立');
    if (id === 'create-env') {
      await must(python, ['-m', 'pip', 'install', '--upgrade', 'pip']);
      await must(python, ['-m', 'pip', 'install', '-r', path.join(ctx.root, 'windows', 'requirements.txt')]);
    }
    await must(python, ['-m', 'pip', 'install', ...P.CUDA_WHEELS]);
    return;
  }
  if (id === 'pull-translation') {
    await ensureOllamaRunning(env, log, deps);
    await must(findExecutable('ollama', env), ['pull', P.TRANSLATION_MODEL]);
    return;
  }
  if (id === 'download-asr') {
    const python = P.findPython(ctx);
    if (!python) throw new Error('請先建立 Python 環境');
    // Default Hugging Face cache: windows/launch.py searches it, and it survives app updates.
    await must(python, ['-c', `from huggingface_hub import snapshot_download; print(snapshot_download('${P.ASR_REPO}'))`]);
  }
}

module.exports = { STEPS, ORDER, planFor, runStep, ensureOllamaRunning };
