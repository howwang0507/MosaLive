"""Diagnose captions that consist only of "chat" / "and chat." / "comments" after a hard cut.

Read-only diagnosis; changes no model, prompt, VAD or endpointing. For each suspect final in an
evaluate_live.mjs result, the audio the service recognized is cut from the replayed WAV and
recognized again with the service's exact Faster-Whisper settings under four conditions:

  live     : glossary initial prompt + overlap word filter   (what the service does)
  no_prompt: no initial prompt         + overlap word filter
  no_filter: glossary initial prompt + all words kept
  neither  : no prompt                 + all words kept

It also lists every raw segment (text, avg_logprob, no_speech_prob, compression ratio, whether
assess_segment kept it) and every word with its end time against the overlap cutoff, so a
dropped real word can be told apart from a hallucinated one. The reference sentence overlapping
the same audio is shown for comparison.

Uses the GPU when --device cuda (default, same as the service). Stop gaming or other GPU work
first, or pass --device cpu (int8; numerics differ slightly from the service's CUDA run).
Models are loaded from the local cache only; nothing is downloaded.

  .venv-win\\Scripts\\python.exe windows\\diagnose_chat_hallucination.py quality\\level-normalized-20261024.json
"""
import argparse,json,os,re,sys,wave
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from quality_checks import assess_segment,static_prompt

ROOT=Path(__file__).resolve().parents[1]
SUSPECT=re.compile(r'^\W*(?:and\s+)?(?:chat|comments?)\W*$',re.I)
TAIL_MS=128   # the service keeps up to 4 frames (128 ms) after the detected speech end
VARIANTS=(('live',True,True),('no_prompt',False,True),('no_filter',True,False),('neither',False,False))

def glossary_prompt():
    """Same prompt the service builds (models.asr_prompt) from asr_glossary.json."""
    path=ROOT/'asr_glossary.json'
    if not path.is_file():return None
    terms=json.loads(path.read_text(encoding='utf-8')).get('terms',[])
    return static_prompt(terms)

def unique_finals(result):
    finals={}
    for e in result.get('events',[]):
        if isinstance(e,dict) and e.get('type')=='final' and e.get('seq') not in finals:finals[e['seq']]=e
    return sorted(finals.values(),key=lambda e:e.get('speech_start_ms',0))

def suspects(finals,all_after_hard_cut=False):
    """Finals that are only chat/comments, or with the flag every final that follows a hard cut."""
    found=[]
    for i,e in enumerate(finals):
        previous=finals[i-1] if i else None
        after_cut=bool(previous) and previous.get('endpoint_reason')=='continuous_limit'
        if SUSPECT.match(e.get('original','').strip()) or (all_after_hard_cut and after_cut):found.append((e,previous,after_cut))
    return found

def clip(audio,final):
    """Audio the service recognized: segment start (incl. overlap) to speech end + kept tail.
    Valid when the replay had no restarts, so session time equals WAV time."""
    start=int(round(final['speech_start_ms']*16));end=int(round((final['speech_end_ms']+TAIL_MS)*16))
    return audio[max(0,start):min(len(audio),end)]

def recognize(model,audio,overlap_ms,language,use_prompt,use_filter,prompt):
    segments,info=model.transcribe(audio,language=language,task='transcribe',beam_size=1,temperature=0,condition_on_previous_text=False,
                                   # same as the service: word timestamps only when there is an overlap to filter
                                   word_timestamps=overlap_ms>0,compression_ratio_threshold=2.4,log_prob_threshold=-1.0,
                                   initial_prompt=prompt if use_prompt else None)
    segments=list(segments);kept=[s for s in segments if assess_segment(s)[0]]
    cutoff=overlap_ms/1000 if use_filter and overlap_ms else None
    text=''.join(w.word for s in kept for w in (s.words or []) if cutoff is None or w.end>cutoff) if cutoff is not None else ''.join(s.text for s in kept)
    # float()/bool(): Faster-Whisper and assess_segment can return numpy scalars, which json cannot write.
    detail=[dict(text=s.text,start=round(float(s.start),2),end=round(float(s.end),2),avg_logprob=round(float(s.avg_logprob),3),no_speech_prob=round(float(s.no_speech_prob),3),
                 compression_ratio=round(float(s.compression_ratio),2),kept=bool(assess_segment(s)[0]),
                 words=[dict(word=w.word,end=round(float(w.end),2),before_overlap_cutoff=bool(overlap_ms and w.end<=overlap_ms/1000)) for w in (s.words or [])])
            for s in segments]
    return dict(text=text.strip(),segments=detail)

def reference_text(reference,final):
    if not reference:return None
    return ' | '.join(s['source'] for s in reference['segments'] if s['end_ms']>final['speech_start_ms'] and s['start_ms']<final['speech_end_ms']+TAIL_MS)

def summarize(rows):
    count=lambda name,pattern:sum(bool(re.search(pattern,r['variants'][name]['text'],re.I)) for r in rows)
    chat=r'\b(?:chat|comments?)\b'
    return dict(suspects=len(rows),**{f'{name}_contains_chat':count(name,chat) for name,_,_ in VARIANTS},
                live_replica_matches_service=sum(r['variants']['live']['text']==r['service_text'] for r in rows),
                real_words_dropped_by_overlap_filter=sum(len(r['variants']['no_filter']['text'].split())>len(r['variants']['live']['text'].split()) for r in rows))

def load_wav(path):
    with wave.open(str(path)) as f:
        if (f.getnchannels(),f.getframerate(),f.getsampwidth())!=(1,16000,2):raise ValueError('Expected the 16 kHz mono PCM16 replay WAV')
        return np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run',help='evaluate_live.mjs result JSON');parser.add_argument('--out',help='new JSON report path')
    parser.add_argument('--device',default=os.environ.get('MOSA_ASR_DEVICE','cuda'),choices=('cuda','cpu'))
    parser.add_argument('--model',default=os.environ.get('MOSA_ASR_MODEL','small'))
    parser.add_argument('--all-after-hard-cut',action='store_true',help='also diagnose every final that follows a hard cut')
    parser.add_argument('--limit',type=int,default=40)
    args=parser.parse_args()
    data=json.loads(Path(args.run).read_text(encoding='utf-8'));result=data['results'][0]
    restarts=sum((result.get('metrics') or {}).get(k) or 0 for k in ('reconnects','playback_reset_count','overflow_count'))
    if restarts:sys.exit('The replay restarted; session time no longer equals WAV time, so clips cannot be cut reliably.')
    audio=load_wav(ROOT/result['path'])
    reference=json.loads((ROOT/result['reference']).read_text(encoding='utf-8')) if result.get('reference') else None
    language={'stream-en':'en','stream-ja':'ja','stream-ko':'ko'}.get(result.get('asrMode'))
    items=suspects(unique_finals(result),args.all_after_hard_cut)[:args.limit]
    if not items:print('No suspect finals found.');return
    out=Path(args.out or Path(args.run).with_name(Path(args.run).stem+'-chat-diagnosis.json'))
    if out.exists():parser.error(f'{out} exists; choose a new --out')
    from faster_whisper import WhisperModel
    model=WhisperModel(args.model,device=args.device,compute_type='int8_float16' if args.device=='cuda' else 'int8',
                       download_root=str(ROOT/'.models/windows'),local_files_only=True)
    prompt=glossary_prompt();rows=[]
    for final,previous,after_cut in items:
        piece=clip(audio,final);overlap=final.get('overlap_ms') or 0
        row=dict(seq=final['seq'],speech_start_ms=final['speech_start_ms'],speech_end_ms=final['speech_end_ms'],overlap_ms=overlap,
                 clip_ms=round(len(piece)/16),after_hard_cut=after_cut,previous_text=(previous or {}).get('original'),
                 service_text=final.get('original',''),reference=reference_text(reference,final),
                 variants={name:recognize(model,piece,overlap,language,use_prompt,use_filter,prompt) for name,use_prompt,use_filter in VARIANTS})
        rows.append(row)
        print(f"\nseq {row['seq']} ({row['clip_ms']} ms, overlap {overlap} ms, after hard cut {after_cut})")
        print('  previous :',(row['previous_text'] or '')[:100]);print('  reference:',(row['reference'] or '')[:140]);print('  service  :',row['service_text'])
        for name,_,_ in VARIANTS:print(f'  {name:<9}:',row['variants'][name]['text'][:120])
    summary=summarize(rows)
    out.write_text(json.dumps(dict(run=args.run,device=args.device,model=args.model,prompt=prompt,tail_ms=TAIL_MS,summary=summary,rows=rows),ensure_ascii=False,indent=1),encoding='utf-8')
    print('\nSummary:',summary);print('Saved',out)
    print('Single diagnostic pass: it suggests a cause; confirm any change with a full benchmark rerun.')

if __name__=='__main__':main()
