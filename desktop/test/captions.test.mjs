import test from 'node:test';
import assert from 'node:assert/strict';
import { CaptionView, holdMs } from '../renderer/captions.js';

test('bilingual shows partial then final; stale events are ignored', () => {
  const v = new CaptionView(), s = { displayMode: 'both' };
  assert.deepEqual(v.accept({ type: 'partial', seq: 1, original: 'Chat, what', translation: '聊天室' }, s), { final: false, original: 'Chat, what', translation: '聊天室', note: '' });
  assert.equal(v.accept({ type: 'final', seq: 1, original: 'Chat, what do you think?', translation: '聊天室的各位，你們覺得呢？' }, s).final, true);
  assert.equal(v.accept({ type: 'partial', seq: 1, original: 'old', translation: '舊' }, s), null);
  assert.equal(v.accept({ type: 'final', seq: 0, original: 'older', translation: '更舊' }, s), null);
});

test('a partial without translation does not replace a finished line', () => {
  const v = new CaptionView(), s = { displayMode: 'zh' };
  v.accept({ type: 'final', seq: 1, original: 'Hello', translation: '你好' }, s);
  assert.equal(v.accept({ type: 'partial', seq: 2, original: 'Next' }, s), null);
  assert.equal(v.accept({ type: 'partial', seq: 2, original: 'Next', translation: '下一句' }, s).translation, '下一句');
});

test('final-only ignores partials', () => {
  const v = new CaptionView();
  assert.equal(v.accept({ type: 'partial', seq: 1, original: 'a', translation: 'b' }, { finalOnly: true }), null);
});

test('original mode (Mandarin livestreams) shows the source text only', () => {
  const v = new CaptionView();
  assert.deepEqual(v.accept({ type: 'final', seq: 3, original: '明天停止上班上課。', translation: '', source_only: true }, { displayMode: 'original' }),
    { final: true, original: '明天停止上班上課。', translation: '', note: '' });
});

test('Chinese-only falls back to the original when translation is unavailable', () => {
  const v = new CaptionView();
  const c = v.accept({ type: 'final', seq: 1, original: 'Hello', translation: '', translation_unavailable: true }, { displayMode: 'zh' });
  assert.equal(c.original, 'Hello'); assert.match(c.note, /翻譯/);
});

test('empty finals are not shown and hold time grows with length', () => {
  const v = new CaptionView();
  assert.equal(v.accept({ type: 'final', seq: 1, original: '', translation: '' }, {}), null);
  assert.equal(holdMs({ translation: '短' }), 2500);
  assert.equal(holdMs({ translation: '字'.repeat(100) }), 8000);
});
