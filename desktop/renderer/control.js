import { capturePipeline } from '../web/engine.js';
import { CaptionView, holdMs } from './captions.js';

const $ = id => document.getElementById(id);
const mosa = window.mosa;
const API = 'mosalive://app/api';
let settings = {}, status = { phase: 'stopped' }, checks = null, steps = {};
let halt = null, mode = null, starting = false, view = new CaptionView(), clearTimer = null, epoch = 0;

// ---------- captions ----------
function show(caption) {
  clearTimeout(clearTimer);
  mosa.sendCaption(caption);
  if (caption) clearTimer = setTimeout(() => mosa.sendCaption(null), holdMs(caption));
}

function onEvent(e) {
  if (e.type === 'partial' || e.type === 'final') {
    const caption = view.accept(e, settings);
    if (caption) show(caption);
    if (e.type === 'final' && Number.isFinite(e.after_speech_ms)) setLive('字幕顯示中 · 說完到字幕約 ' + (e.after_speech_ms / 1000).toFixed(1) + ' 秒');
    return;
  }
  if (e.type === 'audio-level') { $('meter').style.width = Math.max(0, Math.min(100, (e.rms_dbfs + 60) * 100 / 60)) + '%'; return; }
  if (e.type === 'status' || e.type === 'activity') { setLive(e.text); if (e.clear || e.clearPartial) show(null); }
}

function setLive(text) { $('liveStatus').textContent = text || ''; }

async function systemAudio() {
  // The app answers this request with the computer's own sound (Windows loopback); no picker appears.
  const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
  stream.getVideoTracks().forEach(t => t.stop());
  const audio = stream.getAudioTracks();
  if (!audio.length) throw new Error('沒有取得電腦的聲音。請確認 Windows 有播放裝置，再試一次。');
  return new MediaStream(audio);
}

async function testAudio() {
  const player = $('testAudio');
  player.src = 'mosalive://app/web/test-en.wav'; player.loop = true;
  await player.play();
  return player.captureStream();
}

async function start(kind) {
  if (halt || starting) return;
  starting = true; const token = ++epoch;
  try {
    const stream = kind === 'test' ? await testAudio() : await systemAudio();
    if (token !== epoch) { stream.getTracks().forEach(t => t.stop()); return; }
    view.reset();
    halt = await capturePipeline(stream, { base: API, worklet: 'mosalive://app/web/worklet.js', sourceOnly: settings.displayMode === 'original',
      asrMode: settings.asrMode, quality: false, onEvent: e => { if (token === epoch) onEvent(e); } });
    mode = kind;
    setLive(kind === 'test' ? '正在播放英文測試音訊（循環）' : '正在聽電腦播放的聲音…');
    mosa.setCapturing(true);
  } catch (error) {
    setLive('無法開始：' + (error.message || error));
    stopTest();
  } finally { starting = false; render(); }
}

function stopTest() { const p = $('testAudio'); p.pause(); p.removeAttribute('src'); p.load(); }

function stop() {
  epoch++;
  halt?.(); halt = null; mode = null; stopTest();
  show(null); $('meter').style.width = '0';
  setLive('字幕已停止'); mosa.setCapturing(false); render();
}

// ---------- rendering ----------
const PILL = { ready: 'ready', loading: 'loading', starting: 'starting', error: 'error', stopped: 'stopped' };
function render() {
  const ready = status.phase === 'ready';
  $('pill').className = 'pill ' + (PILL[status.phase] || 'stopped');
  $('pillText').textContent = status.text || '';
  $('toggle').disabled = !halt && (!ready || starting);
  $('toggle').textContent = halt ? '停止字幕' : starting ? '開始中…' : '開始字幕';
  $('toggle').classList.toggle('stop', Boolean(halt));
  $('test').disabled = Boolean(halt) || !ready || starting;
  if (!halt && !ready) setLive(status.phase === 'error' ? status.text : status.phase === 'stopped' ? '先啟動字幕服務（下方「字幕服務」）' : '服務準備好後就能開始');
  else if (!halt && !starting && !$('liveStatus').textContent) setLive('準備好了：播放直播或影片，再按「開始字幕」');
  $('svcText').textContent = (status.text || '—') + (status.phase !== 'stopped' && !status.owned ? '（由其他視窗啟動）' : '');
  $('svcAsr').textContent = status.asr || '—';
  $('svcNmt').textContent = status.translation || '—';
  $('svcStart').disabled = ['ready', 'loading', 'starting'].includes(status.phase);
  $('svcStop').disabled = !status.owned;
}

function renderSettings() {
  for (const id of ['displayMode', 'asrMode']) $(id).value = settings[id];
  for (const id of ['fontSize', 'opacity']) { $(id).value = settings[id]; $(id + 'Out').textContent = settings[id] + (id === 'opacity' ? '%' : ''); }
  for (const id of ['finalOnly', 'locked', 'autoStartService', 'stopServiceOnQuit']) $(id).checked = settings[id];
}

function renderChecks(result) {
  checks = result;
  const list = $('checks'); list.textContent = '';
  for (const c of result.results) {
    const li = document.createElement('li'); li.className = c.level;
    const mark = document.createElement('span'); mark.className = 'mark'; mark.textContent = c.level === 'ok' ? '✓' : c.level === 'warn' ? '!' : '✕';
    const body = document.createElement('div'); body.textContent = c.label;
    const small = document.createElement('small'); small.textContent = c.detail; body.append(small);
    li.append(mark, body);
    if (c.fix && steps[c.fix]) {
      const b = document.createElement('button'); b.className = 'link small'; b.textContent = c.fix === 'gpu-driver' ? '下載' : '安裝';
      b.onclick = () => runSetup([c.fix]); li.append(b);
    } else li.append(document.createElement('span'));
    list.append(li);
  }
  const plan = result.plan || [];
  $('setupBox').hidden = !plan.length;
  if (plan.length) $('setupText').textContent = '會依序進行：' + plan.map(id => `${steps[id].label}（${steps[id].size}）`).join('、') + '。需要網路，時間視網路速度而定。';
}

async function runSetup(ids) {
  const what = ids ? ids.map(id => `${steps[id].label}（${steps[id].size || '開啟網頁'}）`).join('\n') : '所有缺少的項目';
  if (!confirm('即將開始：\n' + what + '\n\n需要網路，下載量可能很大。要繼續嗎？')) return;
  $('setupAll').disabled = true;
  try { renderChecks(await mosa.runSetup(ids || null)); }
  catch (error) { $('setupProgress').textContent = error.message; }
  finally { $('setupAll').disabled = false; }
}

function appendLog(line) {
  const pre = $('log'); pre.textContent += line + '\n';
  if (pre.textContent.length > 60000) pre.textContent = pre.textContent.slice(-40000);
  pre.scrollTop = pre.scrollHeight;
}

async function refreshGpu() {
  if (status.phase !== 'ready') { $('svcGpu').textContent = '—'; return; }
  const r = await mosa.resources();
  const g = r?.gpus?.[0];
  $('svcGpu').textContent = g ? `${(g.used_mib / 1024).toFixed(1)} / ${(g.total_mib / 1024).toFixed(1)} GB（整張顯示卡）` : '無法取得';
}

// ---------- wiring ----------
async function save(patch) { settings = await mosa.setSettings(patch); renderSettings(); }

$('toggle').onclick = () => (halt ? stop() : start('system'));
$('test').onclick = () => start('test');
$('displayMode').onchange = e => { save({ displayMode: e.target.value }); halt?.setSourceOnly?.(e.target.value === 'original'); view.reset(); show(null); };
$('asrMode').onchange = e => { save({ asrMode: e.target.value }); halt?.setAsrMode?.(e.target.value); show(null); };
for (const id of ['fontSize', 'opacity']) $(id).oninput = e => save({ [id]: Number(e.target.value) });
for (const id of ['finalOnly', 'locked', 'autoStartService', 'stopServiceOnQuit']) $(id).onchange = e => save({ [id]: e.target.checked });
$('resetOverlay').onclick = () => mosa.resetOverlay();
$('recheck').onclick = async () => { $('checks').innerHTML = '<li class="muted">檢查中…</li>'; renderChecks(await mosa.runChecks()); };
$('setupAll').onclick = () => runSetup(null);
$('svcStart').onclick = async () => { status = await mosa.startService(); render(); };
$('svcStop').onclick = async () => { if (halt) stop(); status = await mosa.stopService(); render(); };
$('openLogs').onclick = () => mosa.openLogs();

mosa.onStatus(s => { status = s; render(); if (s.phase !== 'ready' && halt && mode !== 'test') setLive('字幕服務狀態改變：' + s.text); });
mosa.onLog(appendLog);
mosa.onChecks(renderChecks);
mosa.onSettings(s => { settings = s; renderSettings(); });
mosa.onSetup(p => {
  $('setupProgress').textContent = p.state === 'running' ? '進行中：' + p.label + '…' : p.state === 'done' ? '完成：' + p.label : '失敗：' + p.label + '。' + (p.error || '');
});
mosa.onCommand(cmd => { if (cmd === 'toggle-capture') { if (halt) stop(); else if (status.phase === 'ready') start('system'); } });
window.addEventListener('beforeunload', () => halt?.());

const state = await mosa.getState();
settings = state.settings; status = state.status; steps = state.steps;
renderSettings(); render();
if (state.checks) renderChecks(state.checks);
state.log.forEach(appendLog);
setInterval(refreshGpu, 5000);
