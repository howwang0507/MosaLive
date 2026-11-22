"""Read-only speed snapshot: per-caption stage timings and whether the translator is fully on the GPU.

Run while captions are active, before and after a tuning change:
  .venv-win\Scripts\python.exe windows\speed_report.py --save quality\speed-before.json
"""
import argparse,json,shutil,subprocess,time,urllib.request
from pathlib import Path

def run(command):
    try:return subprocess.run(command,capture_output=True,text=True,timeout=10).stdout.strip()
    except (OSError,subprocess.SubprocessError):return None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--save',help='write the snapshot to a new JSON file')
    args=parser.parse_args()
    with urllib.request.urlopen('http://localhost:8787/health',timeout=4) as response:health=json.load(response)
    models=health.get('models',health)
    placement=models.get('translation_placement') or {};timing=models.get('timing') or {}
    gpu=run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits']) if shutil.which('nvidia-smi') else None
    ollama_ps=run(['ollama','ps']) if shutil.which('ollama') else None
    print('Translator:',models.get('translation'),'| ASR:',models.get('asr'),'on',models.get('device'))
    share=placement.get('gpu_share')
    if share is None:print('Translator on GPU: unknown -',placement.get('note','not checked yet'))
    else:
        print(f"Translator on GPU: {share:.0%} ({placement.get('vram_mib')}/{placement.get('size_mib')} MiB, context {placement.get('context_length')})")
        if share<.99:print('  -> Part of the model runs on CPU, which is much slower. Run SET_OLLAMA_SPEED.bat and restart Ollama, or try a smaller model.')
    if not timing.get('captions'):print('No captions measured yet. Play a video with captions on, then run this again.')
    else:
        rate=timing.get('repair_rate')
        print(f"Captions: {timing['captions']} (translated {timing['translated']}); second-pass repair rate: {'-' if rate is None else f'{rate:.0%}'}")
        for key,label in (('asr_ms','ASR'),('nmt_queue_ms','Translation queue'),('nmt_ms','Translation')):
            print(f"  {label:<18} p50 {timing.get(key+'_p50')} ms   p95 {timing.get(key+'_p95')} ms")
    metrics=models.get('metrics') or {};tuning=models.get('tuning') or {}
    speculation={k:metrics.get(k,0) for k in ('speculative_translations','speculative_translation_reused','speculative_asr_reused')}
    if tuning:print('Tuning:',', '.join(f'{k}={v}' for k,v in tuning.items()))
    ollama=models.get('ollama') or {}
    if ollama.get('calls'):
        print(f"Ollama ({ollama['calls']} recent calls) p50/p95 ms: first token {ollama.get('first_token_ms_p50')}/{ollama.get('first_token_ms_p95')}, "
              f"load {ollama.get('load_ms_p50')}/{ollama.get('load_ms_p95')}, prompt {ollama.get('prompt_ms_p50')}/{ollama.get('prompt_ms_p95')} "
              f"({ollama.get('prompt_tokens_p50')} tokens), generate {ollama.get('eval_ms_p50')}/{ollama.get('eval_ms_p95')} "
              f"({ollama.get('eval_tokens_p50')} tokens, {ollama.get('tokens_per_second_p50')} tokens/s; last {ollama.get('window')} calls only)")
    endpoints=metrics.get('endpoint_counts') or {}
    if endpoints:print('Caption endings (since service start):',', '.join(f'{k}={v}' for k,v in sorted(endpoints.items())))
    if any(speculation.values()):
        made=speculation['speculative_translations']
        print(f"Pause speculation (since service start): {made} translations at pauses, {speculation['speculative_translation_reused']} reused by finals, ASR reused {speculation['speculative_asr_reused']} times")
    if gpu:print('GPU memory used/total MiB, utilization %:',gpu)
    if ollama_ps:print(ollama_ps)
    if args.save:
        path=Path(args.save)
        if path.exists():parser.error('Output already exists; choose a new filename')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(dict(at=time.time(),translator=models.get('translation'),asr=models.get('asr'),device=models.get('device'),
                                        placement=placement,timing=timing,tuning=tuning,speculation=speculation,endpoint_counts=endpoints,ollama=ollama,gpu=gpu,ollama_ps=ollama_ps),ensure_ascii=False,indent=2),encoding='utf-8')
        print('Saved',path)

if __name__=='__main__':main()
