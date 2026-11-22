"""Compare beam search on identical recorded live segments, not end-to-end latency."""
import os,sys,json,wave,time,unicodedata
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
handles=[]
for name in ('cublas','cudnn'):
    p=Path(sys.prefix)/'Lib/site-packages/nvidia'/name/'bin'
    if p.is_dir():
        handles.append(os.add_dll_directory(str(p)))
        os.environ['PATH']=str(p)+os.pathsep+os.environ.get('PATH','')
from faster_whisper import WhisperModel
def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).lower() if not c.isspace() and unicodedata.category(c)[0] not in ('P','Z'))
def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a):
        nxt=[i+1]
        for j,y in enumerate(b):nxt.append(min(nxt[-1]+1,row[j+1]+1,row[j]+(x!=y)))
        row=nxt
    return row[-1]
model=WhisperModel('small',device='cuda',compute_type='int8_float16',download_root=str(ROOT/'.models/windows'))
rows=json.loads((ROOT/'quality/real-auto-0.3.0.json').read_text('utf-8'))['results']
results=[]
for row in rows:
    with wave.open(str(ROOT/row['path'])) as f:audio=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
    segments=[e for e in row['events'] if e['type']=='final']
    result={'id':row['id'],'language':row['language'],'source':row['source'],'settings':{}}
    for beam in (1,3):
        texts=[];duration=0
        for event in segments:
            clip=audio[round(event['speech_start_ms']*16):round((event['speech_end_ms']+128)*16)]
            started=time.perf_counter()
            output,_=model.transcribe(clip,language=None,beam_size=beam,temperature=0,condition_on_previous_text=False,word_timestamps=event.get('overlap_ms',0)>0)
            kept=[s for s in output if s.no_speech_prob<.65]
            text=''.join(w.word for s in kept for w in s.words if w.end>event['overlap_ms']/1000) if event.get('overlap_ms') else ''.join(s.text for s in kept)
            duration+=time.perf_counter()-started;texts.append(text.strip())
        text=' '.join(texts);ref=norm(row['source'])
        result['settings'][str(beam)]={'text':text,'cer':distance(norm(text),ref)/len(ref),'decode_seconds':duration}
    results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    (ROOT/'quality/beam-comparison-0.3.1.json').write_text(json.dumps({'note':'Same recorded final segment boundaries. Sequential beam 1 then 3. Decode timing includes initial warmup; not live latency. No reference text supplied to recognizer.','results':results},ensure_ascii=False,indent=2),encoding='utf-8')
