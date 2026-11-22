"""Allowlisted distribution: never include local models, secrets or company repos."""
from pathlib import Path
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
files=['server.mjs','quality.mjs','glossary.json','asr_glossary.json','package.json','WINDOWS_README.md','ARCHITECTURE.md','THIRD_PARTY_NOTICES.md',
       'INSTALL_WINDOWS.bat','START_WINDOWS.bat','START_WINDOWS_CPU_ASR.bat']
for folder,extensions in [('web',{'.html','.js','.css','.json','.wav'}),('extension',{'.json','.js','.html'}),('windows',{'.py','.ps1','.txt'})]:
    files.extend(str(p.relative_to(root)) for p in (root/folder).iterdir() if p.is_file() and p.suffix in extensions)
files.extend(str(p.relative_to(root)) for p in (root/'tests').glob('*.test.mjs'))
files.extend(p.name for p in root.glob('UPDATE_*.md'))
files.extend(str(p.relative_to(root)) for p in (root/'licenses').iterdir() if p.is_file())
files=sorted({Path(name).as_posix() for name in files})
version=json.loads((root/'extension/manifest.json').read_text(encoding='utf-8'))['version']
out=root/f'dist/MosaSub-Live-Windows-{version}.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    hashes={}
    for name in sorted(files):
        p=root/name
        if p.is_symlink():raise ValueError('Refusing symlink '+name)
        data=p.read_bytes()
        if p.suffix=='.bat':data=data.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
        z.writestr('MosaSub-Live-Windows/'+name,data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    z.writestr('MosaSub-Live-Windows/PACKAGE_SHA256.json',json.dumps(hashes,indent=2))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    assert len(z.namelist())==len(files)+1
print(f'{out}\n{out.stat().st_size} bytes\nSHA256: {hashlib.sha256(out.read_bytes()).hexdigest()}')
