"""Build positive-control clips: a real "chat" said right after a hard cut.

The echo guard (MOSA_ASR_ECHO_RETRY) re-decodes a post-cut result made only of glossary words
("Twitch", "chat"). This checks it does not lose a "chat" the speaker really said. Speaking
exactly into the 6 s hard cut is impractical, so recordings are spliced:

  recordings/long-*.wav   continuous speech of 8 s or more, no pauses (any format FFmpeg reads)
  recordings/chat-*.wav   one short phrase each; the phrase is the file name after "chat-",
                          without a trailing number: chat-thanks-chat-2.wav -> "thanks chat"

Samples written (each replayed in its own session by evaluate_live.mjs):
  after_cut   : passage trimmed at a quiet point near 5.7/5.9/6.1/6.3 s + 150 ms gap + phrase,
                so the hard cut lands around the phrase and the post-cut piece is often only it
  after_pause : 3 s of passage + 1.5 s silence + phrase (no hard cut; the guard must not fire)
  alone       : the phrase alone between silences

  .venv-win\\Scripts\\python.exe windows\\build_chat_controls.py recordings --out quality/eval/chat-controls
"""
import argparse,json,re,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_fleurs_eval import decode,ROOT

FRAME=320
TARGETS_MS=(5700,5900,6100,6300)

def edges(audio,range_db=35):
    """Trim silence relative to the clip's own loudest 20 ms frame (works for any recording level)."""
    n=len(audio)//FRAME
    if not n:return audio
    rms=np.sqrt((audio[:n*FRAME].reshape(n,FRAME).astype(np.float64)**2).mean(axis=1))
    voiced=np.flatnonzero(rms>=max(rms.max()*10**(-range_db/20),1/32768))
    return audio[voiced[0]*FRAME:(voiced[-1]+1)*FRAME] if len(voiced) else audio[:0]

def quiet_cut(audio,target_ms,window_ms=150):
    """Cut at the quietest 20 ms frame within +-window_ms of target_ms, to avoid splitting a word."""
    lo=max(1,int((target_ms-window_ms)*16)//FRAME);hi=min(len(audio)//FRAME-1,int((target_ms+window_ms)*16)//FRAME)
    if hi<=lo:raise ValueError(f'passage shorter than {target_ms+window_ms} ms after trimming')
    rms=[float(np.sqrt((audio[i*FRAME:(i+1)*FRAME].astype(np.float64)**2).mean())) for i in range(lo,hi)]
    return audio[:(lo+int(np.argmin(rms)))*FRAME]

def phrase(path):
    return re.sub(r'-\d+$','',path.stem[len('chat-'):]).replace('-',' ').strip()

def silence(ms):return np.zeros(int(ms*16),np.float32)

def build(recordings,out_dir):
    longs=sorted(Path(recordings).glob('long-*'));chats=sorted(Path(recordings).glob('chat-*'))
    if not longs or not chats:raise ValueError('need recordings/long-*.wav and recordings/chat-*.wav files')
    passages=[(p.stem,edges(decode(p.read_bytes()))) for p in longs]
    for name,audio in passages:
        if len(audio)<6450*16:raise ValueError(f'{name} is {len(audio)/16000:.1f} s after trimming; record 8 s or more of continuous speech')
    out_dir=Path(out_dir);manifest_path=out_dir/'chat-controls.manifest.json'
    if manifest_path.exists():raise FileExistsError(f'{manifest_path} exists; choose another --out')
    out_dir.mkdir(parents=True,exist_ok=True);samples=[]
    def write(sample_id,audio,**meta):
        path=out_dir/(sample_id+'.wav')
        with wave.open(str(path),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
        rel=path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else str(path.resolve())
        samples.append(dict(id=sample_id,path=rel,language='en',kind='chat-positive-control',source=meta['phrase'],**meta))
    for i,chat_path in enumerate(chats):
        words=phrase(chat_path);clip=edges(decode(chat_path.read_bytes()))
        if not words or 'chat' not in words.split():raise ValueError(f'{chat_path.name}: the phrase must contain the word chat')
        for j,target in enumerate(TARGETS_MS):
            name,audio=passages[(i+j)%len(passages)];speech=quiet_cut(audio,target)
            write(f'{chat_path.stem}-after-cut-{target}',np.concatenate([silence(500),speech,silence(150),clip,silence(2000)]),
                  category='after_cut',phrase=words,passage=name,speech_ms=round(len(speech)/16),recording=chat_path.name)
        name,audio=passages[i%len(passages)]
        write(f'{chat_path.stem}-after-pause',np.concatenate([silence(500),quiet_cut(audio,3000),silence(1500),clip,silence(2000)]),
              category='after_pause',phrase=words,passage=name,recording=chat_path.name)
        write(f'{chat_path.stem}-alone',np.concatenate([silence(1000),clip,silence(2000)]),category='alone',phrase=words,recording=chat_path.name)
    manifest_path.write_text(json.dumps(dict(note='Spliced positive controls for the ASR echo guard; each sample is replayed in its own session.',
                                             samples=samples),ensure_ascii=False,indent=1),encoding='utf-8')
    return manifest_path,samples

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('recordings');parser.add_argument('--out',default=str(ROOT/'quality'/'eval'/'chat-controls'))
    args=parser.parse_args()
    manifest,samples=build(args.recordings,args.out)
    counts={c:sum(s['category']==c for s in samples) for c in ('after_cut','after_pause','alone')}
    print(f'Wrote {len(samples)} samples {counts}')
    if manifest.resolve().is_relative_to(ROOT):print('Run: node windows/evaluate_live.mjs',manifest.resolve().relative_to(ROOT).as_posix())

if __name__=='__main__':main()
