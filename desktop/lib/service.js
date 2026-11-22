'use strict';
// Runs the existing launcher (windows/launch.py) and reports its state. The launcher already
// checks Ollama, picks the ASR model, restarts crashed children and keeps the defaults.
const { EventEmitter } = require('node:events');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { lineSplitter, run } = require('./run');
const { fetchJson } = require('./checks');

const HEALTH = 'http://127.0.0.1:8787/health';
const MAX_LOG_LINES = 400;
const MAX_LOG_BYTES = 2 * 1024 * 1024;

// One readable state for the UI from the bridge's /health answer.
function describe(health, { running, starting, lastError }) {
  if (health && health.app === 'mosasub-live-local') {
    const m = health.models || {};
    if (health.ready) return { phase: 'ready', text: '字幕服務已就緒', asr: m.asr, translation: m.translation, device: m.device };
    if (m.error) return { phase: 'error', text: '模型啟動失敗：' + m.error };
    return { phase: 'loading', text: '正在載入模型（第一次可能需要 1–2 分鐘）' };
  }
  if (starting || running) return { phase: 'starting', text: '正在啟動字幕服務…' };
  if (lastError) return { phase: 'error', text: lastError };
  return { phase: 'stopped', text: '字幕服務未啟動' };
}

class ServiceManager extends EventEmitter {
  constructor({ root, logDir, platform = process.platform, getJson = fetchJson, spawnImpl = spawn, runImpl = run }) {
    super();
    Object.assign(this, { root, logDir, platform, getJson, spawnImpl, runImpl });
    this.child = null; this.starting = false; this.lastError = null; this.health = null;
    this.lines = []; this.status = describe(null, {}); this.timer = null; this.stopping = false;
  }

  log(line) {
    const stamped = new Date().toLocaleTimeString('zh-TW', { hour12: false }) + '  ' + line;
    this.lines.push(stamped); if (this.lines.length > MAX_LOG_LINES) this.lines.shift();
    // The launcher prints a one-line reason when it gives up; show it instead of a vague state.
    const stop = /^Startup stopped: (.*)$/.exec(line);
    if (stop) this.lastError = '啟動失敗：' + stop[1];
    try {
      fs.mkdirSync(this.logDir, { recursive: true });
      const file = path.join(this.logDir, 'service.log');
      try { if (fs.statSync(file).size > MAX_LOG_BYTES) fs.renameSync(file, file + '.1'); } catch {}
      fs.appendFileSync(file, stamped + '\n');
    } catch {}
    this.emit('log', stamped);
  }

  async poll() {
    let health = null;
    try { health = await this.getJson(HEALTH, 2000); } catch {}
    this.health = health;
    const next = describe(health, { running: Boolean(this.child), starting: this.starting, lastError: this.lastError });
    next.owned = Boolean(this.child);
    if (JSON.stringify(next) !== JSON.stringify(this.status)) { this.status = next; this.emit('status', next); }
    return next;
  }

  watch(intervalMs = 2000) {
    clearInterval(this.timer);
    this.timer = setInterval(() => this.poll(), intervalMs);
    return this.poll();
  }

  async start({ python, env }) {
    const now = await this.poll();
    if (['ready', 'loading'].includes(now.phase)) { this.log('字幕服務已在執行，直接使用。'); return now; }
    if (this.child) return now;
    if (!python) throw new Error('找不到 Python 環境，請先完成環境設定');
    this.lastError = null; this.starting = true; this.stopping = false;
    this.log('啟動字幕服務：' + python + ' windows/launch.py');
    const child = this.spawnImpl(python, ['-u', path.join('windows', 'launch.py')], { cwd: this.root, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    this.child = child;
    const out = lineSplitter(l => this.log(l)), err = lineSplitter(l => this.log(l));
    child.stdout?.on('data', d => out.push(d)); child.stderr?.on('data', d => err.push(d));
    child.on('error', error => { this.lastError = '無法啟動 Python：' + error.message; this.log(this.lastError); });
    child.on('exit', code => {
      out.end(); err.end();
      if (this.child === child) this.child = null;
      this.starting = false;
      if (!this.stopping && code !== 0 && !this.lastError) this.lastError = `字幕服務意外結束（代碼 ${code}），詳見紀錄`;
      this.log(`字幕服務已結束（代碼 ${code}）`);
      this.poll();
    });
    setTimeout(() => { this.starting = false; }, 15000);
    return this.poll();
  }

  // Stops only what this app started. Ollama is shared and stays running, as with START_WINDOWS.bat.
  async stop() {
    const child = this.child;
    if (!child) return this.poll();
    this.stopping = true;
    this.log('正在停止字幕服務…');
    if (this.platform === 'win32') {
      // Killing launch.py alone would orphan its children; killing the whole tree would also
      // stop Ollama. So list its direct children first and stop all of them except Ollama.
      const ps = await this.runImpl('powershell.exe', ['-NoProfile', '-Command',
        `Get-CimInstance Win32_Process -Filter "ParentProcessId=${child.pid}" | Select-Object ProcessId,Name | ConvertTo-Json -Compress`], { timeoutMs: 10000 });
      let kids = [];
      try { const parsed = JSON.parse(ps.output || '[]'); kids = Array.isArray(parsed) ? parsed : [parsed]; } catch {}
      await this.runImpl('taskkill', ['/PID', String(child.pid), '/F'], { timeoutMs: 10000 });
      for (const kid of kids) {
        if (!kid || /^ollama/i.test(kid.Name || '')) continue;
        await this.runImpl('taskkill', ['/PID', String(kid.ProcessId), '/T', '/F'], { timeoutMs: 10000 });
      }
    } else {
      child.kill('SIGINT');
    }
    await new Promise(resolve => { if (!this.child) return resolve(); const t = setTimeout(resolve, 8000); child.once('exit', () => { clearTimeout(t); resolve(); }); });
    this.child = null; this.starting = false;
    return this.poll();
  }

  async resources() {
    try { return await this.getJson('http://127.0.0.1:8787/resources', 4000); } catch { return null; }
  }

  dispose() { clearInterval(this.timer); }
}

module.exports = { ServiceManager, describe, HEALTH };
