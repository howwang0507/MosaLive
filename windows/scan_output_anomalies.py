"""Offline scan of replay results for broken translation output (no service or model).

For every final caption it reports output_anomalies() and name-like case changes from
quality_checks, next to the flags the service recorded at the time. Use it to see what the
MOSA_OUTPUT_ANOMALY_REPAIR trial would have caught; it does not judge translation meaning.
"""
import argparse,json,sys
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from quality_checks import output_anomalies,caps_words

def finals(result):
    seen={}
    for e in result.get('events',[]):
        if isinstance(e,dict) and e.get('type')=='final' and e.get('seq') not in seen:seen[e['seq']]=e
    return sorted(seen.values(),key=lambda e:e.get('speech_start_ms',0))

def scan(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    out=[]
    for result in data.get('results',[]):
        rows=[];counts=Counter()
        fin=finals(result)
        for e in fin:
            src=e.get('original') or '';zh=e.get('translation') or ''
            flags=output_anomalies(src,zh);ordinary,names=caps_words(src,zh)
            for f in flags:counts[f]+=1
            if names:counts['name_case_changed']+=1
            if flags:counts['any_anomaly']+=1
            if flags and not e.get('quality_flags'):counts['anomaly_unflagged_at_runtime']+=1
            if flags or names:
                rows.append(dict(seq=e.get('seq'),flags=flags,name_like=names,runtime_flags=e.get('quality_flags') or [],
                                 repair_attempted=bool(e.get('quality_repair_attempted')),original=src,translation=zh))
        out.append(dict(file=str(path),id=result.get('id'),finals=len(fin),counts=dict(counts),rows=rows))
    return out

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('results',nargs='+');ap.add_argument('--save');ap.add_argument('--examples',type=int,default=5)
    a=ap.parse_args(argv)
    report=[r for p in a.results for r in scan(p)]
    for r in report:
        c=r['counts'];print(f"{r['file']}  finals={r['finals']}  anomalies={c.get('any_anomaly',0)}  "
              f"unflagged_at_runtime={c.get('anomaly_unflagged_at_runtime',0)}  name_case_changed={c.get('name_case_changed',0)}")
        print('   ',{k:v for k,v in c.items() if k not in ('any_anomaly','anomaly_unflagged_at_runtime','name_case_changed')})
        for row in [x for x in r['rows'] if x['flags']][:a.examples]:
            print(f"    seq {row['seq']} {row['flags']}: {row['translation'][:70]}")
    if a.save:
        dest=Path(a.save)
        if dest.exists():sys.exit(f'refusing to overwrite {dest}')
        dest.write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding='utf-8')
    return report

if __name__=='__main__':main()
