"""Read-only process/GPU/stream counters. Run while Chrome subtitles are active."""
import argparse,json,time,subprocess,urllib.request,statistics
from datetime import datetime,timezone
from pathlib import Path

def fetch_health():
    with urllib.request.urlopen('http://localhost:8787/health',timeout=4) as r:return json.load(r)

def resources(health):
    ids=[health.get('pid'),health.get('models',{}).get('pid')]
    ids=[str(int(pid)) for pid in ids if pid]
    selected=','.join(ids) or '0'
    command=f"Get-Process | Where-Object {{ $_.Id -in @({selected}) -or $_.ProcessName -eq 'chrome' -or $_.ProcessName -like 'ollama*' -or $_.ProcessName -eq 'llama-server' }} | Select-Object Id,ProcessName,WorkingSet64,PrivateMemorySize64 | ConvertTo-Json -Compress"
    raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],timeout=8,creationflags=subprocess.CREATE_NO_WINDOW)
    processes=json.loads(raw.decode('utf-8-sig'))
    if isinstance(processes,dict):processes=[processes]
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],timeout=8,creationflags=subprocess.CREATE_NO_WINDOW).decode().strip()
    return dict(processes=processes,gpu=gpu)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--minutes',type=float,default=30)
    parser.add_argument('--interval',type=float,default=10)
    parser.add_argument('--output',default='quality/twitch-monitor-0.3.4.jsonl')
    args=parser.parse_args()
    if not 0<args.minutes<=120 or not 2<=args.interval<=60:parser.error('Invalid duration or interval')
    path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():parser.error('Output already exists; choose a new run filename')
    begin=time.monotonic();rows=[];last_notice=-60
    with path.open('w',encoding='utf-8') as output:
        while True:
            elapsed=time.monotonic()-begin
            row=dict(elapsed_seconds=round(elapsed,2),at=datetime.now(timezone.utc).isoformat())
            try:
                row['health']=fetch_health();row.update(resources(row['health']))
            except Exception as error:row['error']=str(error)
            rows.append(row);output.write(json.dumps(row,ensure_ascii=False)+'\n');output.flush()
            if elapsed-last_notice>=60 or elapsed>=args.minutes*60:
                last_notice=elapsed
                print(json.dumps(dict(minutes=round(elapsed/60,1),ready=row.get('health',{}).get('ready'),metrics=row.get('health',{}).get('models',{}).get('metrics'),gpu=row.get('gpu'),error=row.get('error'))),flush=True)
            if elapsed>=args.minutes*60:break
            time.sleep(min(args.interval,max(0,args.minutes*60-(time.monotonic()-begin))))
    good=[r for r in rows if r.get('health',{}).get('ready')]
    first=good[0]['health']['models'] if good else {}
    last=good[-1]['health']['models'] if good else {}
    summary=dict(duration_seconds=rows[-1]['elapsed_seconds'],samples=len(rows),failed_samples=sum(bool(r.get('error')) or not r.get('health',{}).get('ready') for r in rows),
        backend_restarts=len({r['health']['models'].get('pid') for r in good})-1 if good else None,
        received_audio_seconds=(last.get('metrics',{}).get('audio_samples',0)-first.get('metrics',{}).get('audio_samples',0))/16000,
        finals=last.get('metrics',{}).get('finals',0)-first.get('metrics',{}).get('finals',0),
        processing_errors=last.get('metrics',{}).get('errors',0)-first.get('metrics',{}).get('errors',0),
        max_pending_batches=max((r['health']['models'].get('pending_batches',0) for r in good),default=0),
        max_replay_entries=max((r['health']['models'].get('replay_cache_entries',0) for r in good),default=0),
        scope='All Chrome processes include other tabs. Memory growth alone does not prove a leak. Confirm video playback and overlay counters separately.')
    path.with_suffix('.summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
