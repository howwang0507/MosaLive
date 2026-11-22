"""FLEURS CC-BY-4.0 held-out read speech, first four test rows per language."""
import io,json,hashlib,urllib.request,wave
from pathlib import Path
import av,pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'quality/real'

def main():
    FOLDER.mkdir(parents=True,exist_ok=True);samples=[];sources=[]
    for language,config in [('en','en_us'),('ja','ja_jp'),('ko','ko_kr')]:
        tree=json.load(urllib.request.urlopen('https://huggingface.co/api/datasets/google/fleurs/tree/refs%2Fconvert%2Fparquet/'+config+'/test'))
        item=next(f for f in tree if f['path'].endswith('.parquet'))
        url='https://huggingface.co/datasets/google/fleurs/resolve/refs%2Fconvert%2Fparquet/'+item['path']
        parquet=FOLDER/(config+'.parquet')
        if not parquet.exists():
            staging=parquet.with_suffix('.part');urllib.request.urlretrieve(url,staging);staging.replace(parquet)
        digest=hashlib.sha256(parquet.read_bytes()).hexdigest()
        if digest!=item['lfs']['oid']:raise RuntimeError('Dataset checksum mismatch')
        rows=next(pq.ParquetFile(parquet).iter_batches(batch_size=4)).to_pylist()
        for index,row in enumerate(rows):
            path=FOLDER/(config+'-'+str(index)+'.wav')
            decoder=av.open(io.BytesIO(row['audio']['bytes']))
            resampler=av.AudioResampler(format='s16',layout='mono',rate=16000);pcm=[]
            for frame in decoder.decode(audio=0):
                pcm.extend(out.to_ndarray().tobytes() for out in resampler.resample(frame))
            pcm.extend(out.to_ndarray().tobytes() for out in resampler.resample(None));decoder.close()
            with wave.open(str(path),'wb') as f:
                f.setparams((1,2,16000,0,'NONE','none'));f.writeframes(b''.join(pcm))
            samples.append(dict(id=language+'-real-'+str(index),language=language,path=path.relative_to(ROOT).as_posix(),
                source=row.get('raw_transcription') or row['transcription'],reference_translation=None,
                kind='human-read-speech',dataset='google/fleurs',dataset_id=row['id'],split='test',row=index,license='CC-BY-4.0'))
        sources.append(dict(config=config,url=url,sha256=digest))
        print('Prepared',config,flush=True)
    (ROOT/'quality/real-manifest.json').write_text(json.dumps(dict(samples=samples,sources=sources,
        note='Google FLEURS, CC-BY-4.0. First 4 test rows per en_us/ja_jp/ko_kr. Human read speech, not Twitch. Audio converted to mono 16k PCM16; original reference text retained.'),ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
