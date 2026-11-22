"""Score evaluate_live.mjs replays against a reference built by build_fleurs_eval.py.

  .venv-win\\Scripts\\python.exe windows\\score_eval.py quality\\eval-A.json [quality\\eval-B.json ...]

Several result files print side by side for A/B runs. Scoring is segmentation-free
where possible, so a strategy that splits one sentence into two captions is not
penalised as a translation error:
  * ASR: document WER twice. "raw" compares words as written; "numbers normalized"
    also equates spelled and written numbers (three == 3, 1,200 == 1200), and
    unit spellings (km/kilometers/kilometres, kg/kilograms, GHz/gigahertz, %/percent). Signs and
    decimals stay part of the token in both (-3 != 3, 3.5 != 3 5).
  * Translation: document-level chrF (character 1-6 grams, beta 2) against the
    zh-TW reference. chrF is only a similarity aid: a dropped "不" barely moves it.
  * Per reference sentence, using captions whose audio truly overlaps it:
    numeric values (magnitudes and decimals; a negative reference value is flagged
    because its sign is not machine-checked in Chinese) and negation markers.
    A sentence only touched within 200 ms of a caption edge is "boundary only":
    its checks are not run and it is listed for review, never counted as covered.
    These are review flags, not a meaning score.
  * Availability: the time a final (or a translated preview) became available to
    the client, on the replay's audio clock. It is not when a viewer saw it on screen:
    Chrome capture, message passing and painting are not included.
    "Reference clip end -> last related final available" (since scorer 2026-10-24.2):
    for each covered sentence, the latest-ending final overlapping it, minus the end of
    the reference audio clip. The clip end includes the recording's own trailing room
    noise, so this is NOT the delay after the speaker stopped; negative values (final
    available before the clip ended) are kept and counted, never clipped to zero.
    A negative value is not a negative delay: usually the final was ready before the
    clip's trailing background sound ended.
    The older "final within 300 ms of clip end" metric is kept as legacy; its numbers
    are not comparable with the new one.
    Since scorer 2026-10-24.3 the translation number check uses the service's
    translation_numbers(): more Chinese measure words are read as counts and the value
    1 is ignored (one/a vs 之一/一個). Its counts are not comparable with 2026-10-24.2.
  * Latency comparability (since 2026-10-25.1, every pair of runs): settings and
    machine speed are judged separately. Machine speed uses Ollama tokens/s and the
    run's own ASR time; a proxy is skipped when a differing setting can change it
    (translation model -> tokens/s; ASR model, device, ASR mode or any tuning key ->
    ASR time). Results: "comparable" (same settings, similar speed); "A/B on <keys>"
    (only those settings differ and the remaining speed proxies agree, so a latency
    difference can be attributed to them, confounded if several keys differ);
    "machine speed differs"; "insufficient data" (too few samples or no usable proxy).
    A difference above 10% is an empirical warning level, not a statistical test.
    Quality metrics (WER, chrF, coverage, flags, repair counts) are not affected.
  * ASR by original level: per-sentence errors from one document alignment, grouped
    by the reference's original active-speech level (thirds), when the reference
    records levels. It shows a correlation only; a level-normalized rerun on the same
    sentences is what measures the effect of volume.
Percentiles are nearest-rank (index ceil(n*q)-1), the same as summarize_evaluation.py
and evaluate_live.mjs.
"""
import argparse,json,math,re,sys,unicodedata
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from quality_checks import numbers,translation_numbers,ENGLISH_NUMBERS,english_number

ROOT=Path(__file__).resolve().parents[1]
SCORER_VERSION='2026-11-07.1'
# Latency comparability (scorer 2026-10-24.4). An empirical warning level, not a statistical test:
# runs whose model throughput or ASR time differ by more than this are not compared on latency.
SPEED_WARNING_RATIO=.10
MIN_OLLAMA_CALLS=50      # health_after keeps at most the last 200 completed calls
MIN_ASR_SAMPLES=30       # finals with their own ASR pass (not reused from a pause preview)
ZH_NEGATION=re.compile('[不沒没未別别無无非勿否]')
ZH_NEGATIVE_VALUE=re.compile('負|负|零下|減|减')
TOKEN=re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?|[a-z0-9]+(?:'[a-z0-9]+)*")
SIGNED=re.compile(r'(?<![\w.])-\d+(?:\.\d+)?|\b(?:minus|negative)\s+\w+|\bbelow zero\b')
BOUNDARY_MS=200

def tokens(text,normalize_numbers):
    text=unicodedata.normalize('NFKC',text).lower().replace('’',"'")
    if normalize_numbers:
        text=ENGLISH_NUMBERS.sub(english_number,re.sub(r'\ba(?=[- ]+(?:hundred|thousand|million|billion)\b)','one',text))
        text=re.sub(r'(?<=\d),(?=\d{3}(?!\d))','',text).replace('%',' percent')
        # Only spelling aliases, never scale conversions (kg != km; signs stay).
        text=re.sub(r'(?<![a-z])kilomet(?:er|re)s?(?![a-z])','km',text)
        text=re.sub(r'(?<![a-z])kilograms?(?![a-z])','kg',text)
        text=re.sub(r'(?<![a-z])gigahertz(?![a-z])','ghz',text)
    return TOKEN.findall(text)

def edit_distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        prev,row[0]=row[0],i
        for j,y in enumerate(b,1):prev,row[j]=row[j],min(row[j]+1,row[j-1]+1,prev+(x!=y))
    return row[-1]

def wer(reference,hypothesis,normalize_numbers):
    ref=tokens(reference,normalize_numbers);hyp=tokens(hypothesis,normalize_numbers)
    return round(edit_distance(ref,hyp)/len(ref),4) if ref else None

def sentence_errors(segments,finals):
    """Attribute word errors to reference sentences via one document-level alignment."""
    ref=[(t,i) for i,s in enumerate(segments) for t in tokens(s['source'],True)]
    hyp=[t for e in finals for t in tokens(e.get('original',''),True)]
    rt=[t for t,_ in ref];n,m=len(rt),len(hyp)
    table=[list(range(m+1))]
    for i in range(1,n+1):
        prev=table[-1];row=[i]+[0]*m;a=rt[i-1]
        for j in range(1,m+1):row[j]=min(prev[j]+1,row[j-1]+1,prev[j-1]+(a!=hyp[j-1]))
        table.append(row)
    errors=[0]*len(segments);words=[0]*len(segments);i,j=n,m;last=len(segments)-1
    while i>0 or j>0:
        if i>0 and j>0 and table[i][j]==table[i-1][j-1]+(rt[i-1]!=hyp[j-1]):
            k=ref[i-1][1];words[k]+=1;errors[k]+=rt[i-1]!=hyp[j-1];last=k;i-=1;j-=1
        elif i>0 and table[i][j]==table[i-1][j]+1:k=ref[i-1][1];words[k]+=1;errors[k]+=1;last=k;i-=1
        else:errors[last]+=1;j-=1   # insertion: charged to the neighbouring reference sentence
    return errors,words

def zh_chars(text):
    return [c for c in unicodedata.normalize('NFKC',text) if not (c.isspace() or unicodedata.category(c)[0] in 'PZS')]

def chrf(hypothesis,reference,order=6,beta=2):
    """Document-level chrF in percent (character n-grams, whitespace and punctuation removed)."""
    hyp,ref=zh_chars(hypothesis),zh_chars(reference);precisions=[];recalls=[]
    for n in range(1,order+1):
        h=Counter(tuple(hyp[i:i+n]) for i in range(len(hyp)-n+1));r=Counter(tuple(ref[i:i+n]) for i in range(len(ref)-n+1))
        if not h or not r:continue
        match=sum((h&r).values());precisions.append(match/sum(h.values()));recalls.append(match/sum(r.values()))
    if not precisions:return 0.
    p,r=sum(precisions)/len(precisions),sum(recalls)/len(recalls)
    return 0. if not p+r else round(100*(1+beta**2)*p*r/(beta**2*p+r),2)

def pct(values,q):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    return round(values[max(0,math.ceil(len(values)*q)-1)],1) if values else None

def norm_zh(text):return ''.join(zh_chars(text or ''))
def join(events,key):return ' '.join(e.get(key,'') for e in events)

def score(result,reference):
    events=[e for e in result.get('events',[]) if isinstance(e,dict)]
    finals={}
    for e in events:
        if e.get('type')=='final' and e.get('seq') not in finals:finals[e['seq']]=e
    finals=sorted(finals.values(),key=lambda e:e.get('speech_start_ms',0))
    available=lambda e:(e.get('capture_to_caption_ms') or 0)+e.get('speech_start_ms',0)  # audio-clock time the client had the event
    segments=reference['segments']
    source=' '.join(s['source'] for s in segments);heard=join(finals,'original')
    zh_ref=''.join(s.get('reference_zh_tw') or s['reference_zh_hans'] for s in segments)
    per=[];latency=[];clip_end=[]
    for s in segments:
        overlap=[e for e in finals if e.get('speech_end_ms',0)>s['start_ms'] and e.get('speech_start_ms',0)<s['end_ms']]
        near=[e for e in finals if e not in overlap and e.get('speech_end_ms',0)>s['start_ms']-BOUNDARY_MS and e.get('speech_start_ms',0)<s['end_ms']+BOUNDARY_MS]
        coverage='covered' if overlap else 'boundary_only' if near else 'missing'
        item=dict(index=s['index'],fleurs_id=s['fleurs_id'],coverage=coverage,asr_missing_numbers=None,translation_missing_numbers=None,
                  asr_sign_changed=None,negative_value_needs_review=False,negation_without_zh_marker=None,clip_end_to_last_final_ms=None)
        if overlap:
            expected=numbers(s['source']);said=join(overlap,'translation');spoken=join(overlap,'original')
            item['asr_missing_numbers']=sorted((expected-numbers(spoken)).elements())
            item['translation_missing_numbers']=sorted((translation_numbers(s['source'])-translation_numbers(said)).elements())
            signed=Counter(t.replace(' ','') for t in SIGNED.findall(s['source'].lower()))
            item['asr_sign_changed']=bool(signed-Counter(t.replace(' ','') for t in SIGNED.findall(spoken.lower())))
            item['negative_value_needs_review']=bool(signed) and not ZH_NEGATIVE_VALUE.search(said)
            item['negation_without_zh_marker']='negation' in s['tags'] and not ZH_NEGATION.search(said)
            ending=[e for e in overlap if e.get('speech_end_ms',0)>=s['end_ms']-300]
            if ending:latency.append(min(available(e) for e in ending)-s['end_ms'])   # legacy rule
            last=max(overlap,key=lambda e:e.get('speech_end_ms',0))
            item['clip_end_to_last_final_ms']=round(available(last)-s['end_ms'],1);clip_end.append(item['clip_end_to_last_final_ms'])
        item['needs_review']=coverage!='covered' or bool(item['asr_missing_numbers'] or item['translation_missing_numbers'] or item['asr_sign_changed']
                                                        or item['negative_value_needs_review'] or item['negation_without_zh_marker'])
        per.append(item)
    by_reason={}
    for e in finals:by_reason.setdefault(e.get('endpoint_reason','unknown'),[]).append(e)
    previews=[];stable=[]
    for f in finals:
        group=[e for e in events if e.get('type')=='partial' and e.get('seq')==f['seq'] and e.get('translation')]
        for subset,bucket in ((group,previews),([e for e in group if e.get('phase')=='stable'],stable)):
            if subset:
                first=subset[0];final_text=norm_zh(f.get('translation'))
                bucket.append(dict(gain=available(f)-available(first),same=norm_zh(first['translation'])==final_text,
                                   prefix=final_text.startswith(norm_zh(first['translation'])),updates=len(subset)))
    def preview_stats(rows):
        if not rows:return dict(captions=0)
        return dict(captions=len(rows),share_of_finals=round(len(rows)/len(finals),3),
                    available_earlier_ms_p50=pct([r['gain'] for r in rows],.5),available_earlier_ms_p95=pct([r['gain'] for r in rows],.95),
                    first_equals_final=round(sum(r['same'] for r in rows)/len(rows),3),final_not_prefixed_by_first=round(sum(not r['prefix'] for r in rows)/len(rows),3),
                    updates_p50=pct([r['updates'] for r in rows],.5))
    metrics=result.get('metrics') or {}
    restarts=(metrics.get('reconnects') or 0)+(metrics.get('playback_reset_count') or 0)+(metrics.get('overflow_count') or 0)
    count=lambda key:sum(bool(p[key]) for p in per)
    by_level=None
    if segments and all((s.get('level') or {}).get('original_active_rms_dbfs') is not None for s in segments):
        errors,word_counts=sentence_errors(segments,finals)
        order=sorted(range(len(segments)),key=lambda k:segments[k]['level']['original_active_rms_dbfs']);third=math.ceil(len(order)/3);by_level=[]
        for name,group in zip(('quietest third','middle third','loudest third'),(order[:third],order[third:2*third],order[2*third:])):
            if group:by_level.append(dict(group=name,sentences=len(group),max_original_active_rms_dbfs=segments[group[-1]]['level']['original_active_rms_dbfs'],
                                          wer=round(sum(errors[k] for k in group)/max(1,sum(word_counts[k] for k in group)),4)))
    return dict(
        run=dict(scorer_version=SCORER_VERSION,sample=result.get('id'),asr_mode=result.get('asrMode'),endpoint_mode=result.get('endpointMode'),
                 reference_timeline=reference.get('timeline_sha256'),loudness=(reference.get('loudness') or {}).get('variant','unrecorded'),
                 tuning=((result.get('health') or {}).get('models') or {}).get('tuning'),
                 alignment_warning=bool(restarts or metrics.get('dropped_audio_ms')),dropped_audio_ms=metrics.get('dropped_audio_ms')),
        asr=dict(wer_raw=wer(source,heard,False),wer_numbers_normalized=wer(source,heard,True),reference_tokens=len(tokens(source,False)),by_original_level=by_level),
        translation=dict(chrf_document=chrf(join(finals,'translation'),zh_ref),reference='zh-TW (OpenCC from zh-Hans)' if segments and segments[0].get('reference_zh_tw') else 'zh-Hans'),
        checks=dict(sentences=len(segments),covered=sum(p['coverage']=='covered' for p in per),boundary_only=sum(p['coverage']=='boundary_only' for p in per),
                    missing=sum(p['coverage']=='missing' for p in per),asr_number_misses=count('asr_missing_numbers'),
                    translation_number_misses=count('translation_missing_numbers'),asr_sign_changes=count('asr_sign_changed'),
                    negative_values_to_review=count('negative_value_needs_review'),negation_without_marker=count('negation_without_zh_marker'),
                    needs_review=[p['index'] for p in per if p['needs_review']]),
        availability=dict(note='audio-clock time the client received the event; not on-screen time',
                          capture_to_caption_ms_p50=pct([e.get('capture_to_caption_ms') for e in finals],.5),
                          capture_to_caption_ms_p95=pct([e.get('capture_to_caption_ms') for e in finals],.95),
                          after_speech_ms_p50=pct([e.get('after_speech_ms') for e in finals],.5),after_speech_ms_p95=pct([e.get('after_speech_ms') for e in finals],.95),
                          clip_end_to_last_final_ms_p50=pct(clip_end,.5),clip_end_to_last_final_ms_p95=pct(clip_end,.95),
                          clip_end_to_last_final_measured=len(clip_end),clip_end_to_last_final_negative=sum(v<0 for v in clip_end),
                          legacy_note='final ending within 300 ms of the clip end; not comparable with clip_end_to_last_final',
                          sentence_end_to_final_ms_p50=pct(latency,.5),sentence_end_to_final_ms_p95=pct(latency,.95),measured_sentences=len(latency),
                          finals=len(finals),by_endpoint={k:dict(count=len(v),capture_to_caption_ms_p50=pct([e.get('capture_to_caption_ms') for e in v],.5),
                                                               capture_to_caption_ms_p95=pct([e.get('capture_to_caption_ms') for e in v],.95),
                                                               after_speech_ms_p50=pct([e.get('after_speech_ms') for e in v],.5)) for k,v in sorted(by_reason.items())}),
        preview_shadow=dict(note='translated previews the client received; display rules decide what a viewer would see',
                            any_translation=preview_stats(previews),stable_phase=preview_stats(stable)),
        ollama_after_run=((result.get('health_after') or {}).get('models') or {}).get('ollama'),
        speed=speed_profile(result,finals),
        sentences=per)

def speed_profile(result,finals):
    """Settings and machine-speed indicators used only to judge whether latency can be compared."""
    models=((result.get('health') or {}).get('models') or {})
    after=((result.get('health_after') or {}).get('models') or {})
    ollama=after.get('ollama') or {}
    asr=[e.get('asr_ms') for e in finals if not e.get('asr_reused_from_pause') and isinstance(e.get('asr_ms'),(int,float)) and e['asr_ms']>0]
    return dict(settings=dict(translation=models.get('translation'),asr=models.get('asr'),device=models.get('device'),tuning=models.get('tuning'),
                              asr_mode=result.get('asrMode'),endpoint_mode=result.get('endpointMode')),
                ollama_tokens_per_second_p50=ollama.get('tokens_per_second_p50'),ollama_calls=ollama.get('calls') or 0,
                asr_ms_p50=pct(asr,.5),asr_samples=len(asr))

def flat_settings(settings):
    flat={k:v for k,v in settings.items() if k!='tuning'}
    flat.update({f'tuning.{k}':v for k,v in (settings.get('tuning') or {}).items()})
    return flat

def latency_comparability(baseline,other):
    """Judge settings and machine speed separately; see the module docstring for the statuses."""
    a,b=baseline['speed'],other['speed'];sa,sb=flat_settings(a['settings']),flat_settings(b['settings'])
    differ=sorted(k for k in set(sa)|set(sb) if sa.get(k)!=sb.get(k))
    proxies=[]
    if 'translation' not in differ:proxies.append(('ollama_tokens_per_second_p50','Ollama tokens/s p50','ollama_calls',MIN_OLLAMA_CALLS,'Ollama calls'))
    if not any(k in ('asr','device','asr_mode') or k.startswith('tuning.') for k in differ):
        proxies.append(('asr_ms_p50','own ASR p50','asr_samples',MIN_ASR_SAMPLES,'finals with their own ASR'))
    if not proxies:return dict(status='insufficient data',settings_differ=differ,reasons=['no speed proxy is independent of the differing settings'])
    reasons=[f'{label}: fewer than {minimum} {what}' for key,_,count,minimum,what in proxies for label,run in (('first',a),('second',b))
             if run[count]<minimum or run[key] is None]
    if reasons:return dict(status='insufficient data',settings_differ=differ,reasons=reasons)
    for key,label,*_ in proxies:
        change=b[key]/a[key]-1
        if abs(change)>SPEED_WARNING_RATIO:reasons.append(f'{label} {a[key]} -> {b[key]} ({change:+.0%})')
    used=[label for _,label,*_ in proxies]
    if reasons:return dict(status='machine speed differs',settings_differ=differ,speed_proxies=used,reasons=reasons)
    if not differ:return dict(status='comparable',settings_differ=[],speed_proxies=used,reasons=[])
    return dict(status='A/B on '+', '.join(differ)+(' (confounded)' if len(differ)>1 else ''),settings_differ=differ,speed_proxies=used,reasons=[])

ROWS=[('ASR WER raw','asr','wer_raw'),('ASR WER numbers normalized','asr','wer_numbers_normalized'),('chrF document','translation','chrf_document'),
      ('sentences covered','checks','covered'),('boundary only (review)','checks','boundary_only'),('missing sentences','checks','missing'),
      ('ASR number misses','checks','asr_number_misses'),('ASR sign changes','checks','asr_sign_changes'),
      ('translation number misses','checks','translation_number_misses'),('negative values to review','checks','negative_values_to_review'),
      ('negation without 不/沒…','checks','negation_without_marker'),
      ('capture -> final p50 (all finals)','availability','capture_to_caption_ms_p50'),('capture -> final p95','availability','capture_to_caption_ms_p95'),
      ('after speech -> final p50','availability','after_speech_ms_p50'),('after speech -> final p95','availability','after_speech_ms_p95'),
      ('clip end -> last final available p50','availability','clip_end_to_last_final_ms_p50'),
      ('clip end -> last final available p95','availability','clip_end_to_last_final_ms_p95'),
      ('  measured sentences','availability','clip_end_to_last_final_measured'),('  negative (kept, not clipped)','availability','clip_end_to_last_final_negative'),
      ('legacy end->final p50 (not comparable)','availability','sentence_end_to_final_ms_p50'),('  legacy measured','availability','measured_sentences'),
      ('finals','availability','finals')]

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('results',nargs='+');parser.add_argument('--reference');parser.add_argument('--save')
    args=parser.parse_args();reports={}
    for name in args.results:
        data=json.loads(Path(name).read_text(encoding='utf-8'))
        for result in data['results']:
            result.setdefault('health',data.get('health'));result.setdefault('health_after',data.get('health_after'))  # stored once per file
            ref_path=Path(args.reference or ROOT/result['reference'])
            reports[f"{Path(name).stem}:{result['id']}"]=score(result,json.loads(ref_path.read_text(encoding='utf-8')))
    labels=list(reports);width=max(24,*(len(l) for l in labels))
    print('metric'.ljust(40)+''.join(l[-width:].rjust(width+2) for l in labels))
    for title,group,key in ROWS:print(title.ljust(40)+''.join(str(reports[l][group][key]).rjust(width+2) for l in labels))
    for kind,name in (('any_translation','any'),('stable_phase','stable')):
        for key,title in (('share_of_finals','share of finals'),('available_earlier_ms_p50','earlier p50 ms'),('final_not_prefixed_by_first','final rewrites first')):
            print(f'preview {name}: {title}'.ljust(40)+''.join(str(reports[l]['preview_shadow'][kind].get(key)).rjust(width+2) for l in labels))
    for label,report in reports.items():
        for row in report['asr']['by_original_level'] or []:print(f"{label}: WER {row['wer']} for {row['group']} (original active RMS <= {row['max_original_active_rms_dbfs']} dBFS, {row['sentences']} sentences)")
    if len(labels)>1:
        print('Latency comparability, every pair (empirical 10% warning level, not a statistical test; quality metrics are not affected):')
        pairs={}
        for i,first in enumerate(labels):
            for second in labels[i+1:]:
                check=latency_comparability(reports[first],reports[second]);pairs[f'{first} | {second}']=check
                proxies=f" [speed by {', '.join(check.get('speed_proxies',[]))}]" if check.get('speed_proxies') else ''
                print(f"  {first} vs {second}: {check['status']}{proxies}"+(f" ({'; '.join(check['reasons'])})" if check['reasons'] else ''))
        for report in reports.values():report['latency_comparability_pairs']=pairs
    timelines={r['run']['reference_timeline'] for r in reports.values()}
    if len(timelines)>1:print('WARNING: these runs use different sentence timelines; do not compare them directly.')
    print(f'Scorer {SCORER_VERSION}. Availability is the audio-clock time the client received events, not when a viewer saw them on screen.')
    for label,report in reports.items():
        if report['run']['alignment_warning']:print(f'WARNING {label}: the stream restarted or dropped audio, so sentence alignment is approximate.')
        ollama=report['ollama_after_run']
        if ollama:print(f"{label}: Ollama last {ollama.get('calls')} calls (bounded window, may not span the whole run): {ollama.get('tokens_per_second_p50')} tokens/s p50")
        print(f"{label}: tuning {report['run']['tuning']}; review sentences {report['checks']['needs_review'][:20]}")
    if args.save:
        path=Path(args.save)
        if path.exists():parser.error('Output already exists; choose a new filename')
        path.write_text(json.dumps(reports,ensure_ascii=False,indent=1),encoding='utf-8');print('Saved',path)

if __name__=='__main__':main()
