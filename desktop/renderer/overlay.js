const $ = id => document.getElementById(id);
const mosa = window.mosa;

function applySettings(s) {
  document.documentElement.style.setProperty('--size', s.fontSize + 'px');
  document.documentElement.style.setProperty('--bg', String(s.opacity / 100));
  document.body.classList.toggle('unlocked', !s.locked);
}

function showCaption(c) {
  $('original').textContent = c?.original || '';
  $('translation').textContent = c?.translation || '';
  $('note').textContent = c?.note || '';
  $('box').classList.toggle('empty', !c);
  $('box').classList.toggle('draft', Boolean(c && !c.final));
}

$('lock').onclick = () => mosa.lockOverlay();
mosa.onSettings(applySettings);
mosa.onCaption(showCaption);
const state = await mosa.getState();
applySettings(state.settings);
showCaption(null);
