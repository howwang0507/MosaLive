"""Reproducible, pooled CER and utterance latency summary; no accuracy claims."""
import json,re,statistics,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]/'quality'
def normalize(s):
    return ''.join(c for c in unicodedata.normalize('NFKC',s).lower()
                   if not c.isspace() and unicodedata.category(c)[0] not in ('P','Z'))
def median(xs):return round(statistics.median(xs),1) if xs else None
def summarize(rows):
    weight=sum(len(normalize(r['source'])) for r in rows)
    errors=sum(r['cer']*len(normalize(r['source'])) for r in rows if r['cer'] is not None)
    source=[];translation=[];final=[]
    for r in rows:
        seen_source=set();seen_translation=set()
        for e in r['events']:
            if e.get('original') and e.get('seq') not in seen_source:
                seen_source.add(e['seq']);source.append(e['capture_to_caption_ms'])
            if e.get('translation') and e.get('seq') not in seen_translation:
                seen_translation.add(e['seq']);translation.append(e['capture_to_caption_ms'])
            if e['type']=='final':final.append(e['after_speech_ms'])
    return dict(cases=len(rows),pooled_cer=round(errors/weight,4) if weight else None,
                first_source_median_ms=median(source),first_translation_median_ms=median(translation),
                after_speech_median_ms=median(final),dropped_audio_ms=sum(r['metrics'].get('dropped_audio_ms',0) for r in rows),
                empty_speech_cases=[r['id'] for r in rows if r['source'] and not r['original'].strip()])
def main():
    result={}
    for name in ['baseline-0.2.0','synthetic-0.3.0','real-auto-0.3.0','real-native-0.3.0']:
        path=ROOT/(name+'.json')
        if not path.exists():continue
        rows=json.loads(path.read_text('utf-8'))['results']
        result[name]={'all':summarize(rows)}
        for lang in ('en','ja','ko'):
            selected=[r for r in rows if r.get('language',r['id'][:2])==lang]
            if selected:result[name][lang]=summarize(selected)
    (ROOT/'summary-0.3.0.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
