"""Explicit real inference probe against existing local services; no downloads."""
import json,urllib.request,sys,wave,io
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def get(url):
    with urllib.request.urlopen(url,timeout=4) as r:return json.load(r)
try:
    health=get('http://127.0.0.1:8790/health')
    print('Configured ASR device:',health.get('device'),'startup ready:',health.get('ready'))
    with wave.open(str(root/'web/test-ja.wav'),'rb') as source:
        if (source.getnchannels(),source.getsampwidth(),source.getframerate())!=(1,2,16000):raise RuntimeError('Test fixture must be mono PCM16 16kHz')
        pcm=source.readframes(source.getnframes())
    canonical=io.BytesIO()
    with wave.open(canonical,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(pcm)
    request=urllib.request.Request('http://127.0.0.1:8787/segment',data=canonical.getvalue(),headers={'Content-Type':'audio/wav','Accept':'application/x-ndjson'},method='POST')
    final=None
    with urllib.request.urlopen(request,timeout=60) as response:
        for line in response:
            event=json.loads(line)
            if event.get('type')=='error':raise RuntimeError(event.get('error'))
            if event.get('type')=='final':final=event
    if not final or not final.get('translation'):raise RuntimeError('No translated final caption')
    print('PASS: actual synthetic audio recognition and translation succeeded')
    print(json.dumps({k:final.get(k) for k in ('original','translation','asr_ms','translation_ms')},ensure_ascii=False))
    print('Device is reported configuration; this is not GPU profiling or real livestream accuracy.')
except Exception as error:
    print('FAIL:',type(error).__name__,str(error));sys.exit(1)
