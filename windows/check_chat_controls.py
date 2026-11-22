"""Check whether the spoken "chat" survived in evaluate_live.mjs replays of the chat controls.

  .venv-win\\Scripts\\python.exe windows\\check_chat_controls.py quality\\chat-controls-off.json quality\\chat-controls-on.json

For each sample: how many times the word "chat" appears in the finals versus the phrase, and
whether the echo guard retried. "lost after retry" counts samples where a final was re-decoded
without the prompt and the expected "chat" is then missing: the false trigger the guard must
avoid. Compare guard off and on: a "chat" lost in both runs is a recognition problem, not the guard.
"""
import argparse,json,re,sys
from pathlib import Path

CHAT=re.compile(r'\bchat\b',re.I)
CATEGORIES=('after_cut','after_pause','alone')

def check_sample(result):
    finals={}
    for e in result.get('events',[]):
        if isinstance(e,dict) and e.get('type')=='final' and e.get('seq') not in finals:finals[e['seq']]=e
    finals=list(finals.values())
    expected=len(CHAT.findall(result.get('phrase') or result.get('source','')))
    found=sum(len(CHAT.findall(e.get('original',''))) for e in finals)
    retried=[e for e in finals if e.get('asr_prompt_echo_retry')]
    kept=found>=expected
    return dict(id=result['id'],category=result.get('category'),phrase=result.get('phrase'),expected=expected,found=found,kept=kept,
                retried=len(retried),lost_after_retry=bool(retried) and not kept,
                finals=[e.get('original','') for e in finals],echo_texts=[e.get('asr_echo_text') for e in retried])

def summarize(rows):
    out={}
    for category in CATEGORIES:
        group=[r for r in rows if r['category']==category]
        out[category]=dict(samples=len(group),kept=sum(r['kept'] for r in group),lost=sum(not r['kept'] for r in group),
                           retried=sum(bool(r['retried']) for r in group),lost_after_retry=sum(r['lost_after_retry'] for r in group))
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('results',nargs='+');parser.add_argument('--save')
    args=parser.parse_args();runs={}
    for name in args.results:
        data=json.loads(Path(name).read_text(encoding='utf-8'))
        tuning=((data.get('health') or {}).get('models') or {}).get('tuning') or {}
        rows=[check_sample(r) for r in data['results']]
        runs[Path(name).stem]=dict(echo_retry=tuning.get('asr_echo_retry'),summary=summarize(rows),samples=rows)
    for label,run in runs.items():
        print(f"\n{label} (asr_echo_retry={run['echo_retry']})")
        for category,s in run['summary'].items():
            print(f"  {category:<12} samples {s['samples']:>3}  chat kept {s['kept']:>3}  lost {s['lost']:>3}  retried {s['retried']:>3}  lost after retry {s['lost_after_retry']:>3}")
        for r in run['samples']:
            if not r['kept'] or r['retried']:
                print(f"    {'LOST ' if not r['kept'] else 'kept '}{r['id']}: finals {r['finals']} | echoed {r['echo_texts']}")
    if args.save:
        path=Path(args.save)
        if path.exists():parser.error('Output already exists; choose a new filename')
        path.write_text(json.dumps(runs,ensure_ascii=False,indent=1),encoding='utf-8');print('Saved',path)

if __name__=='__main__':main()
