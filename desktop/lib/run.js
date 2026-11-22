'use strict';
// Small process helpers: run a command, stream its output line by line, never through a shell.
const { spawn } = require('node:child_process');

function lineSplitter(onLine) {
  let rest = '';
  return {
    push(chunk) {
      rest += chunk.toString('utf8');
      const parts = rest.split(/\r\n|\n|\r/);
      rest = parts.pop();
      // Very long lines (progress bars) are cut so the log stays readable.
      for (const line of parts) if (line.trim()) onLine(line.slice(0, 400));
      if (rest.length > 4000) { onLine(rest.slice(0, 400)); rest = ''; }
    },
    end() { if (rest.trim()) onLine(rest.slice(0, 400)); rest = ''; },
  };
}

// Resolves with { code, output } where output keeps only the last lines.
function run(cmd, args, { cwd, env, onLine = () => {}, timeoutMs = 0, keep = 40, spawnImpl = spawn } = {}) {
  return new Promise(resolve => {
    const tail = [];
    const note = line => { tail.push(line); if (tail.length > keep) tail.shift(); onLine(line); };
    let child;
    try {
      child = spawnImpl(cmd, args, { cwd, env, windowsHide: true, shell: false });
    } catch (error) {
      resolve({ code: -1, output: String(error.message || error), error });
      return;
    }
    const out = lineSplitter(note), err = lineSplitter(note);
    child.stdout?.on('data', d => out.push(d));
    child.stderr?.on('data', d => err.push(d));
    let timer = null, done = false;
    const finish = result => { if (done) return; done = true; clearTimeout(timer); out.end(); err.end(); resolve({ ...result, output: tail.join('\n') }); };
    if (timeoutMs) timer = setTimeout(() => { try { child.kill(); } catch {} finish({ code: -2, timedOut: true }); }, timeoutMs);
    child.on('error', error => finish({ code: -1, error }));
    child.on('close', code => finish({ code }));
  });
}

module.exports = { run, lineSplitter };
