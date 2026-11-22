"""Translation-only benchmark: FLEURS reference English -> Ollama, no ASR, no replay.

Isolates the translator from recognition errors so prompt or model variants can be compared
in minutes. Each variant changes exactly one thing in the production system prompt built by
models.translation_messages(); a variant whose target sentence is missing from the current
prompt raises instead of silently testing the unmodified prompt.

Measured per call: output_anomalies() and name-like case changes, the existing number and
negation flags, sentence chrF against the zh-TW reference, eval tokens and wall time. chrF is
character similarity, not translation accuracy; flags request review, they are not errors.

Example (Windows, needs Ollama running; no MosaLive service):
  .venv-gpu-test\\Scripts\\python.exe windows/translation_bench.py --reference <reference.json>
      --variants baseline caps_rule acronym_reword --repeats 2 --out quality/translation-bench-<date>
"""
import argparse,json,sys,time
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from quality_checks import output_anomalies,caps_words,quality_flags
from score_eval import chrf,pct

ACRONYM_CLAUSE='Keep Latin text only for proper names, product or game titles, acronyms, URLs, or an explicit glossary target.'
VARIANTS={
    'baseline':'Production prompt unchanged.',
    'caps_rule':'Append one sentence forbidding ALL-CAPS for words the source does not capitalize.',
    'acronym_reword':'Reword the Latin-text clause so acronyms are only those already written in capitals in the source.',
}

def apply_variant(messages,variant):
    messages=[dict(m) for m in messages];system=messages[0]['content']
    if variant=='baseline':pass
    elif variant=='caps_rule':
        system+=' Never write an English word in ALL CAPS unless the source writes it in capitals; translate it instead.'
    elif variant=='acronym_reword':
        if ACRONYM_CLAUSE not in system:raise ValueError('acronym clause not found in the current prompt')
        system=system.replace(ACRONYM_CLAUSE,'Keep Latin text only for proper names, product or game titles, URLs, an explicit glossary target, '
                              'or acronyms that the source itself writes in capital letters (such as NASA or GPU).')
    else:raise ValueError(f'unknown variant {variant}')
    messages[0]['content']=system
    return messages

def summarize(rows):
    out={}
    for variant in dict.fromkeys(r['variant'] for r in rows):
        rs=[r for r in rows if r['variant']==variant];c=Counter()
        for r in rs:
            for f in r['anomalies']:c[f]+=1
            c['any_anomaly']+=bool(r['anomalies']);c['name_case_changed']+=bool(r['name_like'])
            for f in r['flags']:c[f]+=1
            c['errors']+=bool(r.get('error'))
        chrfs=[r['chrf'] for r in rs if r.get('chrf') is not None];walls=[r['wall_ms'] for r in rs if r.get('wall_ms')]
        out[variant]=dict(calls=len(rs),counts=dict(c),chrf_mean=round(sum(chrfs)/len(chrfs),2) if chrfs else None,
                          wall_ms_p50=pct(walls,.5),wall_ms_p95=pct(walls,.95))
    return out

def run(segments,variants,repeats,translate,progress=None):
    """translate(messages)->dict(text, done_reason, eval_tokens, wall_ms, error). Order: repeat, variant, sentence."""
    from models import translation_messages  # production prompt; imported lazily so tests can stub it
    rows=[]
    for rep in range(repeats):
        for variant in variants:
            for i,s in enumerate(segments):
                src=s['source'];ref=s.get('reference_zh_tw') or s.get('reference_zh_hans') or ''
                res=translate(apply_variant(translation_messages(src,[],[]),variant))
                zh=res.get('text') or ''
                ordinary,names=caps_words(src,zh)
                rows.append(dict(variant=variant,repeat=rep,index=i,source=src,translation=zh,reference=ref,
                                 anomalies=output_anomalies(src,zh),name_like=names,
                                 flags=quality_flags(src,zh,'en',(),anomalies=False),chrf=chrf(zh,ref) if zh and ref else None,
                                 **{k:res.get(k) for k in ('done_reason','eval_tokens','wall_ms','error')}))
                if progress:progress(len(rows))
    return rows

def ollama_translate(model,keep_alive='30m'):
    import httpx
    from models import convert
    def call(messages):
        started=time.monotonic();text='';last={}
        try:
            with httpx.stream('POST','http://127.0.0.1:11434/api/chat',timeout=httpx.Timeout(60,connect=3),json={
                'model':model,'messages':messages,'stream':True,'keep_alive':keep_alive,
                'options':{'temperature':0,'num_ctx':2048,'num_predict':160}}) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:continue
                    e=json.loads(line)
                    if e.get('error'):raise RuntimeError(e['error'])
                    text+=e.get('message',{}).get('content','')
                    if e.get('done'):last=e
        except Exception as error:
            return dict(text=convert.convert(text.strip()),error=f'{type(error).__name__}: {error}',wall_ms=round((time.monotonic()-started)*1000,1))
        return dict(text=convert.convert(text.strip()),done_reason=last.get('done_reason'),eval_tokens=last.get('eval_count'),
                    wall_ms=round((time.monotonic()-started)*1000,1))
    return call

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reference',required=True);ap.add_argument('--out',required=True)
    ap.add_argument('--variants',nargs='+',default=['baseline'],choices=list(VARIANTS))
    ap.add_argument('--repeats',type=int,default=2);ap.add_argument('--model',default='qwen2.5:7b')
    ap.add_argument('--limit',type=int,help='first N sentences only (smoke test)')
    a=ap.parse_args(argv)
    out=Path(a.out)
    if out.exists():sys.exit(f'refusing to overwrite {out}')
    segments=json.loads(Path(a.reference).read_text(encoding='utf-8'))['segments'][:a.limit]
    for v in a.variants:apply_variant([{'role':'system','content':__import__('models').translation_messages('x',[],[])[0]['content']}],v)
    total=len(segments)*len(a.variants)*a.repeats
    rows=run(segments,a.variants,a.repeats,ollama_translate(a.model),lambda n:print(f'\r{n}/{total}',end='',flush=True))
    print();out.mkdir(parents=True)
    with open(out/'calls.jsonl','w',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary=dict(model=a.model,variants={v:VARIANTS[v] for v in a.variants},repeats=a.repeats,sentences=len(segments),
                 reference=a.reference,summary=summarize(rows))
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=1),encoding='utf-8')
    for v,s in summary['summary'].items():print(v,json.dumps(s,ensure_ascii=False))
    return summary

if __name__=='__main__':main()
