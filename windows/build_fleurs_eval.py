"""Build a repeatable English->Traditional Chinese evaluation stream from FLEURS.

FLEURS (google/fleurs, CC BY 4.0) gives read English speech with transcripts and
the same FLoRes sentence in Mandarin. This script pairs them by sentence id (never
by row number), trims each clip's edge silence, joins clips with seeded gaps and
writes three files under quality/eval/:

  <name>.wav             16 kHz mono PCM16 stream for windows/evaluate_live.mjs
  <name>.reference.json  per-sentence timing, English source, zh-Hans and zh-TW references
  <name>.manifest.json   manifest for evaluate_live.mjs

Concatenated read sentences are a repeatable benchmark, not natural live speech:
speaker changes, joins and pause lengths are synthetic. Pair it with a natural set.

  .venv-win\\Scripts\\python.exe windows\\build_fleurs_eval.py --minutes 20

All three files come from one dataset commit: "main" is resolved to a commit id once,
then every download uses that id, and each file's SHA-256 is recorded. No credentials
are sent (the dataset is public; urllib would forward an Authorization header across
redirects to other hosts). If downloading is blocked, fetch the three files manually
and pass --source-dir together with --revision <commit>.
"""
import argparse,csv,hashlib,io,json,math,os,random,re,sys,tarfile,time,urllib.request,wave
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
REPO='https://huggingface.co/datasets/google/fleurs/resolve/{revision}/data/{lang}/{path}'
REVISION_API='https://huggingface.co/api/datasets/google/fleurs/revision/{revision}'
FILES={'source_tsv':('en_us','test.tsv'),'target_tsv':('cmn_hans_cn','test.tsv'),'source_audio':('en_us','audio/test.tar.gz')}
SOURCE_LANG,TARGET_LANG='en_us','cmn_hans_cn'
NUMBER=re.compile(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|thousand|million|billion|percent)\b',re.I)
NEGATION=re.compile(r"\b(?:not|no|never|none|nobody|nothing|neither|nor|without|cannot)\b|n['’]t\b",re.I)
CONDITION=re.compile(r'\b(?:if|unless|until|although|though|because|except)\b',re.I)

def request(url):
    # Deliberately no Authorization header: it would follow redirects to other hosts.
    return urllib.request.Request(url,headers={'User-Agent':'mosasub-eval'})

def resolve_revision(revision):
    """Turn a branch name into the commit id used for every download."""
    if re.fullmatch(r'[0-9a-f]{40}',revision):return revision
    with urllib.request.urlopen(request(REVISION_API.format(revision=revision)),timeout=30) as response:
        sha=json.load(response).get('sha','')
    if not re.fullmatch(r'[0-9a-f]{40}',sha):raise RuntimeError(f'Could not resolve FLEURS revision {revision!r} to a commit')
    return sha

def sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        while chunk:=f.read(1<<20):digest.update(chunk)
    return digest.hexdigest()

def fetch(url,path):
    """Download once into a cache folder named after the pinned commit."""
    if path.exists() and path.stat().st_size:return path
    path.parent.mkdir(parents=True,exist_ok=True)
    print('Downloading',url,flush=True)
    with urllib.request.urlopen(request(url),timeout=60) as response,open(str(path)+'.part','wb') as out:
        while chunk:=response.read(1<<20):out.write(chunk)
    os.replace(str(path)+'.part',path)
    return path

def read_tsv(path):
    """FLEURS rows: id, file_name, raw_transcription, transcription, phonemes, num_samples, gender."""
    rows=[]
    with open(path,encoding='utf-8',newline='') as f:
        for line in csv.reader(f,delimiter='\t',quoting=csv.QUOTE_NONE):
            if len(line)<7:raise ValueError(f'{path}: expected 7 FLEURS columns, got {len(line)}')
            rows.append(dict(id=line[0],file=line[1],raw=line[2].strip(),normalized=line[3].strip(),samples=int(line[5])))
    return rows

def tags(text):
    return [name for name,pattern in (('number',NUMBER),('negation',NEGATION),('condition',CONDITION)) if pattern.search(text)]

def select(source_rows,target_rows,minutes,seed):
    """One English recording per sentence id that also has a Mandarin reference."""
    targets={}
    for row in sorted(target_rows,key=lambda r:r['file']):targets.setdefault(row['id'],row)
    sources={}
    for row in sorted(source_rows,key=lambda r:r['file']):sources.setdefault(row['id'],row)
    ids=sorted(set(sources)&set(targets),key=int)
    random.Random(seed).shuffle(ids)
    # Sentences with numbers, negation or conditions go first so the stream covers them.
    ids.sort(key=lambda i:not tags(sources[i]['raw']))
    budget=minutes*60*16000;chosen=[];total=0
    tagged_budget=budget*.4
    for i in ids:
        if total>=budget:break
        if tags(sources[i]['raw']) and total>=tagged_budget:continue
        chosen.append((sources[i],targets[i]));total+=sources[i]['samples']
    if total<budget:  # fill the remainder with untagged sentences in seeded order
        used={s['id'] for s,_ in chosen}
        for i in ids:
            if total>=budget:break
            if i not in used:chosen.append((sources[i],targets[i]));total+=sources[i]['samples']
    return chosen,len(ids)

def decode(data):
    # Reuse the installed decoder: real FLEURS uses float WAV, not only PCM16.
    from faster_whisper.audio import decode_audio
    return decode_audio(io.BytesIO(data),sampling_rate=16000)

def trim(audio,threshold=1/32768,keep=1600):
    """Trim only near-digital silence; a fixed speech-level gate can erase quiet recordings."""
    window=320;n=len(audio)//window
    if not n:return audio
    rms=np.sqrt((audio[:n*window].reshape(n,window)**2).mean(axis=1))
    voiced=np.flatnonzero(rms>threshold)
    if not len(voiced):return audio
    return audio[max(0,voiced[0]*window-keep):min(len(audio),(voiced[-1]+1)*window+keep)]

# Level normalization (optional, for a second benchmark variant; the original-level variant stays the reference).
# "Active speech RMS" is a custom estimate: RMS over 20 ms frames whose RMS is within ACTIVE_RANGE_DB
# of the clip's 95th-percentile frame RMS. It is not an ITU-T P.56 measurement and makes no claim
# to conform to it. It is neither the peak nor the RMS of the whole clip, so pauses and edge noise
# do not pull it down.
ACTIVE_RANGE_DB=30
MAX_GAIN_DB=50        # never amplify near-silent clips without bound
PEAK_CEILING_DBFS=-1  # gain is reduced (not clipped or limited) if a peak would exceed this
FRAME=320
db=lambda x:round(20*math.log10(x),2) if x>0 else None

def levels(audio):
    """Peak and active-speech RMS in dBFS; active RMS is None when no frame rises above digital silence."""
    n=len(audio)//FRAME;peak=float(np.abs(audio).max()) if len(audio) else 0.
    if not n:return dict(active_rms_dbfs=None,peak_dbfs=db(peak),active_frames=0)
    frames=np.sqrt((audio[:n*FRAME].reshape(n,FRAME).astype(np.float64)**2).mean(axis=1))
    floor=max(1/32768,float(np.percentile(frames,95))*10**(-ACTIVE_RANGE_DB/20))
    active=frames[frames>=floor]
    rms=float(np.sqrt((active**2).mean())) if len(active) and float(np.percentile(frames,95))>1/32768 else 0.
    return dict(active_rms_dbfs=db(rms),peak_dbfs=db(peak),active_frames=int(len(active)) if rms else 0)

def normalize(audio,target_dbfs):
    """Scale one clip so its active-speech RMS reaches target_dbfs, within the gain cap and peak ceiling."""
    before=levels(audio);info=dict(original_active_rms_dbfs=before['active_rms_dbfs'],original_peak_dbfs=before['peak_dbfs'],
                                   gain_db=0.,gain_capped=False,peak_limited=False,no_active_speech=before['active_rms_dbfs'] is None)
    if info['no_active_speech']:return audio,{**info,'output_active_rms_dbfs':None,'output_peak_dbfs':before['peak_dbfs']}
    gain=target_dbfs-before['active_rms_dbfs']
    if gain>MAX_GAIN_DB:gain=MAX_GAIN_DB;info['gain_capped']=True
    if before['peak_dbfs'] is not None and before['peak_dbfs']+gain>PEAK_CEILING_DBFS:gain=PEAK_CEILING_DBFS-before['peak_dbfs'];info['peak_limited']=True
    out=(audio*10**(gain/20)).astype(np.float32);after=levels(out)
    return out,{**info,'gain_db':round(gain,2),'output_active_rms_dbfs':after['active_rms_dbfs'],'output_peak_dbfs':after['peak_dbfs']}

def timeline_sha256(segments):
    """Fingerprint of sentence ids, files and timing: equal across level variants built from the same inputs."""
    keys=[[s['fleurs_id'],s['file'],s['start_ms'],s['end_ms']] for s in segments]
    return hashlib.sha256(json.dumps(keys).encode()).hexdigest()

def gap_ms(rng):
    # 60% short gaps keep speech continuous (below the 896 ms pause); 40% are clear sentence pauses.
    return rng.randint(150,450) if rng.random()<.6 else rng.randint(900,1600)

def build(source_tsv,target_tsv,archive,out_dir,name,minutes,seed,revision=None,converter=None,files=None,loudness_dbfs=None,match_reference=None):
    chosen,paired=select(read_tsv(source_tsv),read_tsv(target_tsv),minutes,seed)
    wanted={s['file']:s for s,_ in chosen};clips={}
    with tarfile.open(archive,'r|gz') as tar:  # streamed: stops reading once every clip is found
        for member in tar:
            base=os.path.basename(member.name)
            if member.isfile() and base in wanted:
                clips[base]=trim(decode(tar.extractfile(member).read()))
                if len(clips)==len(wanted):break
    missing=sorted(set(wanted)-set(clips))
    if missing:raise ValueError(f'{len(missing)} selected clips are missing from the archive, e.g. {missing[0]}')
    rng=random.Random(seed+1);parts=[];segments=[];cursor=0
    for index,(source,target) in enumerate(chosen):
        if index:
            silence=np.zeros(gap_ms(rng)*16,np.float32);parts.append(silence);cursor+=len(silence)
        clip=clips[source['file']]
        # Gain is applied after trimming, so every level variant keeps identical sentence timing.
        clip,level=normalize(clip,loudness_dbfs) if loudness_dbfs is not None else (clip,{**{'original_'+k:v for k,v in levels(clip).items() if k!='active_frames'},'gain_db':0.})
        parts.append(clip)
        segments.append(dict(index=index,fleurs_id=int(source['id']),file=source['file'],start_ms=round(cursor/16,1),end_ms=round((cursor+len(clip))/16,1),
                             source=source['raw'],source_normalized=source['normalized'],reference_zh_hans=target['raw'],
                             reference_zh_tw=converter(target['raw']) if converter else None,tags=tags(source['raw']),level=level))
        cursor+=len(clip)
    timeline=timeline_sha256(segments)
    if match_reference is not None and match_reference.get('timeline_sha256',timeline_sha256(match_reference['segments']))!=timeline:
        raise ValueError('Sentence ids, order or timing differ from --match-reference; nothing was written')
    audio=np.concatenate(parts);pcm=(np.clip(audio,-1,1)*32767).astype('<i2')
    out_dir.mkdir(parents=True,exist_ok=True)
    wav_path=out_dir/(name+'.wav')
    existing=[p for p in (wav_path,out_dir/(name+'.reference.json'),out_dir/(name+'.manifest.json')) if p.exists()]
    if existing:raise FileExistsError(f'Refusing to overwrite {existing[0]}; choose another --out')
    with wave.open(str(wav_path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(pcm.tobytes())
    coverage={t:sum(t in s['tags'] for s in segments) for t in ('number','negation','condition')}
    reference=dict(dataset='google/fleurs',license='CC BY 4.0',revision=revision,files=files,source_language=SOURCE_LANG,target_language=TARGET_LANG,
                   created_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),seed=seed,paired_sentence_ids=paired,
                   duration_ms=round(len(audio)/16,1),sentences=len(segments),tag_coverage=coverage,timeline_sha256=timeline,
                   loudness=dict(variant='original level (no gain)') if loudness_dbfs is None else dict(
                       variant='custom active-speech RMS estimate normalized (not ITU-T P.56)',target_active_rms_dbfs=loudness_dbfs,active_range_db=ACTIVE_RANGE_DB,
                       max_gain_db=MAX_GAIN_DB,peak_ceiling_dbfs=PEAK_CEILING_DBFS,frame_ms=20,
                       gain_capped=sum(s['level']['gain_capped'] for s in segments),peak_limited=sum(s['level']['peak_limited'] for s in segments),
                       no_active_speech=sum(s['level']['no_active_speech'] for s in segments),
                       note='Per-clip gain only; background noise in each clip is scaled with it. Gaps stay digital silence.'),
                   zh_tw_reference='OpenCC s2twp conversion of the zh-Hans reference; Taiwan wording needs human review' if converter else None,
                   note='Synthetic concatenation of read sentences with seeded gaps; not natural live speech.',segments=segments)
    def rel(p):  # evaluate_live.mjs resolves manifest paths from the project root
        p=p.resolve()
        return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)
    ref_path=out_dir/(name+'.reference.json');ref_path.write_text(json.dumps(reference,ensure_ascii=False,indent=1),encoding='utf-8')
    manifest=dict(samples=[dict(id=name,path=rel(wav_path),language='en',kind='fleurs-concatenated',reference=rel(ref_path),
                                source=' '.join(s['source'] for s in segments))])
    manifest_path=out_dir/(name+'.manifest.json');manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=1),encoding='utf-8')
    return wav_path,ref_path,manifest_path,reference

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--minutes',type=float,default=20);parser.add_argument('--seed',type=int,default=2026)
    parser.add_argument('--revision',default='main',help='branch or 40-character commit; a branch is resolved to a commit first')
    parser.add_argument('--source-dir',help='use already downloaded files laid out as en_us/test.tsv, cmn_hans_cn/test.tsv, en_us/audio/test.tar.gz')
    parser.add_argument('--cache',default=str(ROOT/'.cache'/'fleurs'));parser.add_argument('--out',default=str(ROOT/'quality'/'eval'))
    parser.add_argument('--loudness-dbfs',type=float,help='build the level-normalized variant: target active-speech RMS in dBFS, e.g. -20')
    parser.add_argument('--match-reference',help='reference.json of the original-level build; abort unless ids, order and timing are identical')
    args=parser.parse_args()
    if args.loudness_dbfs is not None and not -40<=args.loudness_dbfs<=-6:parser.error('--loudness-dbfs must be between -40 and -6')
    match=json.loads(Path(args.match_reference).read_text(encoding='utf-8')) if args.match_reference else None
    if not 1<=args.minutes<=120:parser.error('--minutes must be between 1 and 120')
    if args.source_dir:
        if not re.fullmatch(r'[0-9a-f]{40}',args.revision):parser.error('--source-dir needs --revision <40-character commit> of the files you downloaded')
        revision=args.revision;paths={key:Path(args.source_dir)/lang/name for key,(lang,name) in FILES.items()}
    else:
        revision=resolve_revision(args.revision);cache=Path(args.cache)/revision
        paths={key:fetch(REPO.format(revision=revision,lang=lang,path=name),cache/lang/name) for key,(lang,name) in FILES.items()}
    files={key:dict(path=f'data/{FILES[key][0]}/{FILES[key][1]}',sha256=sha256(path),bytes=path.stat().st_size) for key,path in paths.items()}
    src,tgt,archive=paths['source_tsv'],paths['target_tsv'],paths['source_audio']
    try:
        from opencc import OpenCC;converter=OpenCC('s2twp').convert
    except ImportError:converter=None;print('opencc not installed: zh-TW references will be missing',file=sys.stderr)
    name=f'fleurs-en-zh-{args.minutes:g}min-seed{args.seed}'+(f'-active{args.loudness_dbfs:g}dBFS' if args.loudness_dbfs is not None else '')
    wav,ref,manifest,info=build(src,tgt,archive,Path(args.out),name,args.minutes,args.seed,revision,converter,files,args.loudness_dbfs,match)
    print(f"Built {info['sentences']} sentences, {info['duration_ms']/60000:.1f} min, revision {revision}; coverage {info['tag_coverage']}; timeline {info['timeline_sha256'][:12]}")
    if args.loudness_dbfs is not None:
        l=info['loudness'];print(f"Level: target {l['target_active_rms_dbfs']} dBFS active RMS; gain capped {l['gain_capped']}, peak limited {l['peak_limited']}, no active speech {l['no_active_speech']}")
    if manifest.resolve().is_relative_to(ROOT):print('Run: node windows/evaluate_live.mjs',manifest.resolve().relative_to(ROOT).as_posix())
    else:print('Manifest written outside the project; evaluate_live.mjs expects it under the project folder:',manifest)

if __name__=='__main__':main()
