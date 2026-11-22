'use strict';
// MosaLive desktop app: one window to set up and control the local caption service, plus an
// always-on-top caption overlay fed by the computer's own audio (Windows loopback capture).
const { app, BrowserWindow, Tray, Menu, ipcMain, protocol, net, session, desktopCapturer, shell, globalShortcut, nativeImage, screen, Notification } = require('electron');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const P = require('./lib/paths');
const { runChecks } = require('./lib/checks');
const { STEPS, planFor, runStep, ensureOllamaRunning } = require('./lib/setup');
const { ServiceManager } = require('./lib/service');
const { Settings } = require('./lib/settings');
const { routeFor } = require('./lib/routes');

protocol.registerSchemesAsPrivileged([{ scheme: 'mosalive', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true } }]);

if (!app.requestSingleInstanceLock()) { app.quit(); }

const packaged = app.isPackaged;
const ROOT = P.runtimeRoot({ packaged, appDir: __dirname, resourcesPath: process.resourcesPath });
const DATA = P.dataRoot({ localAppData: process.env.LOCALAPPDATA, userData: app.getPath('userData') });
const ctxBase = () => ({ root: ROOT, data: DATA, packaged, env: process.env, home: os.homedir(), platform: process.platform, arch: process.arch, release: os.release() });
const settings = new Settings(path.join(app.getPath('userData'), 'settings.json'));
const service = new ServiceManager({ root: ROOT, logDir: path.join(DATA, 'logs') });
const ICON = path.join(__dirname, 'build', 'icon.png');

let control = null, overlay = null, tray = null, quitting = false, capturing = false, lastChecks = null, setupBusy = false;

const sendAll = (channel, payload) => { for (const w of [control, overlay]) if (w && !w.isDestroyed()) w.webContents.send(channel, payload); };

function extraPath() {
  const dirs = [];
  const ollama = lastChecks?.ollama;
  if (ollama) dirs.push(path.dirname(ollama));
  const python = P.findPython(ctxBase());
  if (python) dirs.push(...P.cudaWheelDirs(python));
  return dirs;
}

async function refreshChecks() {
  lastChecks = await runChecks(ctxBase());
  lastChecks.plan = planFor(lastChecks.results);
  sendAll('checks', lastChecks);
  return lastChecks;
}

async function startService() {
  const checks = lastChecks || await refreshChecks();
  const python = P.findPython(ctxBase());
  const env = P.serviceEnv(process.env, { nodeExe: process.execPath, extraPath: extraPath() });
  // launch.py would start Ollama too, but it needs it on PATH; starting it here also covers fresh installs.
  if (checks.ollama) { try { await ensureOllamaRunning(env, line => service.log(line)); } catch (e) { service.log(e.message); } }
  return service.start({ python, env });
}

function createControl() {
  control = new BrowserWindow({
    width: 980, height: 760, minWidth: 760, minHeight: 600, title: 'MosaLive', icon: ICON, backgroundColor: '#F7F4EE', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true, nodeIntegration: false, backgroundThrottling: false },
  });
  control.setMenuBarVisibility(false);
  control.loadURL('mosalive://app/renderer/control.html');
  control.once('ready-to-show', () => control.show());
  control.on('close', event => {
    if (quitting) return;
    // Captions keep running from the tray; the window just hides.
    event.preventDefault(); control.hide();
    if (!settings.get().seenTrayHint && Notification.isSupported()) {
      new Notification({ title: 'MosaLive 仍在執行', body: '字幕會繼續顯示。從右下角系統匣圖示可以打開控制台或結束程式。', icon: ICON }).show();
      settings.set({ seenTrayHint: true });
    }
  });
}

function defaultOverlayBounds() {
  const area = screen.getPrimaryDisplay().workArea;
  const width = Math.min(1100, Math.round(area.width * 0.7)), height = 170;
  return { x: Math.round(area.x + (area.width - width) / 2), y: Math.round(area.y + area.height - height - 40), width, height };
}

function visibleBounds(bounds) {
  if (!bounds) return defaultOverlayBounds();
  const onScreen = screen.getAllDisplays().some(d => {
    const a = d.workArea;
    return bounds.x < a.x + a.width - 50 && bounds.x + bounds.width > a.x + 50 && bounds.y < a.y + a.height - 30 && bounds.y + bounds.height > a.y;
  });
  return onScreen ? bounds : defaultOverlayBounds();
}

function applyLock(locked) {
  if (!overlay) return;
  // Locked: clicks pass through to the video underneath. Unlocked: the box can be moved and resized.
  overlay.setIgnoreMouseEvents(locked, { forward: true });
  overlay.setFocusable(!locked);
}

function createOverlay() {
  overlay = new BrowserWindow({
    ...visibleBounds(settings.get().overlayBounds), frame: false, transparent: true, alwaysOnTop: true, skipTaskbar: true, resizable: true,
    hasShadow: false, show: false, minWidth: 320, minHeight: 80, title: 'MosaLive 字幕',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true, sandbox: true, nodeIntegration: false, backgroundThrottling: false },
  });
  overlay.setAlwaysOnTop(true, 'screen-saver');
  overlay.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  overlay.loadURL('mosalive://app/renderer/overlay.html');
  overlay.once('ready-to-show', () => { overlay.showInactive(); applyLock(settings.get().locked); });
  let saveTimer = null;
  const save = () => { clearTimeout(saveTimer); saveTimer = setTimeout(() => overlay && settings.set({ overlayBounds: overlay.getBounds() }), 400); };
  overlay.on('move', save); overlay.on('resize', save);
  overlay.on('close', event => { if (!quitting) { event.preventDefault(); overlay.hide(); } });
}

function setSettings(patch) {
  const accepted = settings.set(patch);
  if ('locked' in accepted) applyLock(accepted.locked);
  sendAll('settings', settings.get());
  updateTray();
  return settings.get();
}

function updateTray() {
  if (!tray) return;
  const s = settings.get();
  tray.setToolTip('MosaLive｜' + (capturing ? '字幕顯示中' : service.status.text));
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '打開控制台', click: () => { control.show(); control.focus(); } },
    { label: capturing ? '停止字幕' : '開始字幕', enabled: capturing || service.status.phase === 'ready', click: () => sendAll('command', 'toggle-capture') },
    { label: '鎖定字幕框（點擊穿透）', type: 'checkbox', checked: s.locked, click: item => setSettings({ locked: item.checked }) },
    { label: '顯示字幕框', click: () => overlay.showInactive() },
    { type: 'separator' },
    { label: '結束 MosaLive', click: () => { quitting = true; app.quit(); } },
  ]));
}

function registerIpc() {
  ipcMain.handle('state:get', () => ({ settings: settings.get(), status: service.status, checks: lastChecks, log: service.lines.slice(-200),
    steps: STEPS, version: app.getVersion(), capturing, root: packaged ? null : ROOT }));
  ipcMain.handle('settings:set', (_e, patch) => setSettings(patch));
  ipcMain.handle('checks:run', () => refreshChecks());
  ipcMain.handle('service:start', async () => { try { return await startService(); } catch (e) { service.lastError = e.message; return service.poll(); } });
  ipcMain.handle('service:stop', () => service.stop());
  ipcMain.handle('service:resources', () => service.resources());
  ipcMain.handle('setup:run', async (_e, ids) => {
    if (setupBusy) throw new Error('安裝進行中，請等它完成');
    const checks = lastChecks || await refreshChecks();
    const plan = Array.isArray(ids) ? ids.filter(id => STEPS[id]) : planFor(checks.results);
    setupBusy = true;
    try {
      for (const id of plan) {
        sendAll('setup', { id, state: 'running', label: STEPS[id].label });
        const log = line => { service.log('[安裝] ' + line); };
        try { await runStep(id, { ...ctxBase(), openExternal: url => shell.openExternal(url) }, log); }
        catch (error) { sendAll('setup', { id, state: 'failed', label: STEPS[id].label, error: error.message }); return refreshChecks(); }
        sendAll('setup', { id, state: 'done', label: STEPS[id].label });
      }
    } finally { setupBusy = false; }
    return refreshChecks();
  });
  ipcMain.handle('overlay:reset', () => { overlay.setBounds(defaultOverlayBounds()); overlay.showInactive(); return true; });
  ipcMain.handle('open:logs', () => shell.openPath(path.join(DATA, 'logs')));
  ipcMain.on('caption', (_e, caption) => { if (overlay && !overlay.isDestroyed()) overlay.webContents.send('caption', caption); });
  ipcMain.on('capture:state', (_e, on) => {
    capturing = Boolean(on);
    if (capturing && overlay && !overlay.isVisible()) overlay.showInactive();
    sendAll('capture', capturing); updateTray();
  });
  ipcMain.on('overlay:lock', () => setSettings({ locked: true }));
}

// Captions read the computer's sound output. Windows provides it as "loopback" audio; the
// screen video that comes with it is dropped by the page right away.
function allowSystemAudio() {
  session.defaultSession.setDisplayMediaRequestHandler((_request, callback) => {
    desktopCapturer.getSources({ types: ['screen'] }).then(sources => {
      if (!sources.length) return callback({});
      callback({ video: sources[0], audio: process.platform === 'win32' ? 'loopback' : undefined });
    }).catch(() => callback({}));
  });
  session.defaultSession.setPermissionRequestHandler((_wc, permission, done) => done(['media', 'display-capture', 'notifications'].includes(permission)));
}

function registerProtocol() {
  protocol.handle('mosalive', async request => {
    const route = routeFor(request.url, request.method, { appDir: __dirname, root: ROOT });
    if (route.kind === 'file') {
      const response = await net.fetch(pathToFileURL(route.file).toString());
      return new Response(response.body, { status: response.status, headers: { 'Content-Type': route.type, 'Cache-Control': 'no-store' } });
    }
    if (route.kind === 'api') {
      // The bridge only accepts its own origin or the Chrome extension, so the app talks to it
      // from the main process (no Origin header) and streams the NDJSON answer back unchanged.
      const headers = {};
      for (const [k, v] of request.headers) if (/^(content-type|accept|x-mosa-)/i.test(k)) headers[k] = v;
      const body = request.method === 'POST' ? await request.arrayBuffer() : undefined;
      try {
        return await net.fetch('http://127.0.0.1:8787' + route.target, { method: request.method, headers, body, bypassCustomProtocolHandlers: true });
      } catch (error) {
        return new Response(JSON.stringify({ error: '本機字幕服務沒有回應：' + error.message }), { status: 503, headers: { 'Content-Type': 'application/json' } });
      }
    }
    return new Response('Not found', { status: 404 });
  });
}

function registerShortcuts() {
  const map = { 'Alt+Shift+S': () => sendAll('command', 'toggle-capture'), 'Alt+Shift+L': () => setSettings({ locked: !settings.get().locked }),
    'Alt+Shift+D': () => { const order = ['both', 'zh', 'original'], now = settings.get().displayMode; setSettings({ displayMode: order[(order.indexOf(now) + 1) % 3] }); } };
  for (const [key, fn] of Object.entries(map)) { try { globalShortcut.register(key, fn); } catch {} }
}

app.on('second-instance', () => { if (control) { control.show(); control.focus(); } });

app.whenReady().then(async () => {
  app.setAppUserModelId('io.github.howwang0507.mosalive');
  registerProtocol(); allowSystemAudio(); registerIpc();
  createControl(); createOverlay();
  tray = new Tray(nativeImage.createFromPath(ICON).resize({ width: 16, height: 16 }));
  tray.on('click', () => { control.show(); control.focus(); });
  updateTray(); registerShortcuts();
  service.on('status', status => { sendAll('status', status); updateTray(); });
  service.on('log', line => sendAll('log', line));
  await service.watch();
  const checks = await refreshChecks();
  if (settings.get().autoStartService && checks.ready && service.status.phase === 'stopped') startService().catch(e => service.log(e.message));
});

app.on('before-quit', event => {
  quitting = true;
  if (settings.get().stopServiceOnQuit && service.child && !service.stopping) {
    // Free the GPU before leaving: stop the models this app started.
    event.preventDefault();
    service.stop().finally(() => { service.child = null; app.quit(); });
  }
});
app.on('will-quit', () => { globalShortcut.unregisterAll(); service.dispose(); });
app.on('window-all-closed', () => { /* stay in the tray */ });
