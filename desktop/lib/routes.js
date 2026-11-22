'use strict';
// What the app's mosalive://app/ pages may load. Everything is allowlisted: the app's own
// renderer files, the shared caption pipeline from web/, and two bridge endpoints.
const path = require('node:path');

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.wav': 'audio/wav' };
const RENDERER = new Set(['control.html', 'control.js', 'control.css', 'overlay.html', 'overlay.js', 'overlay.css', 'captions.js', 'icon.png']);
// The same pipeline files the browser test page uses, so app and web page cannot drift apart.
const WEB = new Set(['engine.js', 'live-client.js', 'ndjson.js', 'worklet.js', 'test-en.wav', 'test-ja.wav', 'test-ko.wav']);
const API = { 'POST /live/frame': '/live/frame', 'GET /health': '/health' };

function routeFor(url, method, { appDir, root }) {
  let u;
  try { u = new URL(url); } catch { return { kind: 'none' }; }
  if (u.protocol !== 'mosalive:' || u.host !== 'app') return { kind: 'none' };
  const parts = u.pathname.split('/').filter(Boolean);
  if (parts.length === 2 && parts[0] === 'renderer' && RENDERER.has(parts[1]) && method === 'GET')
    return { kind: 'file', file: path.join(appDir, 'renderer', parts[1]), type: TYPES[path.extname(parts[1])] };
  if (parts.length === 2 && parts[0] === 'web' && WEB.has(parts[1]) && method === 'GET')
    return { kind: 'file', file: path.join(root, 'web', parts[1]), type: TYPES[path.extname(parts[1])] };
  if (parts[0] === 'api') {
    const target = API[method + ' /' + parts.slice(1).join('/')];
    if (target && !u.search) return { kind: 'api', target };
  }
  return { kind: 'none' };
}

module.exports = { routeFor };
