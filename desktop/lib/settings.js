'use strict';
// User preferences, validated on every read and write so a damaged file cannot break the app.
const fs = require('node:fs');
const path = require('node:path');

const DEFAULTS = {
  displayMode: 'both',      // both | zh | original
  asrMode: 'auto',          // auto | stream-en | stream-ja | stream-ko
  finalOnly: false,
  fontSize: 30,
  opacity: 70,
  locked: false,
  autoStartService: true,
  stopServiceOnQuit: true,  // frees the GPU when the app closes
  overlayBounds: null,      // { x, y, width, height }
  seenTrayHint: false,
};

const RULES = {
  displayMode: v => ['both', 'zh', 'original'].includes(v),
  asrMode: v => ['auto', 'stream-en', 'stream-ja', 'stream-ko'].includes(v),
  finalOnly: v => typeof v === 'boolean',
  fontSize: v => Number.isInteger(v) && v >= 16 && v <= 64,
  opacity: v => Number.isInteger(v) && v >= 0 && v <= 100,
  locked: v => typeof v === 'boolean',
  autoStartService: v => typeof v === 'boolean',
  stopServiceOnQuit: v => typeof v === 'boolean',
  overlayBounds: v => v === null || (v && ['x', 'y', 'width', 'height'].every(k => Number.isFinite(v[k])) && v.width >= 200 && v.height >= 60),
  seenTrayHint: v => typeof v === 'boolean',
};

function clean(input) {
  const out = {};
  for (const [key, ok] of Object.entries(RULES)) if (input && key in input && ok(input[key])) out[key] = input[key];
  return out;
}

class Settings {
  constructor(file) { this.file = file; this.values = { ...DEFAULTS }; this.load(); }
  load() {
    try { this.values = { ...DEFAULTS, ...clean(JSON.parse(fs.readFileSync(this.file, 'utf8'))) }; } catch { this.values = { ...DEFAULTS }; }
    return this.values;
  }
  get() { return { ...this.values }; }
  set(patch) {
    const accepted = clean(patch);
    this.values = { ...this.values, ...accepted };
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      fs.writeFileSync(this.file + '.tmp', JSON.stringify(this.values, null, 2));
      fs.renameSync(this.file + '.tmp', this.file);
    } catch {}
    return accepted;
  }
}

module.exports = { Settings, DEFAULTS, clean };
