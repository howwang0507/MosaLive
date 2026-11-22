"""Local synthetic smoke benchmark; excludes browser capture time, not a quality score."""
import io,json,time,wave,statistics
from pathlib import Path
import httpx,numpy as np

ROOT=Path(__file__).resolve().parents[1]

def audio(name):
    if name=='tone':
        frames=(np.sin(np.arange(48000)*2*np.pi*440/16000)*.1*32767).astype('<i2').tobytes()
    else:
        with wave.open(str(ROOT/'web'/('test-'+name+'.wav')),'rb') as f:
            assert (f.getnchannels(),f.getframerate(),f.getsampwidth())==(1,16000,2)
            frames=f.readframes(f.getnframes())
    buf=io.BytesIO()
    with wave.open(buf,'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(frames)
    return buf.getvalue()

if __name__=='__main__':
    results=[]
    with httpx.Client(timeout=120) as c:
        health=c.get('http://127.0.0.1:8787/health').json()
        for name in ['ja','en','ko','tone']:
            for display in ['both','original']:
                runs=[]
                for i in range(4):
                    t=time.perf_counter()
                    r=c.post('http://127.0.0.1:8787/segment',content=audio(name),headers={'Accept':'application/x-ndjson','X-Mosa-Display':display})
                    r.raise_for_status();events=[json.loads(line) for line in r.text.splitlines()]
                    final=events[-1]
                    if final.get('type')!='final':raise RuntimeError(final)
                    runs.append(dict(wall_ms=(time.perf_counter()-t)*1000,result=final))
                entry=dict(sample=name,display=display,median_warm_ms=round(statistics.median(r['wall_ms'] for r in runs[1:]),1),runs=runs)
                results.append(entry)
                print(name,display,entry['median_warm_ms'],json.dumps(final,ensure_ascii=False),flush=True)
    output=ROOT/'benchmark-live-multilingual.json'
    output.write_text(json.dumps(dict(note='Synthetic samples; excludes audio capture and rendering; first run excluded from median.',health=health,results=results),ensure_ascii=False,indent=2),encoding='utf-8')
