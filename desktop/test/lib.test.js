'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const P = require('../lib/paths');
const { parseGpus, hasModel, runChecks } = require('../lib/checks');
const { planFor, STEPS } = require('../lib/setup');
const { describe: describeHealth, ServiceManager } = require('../lib/service');
const { Settings, DEFAULTS } = require('../lib/settings');
const { routeFor } = require('../lib/routes');
const { lineSplitter } = require('../lib/run');

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'mosalive-'));

test('runtime and data roots', () => {
  assert.equal(P.runtimeRoot({ packaged: false, appDir: '/repo/desktop' }), path.resolve('/repo'));
  assert.equal(P.runtimeRoot({ packaged: true, resourcesPath: '/app/resources' }), path.join('/app/resources', 'runtime'));
  assert.equal(P.dataRoot({ localAppData: '/L', userData: '/U' }), path.join('/L', 'MosaLive'));
  assert.equal(P.dataRoot({ userData: '/U' }), '/U');
});

test('python: project environments first, then the app environment', () => {
  const list = P.pythonCandidates({ root: '/r', data: '/d', packaged: true });
  assert.deepEqual(list.map(p => p.split(path.sep).slice(-3, -2)[0]), ['.venv-gpu-test', '.venv-win', 'python']);
  assert.equal(P.findPython({ root: '/r', data: '/d', packaged: true }, p => p.includes('python' + path.sep + 'Scripts')), list[2]);
  assert.equal(P.findPython({ root: '/r', data: '/d', packaged: false }, () => false), null);
});

test('ASR model search mirrors launch.py (project cache, then HF cache)', () => {
  const root = tmp(), home = tmp();
  assert.equal(P.findAsrModel({ root, env: {}, home }), null);
  const snap = path.join(home, '.cache', 'huggingface', 'hub', 'models--mobiuslabsgmbh--faster-whisper-large-v3-turbo', 'snapshots', 'abc');
  fs.mkdirSync(snap, { recursive: true }); fs.writeFileSync(path.join(snap, 'model.bin'), 'x');
  assert.equal(P.findAsrModel({ root, env: {}, home }), snap);
  const custom = tmp();
  assert.equal(P.findAsrModel({ root, env: { HF_HUB_CACHE: custom }, home }), null);
});

test('service env keeps user overrides and adds bundled node', () => {
  const env = P.serviceEnv({ PATH: '/bin', MOSA_NMT_MODEL: 'qwen2.5:7b' }, { nodeExe: '/app/MosaLive.exe', extraPath: ['/cuda'] });
  assert.equal(env.MOSA_NMT_MODEL, 'qwen2.5:7b');
  assert.equal(env.MOSA_ASR_MODEL, 'large-v3-turbo');
  assert.equal(env.MOSA_SOFT_CUT_MS, '3500');
  assert.equal(env.MOSA_NO_BROWSER, '1');
  assert.equal(env.MOSA_NODE, '/app/MosaLive.exe');
  assert.equal(env.ELECTRON_RUN_AS_NODE, '1');
  assert.equal(env.PATH, ['/cuda', '/bin'].join(path.delimiter));
  const win = P.serviceEnv({ Path: 'C:\\x' }, { extraPath: ['D:\\y'] });
  assert.equal(win.Path, ['D:\\y', 'C:\\x'].join(path.delimiter));
  assert.equal('PATH' in win, false);
});

test('GPU and model parsing', () => {
  assert.deepEqual(parseGpus('NVIDIA GeForce RTX 4060 Ti, 8188\r\n'), [{ name: 'NVIDIA GeForce RTX 4060 Ti', memoryMiB: 8188 }]);
  assert.deepEqual(parseGpus(''), []);
  assert.equal(hasModel({ models: [{ name: 'gemma3:4b' }] }, 'gemma3:4b'), true);
  assert.equal(hasModel({ models: [{ name: 'qwen2.5:7b' }] }, 'gemma3:4b'), false);
});

test('checks: a fresh computer asks for every install step in order', async () => {
  const ctx = { root: tmp(), data: tmp(), packaged: true, env: { PATH: '' }, home: tmp(), platform: 'win32', arch: 'x64', release: '10.0.22631' };
  const report = await runChecks(ctx, { exists: () => false, run: async () => ({ code: 1, output: '' }), fetchJson: async () => { throw new Error('down'); } });
  const byId = Object.fromEntries(report.results.map(r => [r.id, r]));
  assert.equal(byId.gpu.level, 'error');
  assert.equal(byId['python-env'].fix, 'install-python');
  assert.equal(byId.ollama.fix, 'install-ollama');
  assert.equal(byId['asr-model'].level, 'warn');
  assert.equal(report.ready, false);
  assert.deepEqual(planFor(report.results), ['install-python', 'install-ollama', 'create-env', 'pull-translation', 'download-asr']);
});

test('checks: a ready computer passes', async () => {
  const root = tmp(), home = tmp();
  const snap = path.join(root, '.models', 'windows', 'models--mobiuslabsgmbh--faster-whisper-large-v3-turbo', 'snapshots', 's');
  fs.mkdirSync(snap, { recursive: true }); fs.writeFileSync(path.join(snap, 'model.bin'), 'x');
  const venv = path.join(root, '.venv-gpu-test');
  const present = new Set([P.venvPython(venv), ...P.cudaWheelDirs(P.venvPython(venv))]);
  const ctx = { root, data: tmp(), packaged: false, env: { PATH: '' }, home, platform: 'win32', arch: 'x64', release: '10' };
  const report = await runChecks(ctx, { exists: p => present.has(p) || fs.existsSync(p), run: async () => ({ code: 0, output: 'NVIDIA GeForce RTX 4060 Ti, 8188' }),
    fetchJson: async () => ({ models: [{ name: 'gemma3:4b' }] }) });
  assert.equal(report.ready, true, JSON.stringify(report.results));
  assert.equal(report.results.every(r => r.level === 'ok'), true);
  assert.deepEqual(planFor(report.results), []);
});

test('every fix named by checks has a setup step', () => {
  for (const id of ['install-python', 'install-ollama', 'create-env', 'cuda-wheels', 'pull-translation', 'download-asr', 'gpu-driver']) assert.ok(STEPS[id], id);
});

test('health is described for the UI', () => {
  assert.equal(describeHealth({ app: 'mosasub-live-local', ready: true, models: { asr: 'large-v3-turbo', translation: 'gemma3:4b' } }, {}).phase, 'ready');
  assert.equal(describeHealth({ app: 'mosasub-live-local', ready: false, models: { error: 'CUDA' } }, {}).phase, 'error');
  assert.equal(describeHealth({ app: 'mosasub-live-local', ready: false, models: {} }, {}).phase, 'loading');
  assert.equal(describeHealth({ app: 'something-else' }, {}).phase, 'stopped');
  assert.equal(describeHealth(null, { starting: true }).phase, 'starting');
  assert.equal(describeHealth(null, { lastError: 'x' }).text, 'x');
});

test('service reuses a running service and does not spawn', async () => {
  let spawned = false;
  const s = new ServiceManager({ root: tmp(), logDir: tmp(), getJson: async () => ({ app: 'mosasub-live-local', ready: true, models: {} }), spawnImpl: () => { spawned = true; } });
  const status = await s.start({ python: '/p', env: {} });
  assert.equal(status.phase, 'ready'); assert.equal(status.owned, false); assert.equal(spawned, false);
});

test('service surfaces the launcher failure line', () => {
  const s = new ServiceManager({ root: tmp(), logDir: tmp() });
  s.log('Startup stopped: Configured translation model is not installed: gemma3:4b. No model was downloaded.');
  assert.match(s.lastError, /gemma3:4b/);
});

test('service stop on Windows keeps Ollama running', async () => {
  const { EventEmitter } = require('node:events');
  const calls = [];
  const child = Object.assign(new EventEmitter(), { pid: 100 });
  const s = new ServiceManager({ root: tmp(), logDir: tmp(), platform: 'win32', getJson: async () => { throw new Error('down'); },
    runImpl: async (cmd, args) => {
      calls.push([cmd, ...args].join(' '));
      if (cmd === 'powershell.exe') return { code: 0, output: JSON.stringify([{ ProcessId: 101, Name: 'python.exe' }, { ProcessId: 102, Name: 'node.exe' }, { ProcessId: 103, Name: 'ollama.exe' }]) };
      if (args[1] === '100') setImmediate(() => child.emit('exit', 1));
      return { code: 0, output: '' };
    } });
  s.child = child;
  await s.stop();
  assert.deepEqual(calls.slice(1), ['taskkill /PID 100 /F', 'taskkill /PID 101 /T /F', 'taskkill /PID 102 /T /F']);
});

test('settings reject bad values and survive a damaged file', () => {
  const file = path.join(tmp(), 'settings.json');
  fs.writeFileSync(file, '{not json');
  const s = new Settings(file);
  assert.deepEqual(s.get(), DEFAULTS);
  assert.deepEqual(s.set({ fontSize: 999, displayMode: 'zh', evil: 1 }), { displayMode: 'zh' });
  assert.equal(new Settings(file).get().displayMode, 'zh');
});

test('protocol routes are allowlisted', () => {
  const opts = { appDir: '/app', root: '/root' };
  assert.deepEqual(routeFor('mosalive://app/renderer/control.html', 'GET', opts), { kind: 'file', file: path.join('/app', 'renderer', 'control.html'), type: 'text/html; charset=utf-8' });
  assert.equal(routeFor('mosalive://app/web/engine.js', 'GET', opts).file, path.join('/root', 'web', 'engine.js'));
  assert.equal(routeFor('mosalive://app/web/../server.mjs', 'GET', opts).kind, 'none');
  assert.equal(routeFor('mosalive://app/web/app.js', 'GET', opts).kind, 'none');
  assert.equal(routeFor('mosalive://app/renderer/%2e%2e/main.js', 'GET', opts).kind, 'none');
  assert.deepEqual(routeFor('mosalive://app/api/live/frame', 'POST', opts), { kind: 'api', target: '/live/frame' });
  assert.equal(routeFor('mosalive://app/api/glossary', 'POST', opts).kind, 'none');
  assert.equal(routeFor('mosalive://app/api/live/frame', 'GET', opts).kind, 'none');
  assert.equal(routeFor('mosalive://other/renderer/control.html', 'GET', opts).kind, 'none');
});

test('line splitter handles CRLF, progress carriage returns and long lines', () => {
  const lines = []; const s = lineSplitter(l => lines.push(l));
  s.push(Buffer.from('a\r\nb\rc')); s.push(Buffer.from('d\n' + 'x'.repeat(500))); s.end();
  assert.deepEqual(lines.slice(0, 3), ['a', 'b', 'cd']);
  assert.equal(lines[3].length, 400);
});
