"""Install official sherpa-onnx streaming models; never execute archive scripts."""
import hashlib,json,tarfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'.models/streaming'
MODELS={'multi':'sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10',
        'ko':'sherpa-onnx-streaming-zipformer-korean-2024-06-16'}
def install():
    ROOT.mkdir(parents=True,exist_ok=True)
    records=[]
    for key,name in MODELS.items():
        url='https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/'+name+'.tar.bz2'
        archive=ROOT/(name+'.tar.bz2')
        if not archive.exists():
            staging=archive.with_suffix('.part');urllib.request.urlretrieve(url,staging);staging.replace(archive)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                target=(ROOT/member.name).resolve()
                if not target.is_relative_to(ROOT.resolve()):raise RuntimeError('Unsafe archive path')
                if member.isfile() and (member.name.endswith(('.onnx','.txt','.md')) or 'LICENSE' in member.name):
                    tar.extract(member,ROOT,filter='data')
        records.append(dict(key=key,name=name,url=url,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
        print('Installed',key,name,flush=True)
    (ROOT/'sources.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
if __name__=='__main__':install()
