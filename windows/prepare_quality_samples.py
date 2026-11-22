"""Authored diagnostic text only goes to TTS; live speech never leaves the PC."""
import asyncio,json,wave
from pathlib import Path
import av,edge_tts
from translation_eval import SAMPLES
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'quality/samples'
VOICES={'ja':'ja-JP-NanamiNeural','ko':'ko-KR-SunHiNeural','en':'en-US-JennyNeural'}

async def make(key,text,voice):
    path=FOLDER/(key+'.wav')
    if path.exists():return path
    mp3=FOLDER/(key+'.mp3')
    await edge_tts.Communicate(text,voice).save(str(mp3))
    container=av.open(str(mp3));resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
    frames=[]
    for frame in container.decode(audio=0):
        for out in resampler.resample(frame):frames.append(out.to_ndarray().tobytes())
    for out in resampler.resample(None):frames.append(out.to_ndarray().tobytes())
    container.close()
    with wave.open(str(path),'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b''.join(frames))
    return path

async def main():
    FOLDER.mkdir(parents=True,exist_ok=True)
    samples=[]
    for key,text,meaning in SAMPLES:
        voice=VOICES[key[:2]]
        path=await make(key,text,voice)
        samples.append(dict(id=key,path=path.relative_to(ROOT).as_posix(),source=text,reference_translation=meaning,
                            kind='synthetic',speaker=voice))
    # Same-language A/B/A dialogue; repeated voice uses different text.
    extra=[('speaker-a1','We should wait here. Our teammate will arrive in ten seconds.','en-US-JennyNeural','我們應該在這裡等。隊友十秒後到。'),
           ('speaker-b','I agree. Do not attack until everyone is ready.','en-US-GuyNeural','我同意。所有人準備好以前不要攻擊。'),
           ('speaker-a2','Now everyone is here. We can start the next round.','en-US-JennyNeural','現在大家都到了。我們可以開始下一輪。')]
    combined=bytearray();turns=[]
    for key,text,voice,meaning in extra:
        path=await make(key,text,voice)
        with wave.open(str(path),'rb') as w:raw=w.readframes(w.getnframes())
        start=len(combined)/32000;combined.extend(raw)
        turns.append(dict(start=start,end=len(combined)/32000,speaker=voice))
        combined.extend(bytes(32000))
    dialogue=FOLDER/'dialogue.wav'
    with wave.open(str(dialogue),'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(combined)
    samples.append(dict(id='dialogue',path=dialogue.relative_to(ROOT).as_posix(),kind='synthetic',
                        source=' '.join(t[1] for t in extra),reference_translation=' '.join(t[3] for t in extra),turns=turns))
    silence=FOLDER/'silence.wav'
    with wave.open(str(silence),'wb') as w:
        w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(bytes(32000*4))
    samples.append(dict(id='silence',path=silence.relative_to(ROOT).as_posix(),kind='synthetic',source='',reference_translation=''))
    (ROOT/'quality/manifest.json').write_text(json.dumps({'note':'Authored synthetic diagnostics, not real-world accuracy. References prepared before inference.','samples':samples},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Prepared',len(samples),'diagnostics.',flush=True)

if __name__=='__main__':asyncio.run(main())
