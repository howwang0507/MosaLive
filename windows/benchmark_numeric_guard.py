"""Opt-in controlled pipeline benchmark, never a real-model speed claim."""
import argparse,asyncio,importlib.util,json,statistics,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

async def measure(baseline):
    spec=importlib.util.spec_from_file_location('numeric_probe',ROOT/'tests/test_numeric_translation.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    old={}
    source=subprocess.check_output(['git','show',baseline+':windows/quality_checks.py'],cwd=ROOT)
    exec(compile(source,'baseline_quality_checks.py','exec'),old)
    rows={'baseline':[],'current':[]}
    # Warm imports, then alternate order to reduce order bias.
    await probe.numeric_translation_probe()
    for _ in range(5):
        for name,guard in [('baseline',old['quality_flags']),('current',None)]:
            event,calls=await probe.numeric_translation_probe(guard)
            rows[name].append({'calls':calls,'nmt_ms':round(event['nmt_ms'],3),
                               'repair':event.get('quality_repair_attempted',False),
                               'numeric_flags':event['quality_flags'].count('number_mismatch')})
    return {'mode':'synthetic ASGI pipeline; fixed 20ms fake inference; no real ASR or LLM',
            'baseline_ref':baseline,'runs':rows,
            'median_nmt_ms':{name:round(statistics.median(r['nmt_ms'] for r in runs),3) for name,runs in rows.items()}}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref',required=True)
    args=parser.parse_args()
    print(json.dumps(asyncio.run(measure(args.baseline_ref)),indent=2))
