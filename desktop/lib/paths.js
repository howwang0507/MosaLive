'use strict';
// Where things live. Pure functions with injected paths so they can be tested on any OS.
const path = require('node:path');
const fs = require('node:fs');

// Same defaults as START_WINDOWS.bat; values already set in the environment win.
const DEFAULT_ENV = { MOSA_NMT_MODEL: 'gemma3:4b', MOSA_ASR_MODEL: 'large-v3-turbo', MOSA_SOFT_CUT_MS: '3500' };
const TRANSLATION_MODEL = 'gemma3:4b';
const ASR_REPO = 'mobiuslabsgmbh/faster-whisper-large-v3-turbo';
// Pinned to the wheels already shipped in _cuda_pkgs; launch.py adds their bin folders to PATH.
const CUDA_WHEELS = ['nvidia-cublas-cu12==12.6.4.1', 'nvidia-cudnn-cu12==9.5.1.17'];

// Development runs from <repo>/desktop; the installed app carries the service in resources/runtime.
function runtimeRoot({ packaged, appDir, resourcesPath }) {
  return packaged ? path.join(resourcesPath, 'runtime') : path.resolve(appDir, '..');
}

// Large, machine-specific data (the Python environment) stays out of roaming profiles and
// outside the install folder, so updating or reinstalling the app keeps it.
function dataRoot({ localAppData, userData }) {
  return localAppData ? path.join(localAppData, 'MosaLive') : userData;
}

function envDir({ packaged, root, data }) {
  return packaged ? path.join(data, 'python') : path.join(root, '.venv-win');
}

const venvPython = dir => path.join(dir, 'Scripts', 'python.exe');

// Existing project environments first (the GPU test environment is what START_WINDOWS.bat prefers).
function pythonCandidates({ root, data, packaged }) {
  const list = [venvPython(path.join(root, '.venv-gpu-test')), venvPython(path.join(root, '.venv-win'))];
  list.push(venvPython(envDir({ packaged, root, data })));
  return [...new Set(list)];
}

function findPython(opts, exists = fs.existsSync) {
  return pythonCandidates(opts).find(p => exists(p)) || null;
}

// Mirrors resolve_asr() in windows/launch.py: project cache first, then the user's Hugging Face cache.
function hubDir(env, home) {
  if (env.HF_HUB_CACHE) return env.HF_HUB_CACHE;
  if (env.HF_HOME) return path.join(env.HF_HOME, 'hub');
  return path.join(home, '.cache', 'huggingface', 'hub');
}

function findAsrModel({ root, env, home }, fsx = fs) {
  const folder = 'models--' + ASR_REPO.replace('/', '--');
  for (const base of [path.join(root, '.models', 'windows'), hubDir(env, home)]) {
    const snapshots = path.join(base, folder, 'snapshots');
    let names = [];
    try { names = fsx.readdirSync(snapshots); } catch { continue; }
    for (const name of names) {
      const file = path.join(snapshots, name, 'model.bin');
      if (fsx.existsSync(file)) return path.dirname(file);
    }
  }
  return null;
}

function cudaWheelDirs(pythonExe) {
  const prefix = path.dirname(path.dirname(pythonExe));
  return ['cublas', 'cudnn'].map(name => path.join(prefix, 'Lib', 'site-packages', 'nvidia', name, 'bin'));
}

// Fresh installs via winget do not update this process's PATH, so also look in the default folders.
function knownExecutable(name, env) {
  const local = env.LOCALAPPDATA || '';
  const windir = env.WINDIR || 'C:\\Windows';
  const table = {
    ollama: [path.join(local, 'Programs', 'Ollama', 'ollama.exe')],
    py: [path.join(windir, 'py.exe'), path.join(local, 'Programs', 'Python', 'Launcher', 'py.exe')],
    python311: [path.join(local, 'Programs', 'Python', 'Python311', 'python.exe')],
  };
  return table[name] || [];
}

function serviceEnv(base, { nodeExe, extraPath = [] }) {
  const env = { ...base };
  for (const [key, value] of Object.entries(DEFAULT_ENV)) if (!env[key]) env[key] = value;
  env.MOSA_NO_BROWSER = '1';
  env.PYTHONIOENCODING = 'utf-8';
  env.PYTHONUTF8 = '1';
  // server.mjs runs on Electron's bundled Node, so a separate Node.js install is not required.
  if (nodeExe) { env.MOSA_NODE = nodeExe; env.ELECTRON_RUN_AS_NODE = '1'; }
  const key = Object.keys(env).find(k => k.toUpperCase() === 'PATH') || 'PATH';
  env[key] = [...extraPath, env[key] || ''].filter(Boolean).join(path.delimiter);
  return env;
}

module.exports = { DEFAULT_ENV, TRANSLATION_MODEL, ASR_REPO, CUDA_WHEELS, runtimeRoot, dataRoot, envDir, venvPython,
  pythonCandidates, findPython, hubDir, findAsrModel, cudaWheelDirs, knownExecutable, serviceEnv };
