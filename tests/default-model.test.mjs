import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const read = name => readFileSync(new URL('../'+name,import.meta.url),'utf8');
test('standard launch, backend fallback, installer and README use the measured model',()=>{
 const model = read('START_WINDOWS.bat').match(/MOSA_NMT_MODEL=([^"\r\n]+)/)[1];
 assert.equal(model,'gemma3:4b');
 for(const path of ['windows/models.py','windows/launch.py']) {
  assert.equal(read(path).match(/get\('MOSA_NMT_MODEL','([^']+)'\)/)[1],model,path);
 }
 assert.ok(read('windows/install.ps1').includes('ollama pull '+model));
 assert.ok(read('README.md').includes('Ollama '+model));
});
