"""Summarize saved evaluations without mistaking CER for translation accuracy."""
import json,sys,math,unicodedata
from pathlib import Path

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC',text).lower()
                   if not c.isspace() and unicodedata.category(c)[0] not in 'PZ')

def percentile(values,p):
    values=sorted(v for v in values if isinstance(v,(int,float)) and math.isfinite(v))
    return round(values[max(0,math.ceil(len(values)*p)-1)],1) if values else None

def summarize(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'));rows=data['results']
    first_source=[];first_translation=[];finals=[]
    for row in rows:
        source_seen=set();translation_seen=set()
        for event in row.get('events',[]):
            seq=event.get('seq')
            if event.get('original') and seq not in source_seen:
                source_seen.add(seq);first_source.append(event.get('capture_to_caption_ms'))
            if event.get('translation') and seq not in translation_seen:
                translation_seen.add(seq);first_translation.append(event.get('capture_to_caption_ms'))
            if event.get('type')=='final':finals.append(event)
    chars=sum(len(normalized(row.get('source',''))) for row in rows)
    errors=sum((row.get('cer') or 0)*len(normalized(row.get('source',''))) for row in rows)
    return dict(cases=len(rows),code_revision=data.get('health',{}).get('models',{}).get('code_revision'),
                pooled_source_cer=round(errors/chars,4) if chars else None,
                first_source_p50_ms=percentile(first_source,.5),first_translation_p50_ms=percentile(first_translation,.5),
                after_speech_p50_ms=percentile([e.get('after_speech_ms') for e in finals],.5),
                after_speech_p95_ms=percentile([e.get('after_speech_ms') for e in finals],.95),
                dropped_audio_ms=sum(r.get('metrics',{}).get('dropped_audio_ms',0) for r in rows),
                duplicate_finals=sum(r.get('duplicate_finals',0) for r in rows),
                unexpected_speech_cases=sum(bool(r.get('unexpected_speech')) for r in rows),
                flagged_finals=sum(bool(e.get('needs_human_review')) for e in finals),
                note='Replay diagnostics, not Twitch rendering or a translation accuracy score.')

if __name__=='__main__':
    print(json.dumps({path:summarize(path) for path in sys.argv[1:]},ensure_ascii=False,indent=2))
