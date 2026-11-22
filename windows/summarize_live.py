"""Summarize saved health/resource samples without touching running services."""
import argparse
import json
import statistics
from pathlib import Path


def summarize(rows):
    good = [r for r in rows if r.get('health', {}).get('ready') and not r.get('error')]
    if not good:
        raise ValueError('No complete ready samples')
    duration = rows[-1]['elapsed_seconds'] - rows[0]['elapsed_seconds']
    pids = {r['health']['models']['pid'] for r in good}
    stable = len(pids) == 1
    first = good[0]['health']['models']['metrics']
    last = good[-1]['health']['models']['metrics']
    def delta(key):
        return last[key] - first[key] if stable else None
    def memory(row, group):
        health = row['health']
        def selected(p):
            if group == 'backend': return p['Id'] == health['models']['pid']
            if group == 'bridge': return p['Id'] == health['pid']
            return p['ProcessName'] == 'chrome'
        return sum(p['PrivateMemorySize64'] for p in row['processes'] if selected(p)) / 1048576
    resources = {}
    for group in ('backend', 'bridge', 'all_chrome'):
        values = [memory(r, group) for r in good]
        # Exclude the first five minutes for the early stable window on long runs.
        early = [memory(r, group) for r in good if 300 <= r['elapsed_seconds'] <= 600]
        late = [memory(r, group) for r in good if r['elapsed_seconds'] >= rows[-1]['elapsed_seconds'] - 300]
        resources[group] = dict(first_mib=values[0], last_mib=values[-1], max_mib=max(values),
            early_window_median_mib=statistics.median(early) if early else None,
            last_five_minutes_median_mib=statistics.median(late))
    gpu = [float(r['gpu'].split(',')[0]) for r in good]
    audio = delta('audio_samples')
    return dict(duration_seconds=duration, complete_30_minutes=duration >= 1800,
        samples=len(rows), failed_samples=len(rows)-len(good),
        backend_pid_changed=not stable,
        bridge_pid_changed=len({r['health']['pid'] for r in good}) != 1,
        audio_seconds=audio / 16000 if audio is not None else None,
        finals=delta('finals'), errors=delta('errors'),
        canceled_batches=delta('canceled_batches'),
        max_pending=max(r['health']['models']['pending_batches'] for r in good),
        max_replay_cache=max(r['health']['models']['replay_cache_entries'] for r in good),
        memory_private=resources, gpu_used_mib=dict(min=min(gpu),max=max(gpu),last=gpu[-1]),
        limitations=['Health counters do not establish the active Twitch channel or subtitle rendering.',
            'All Chrome tabs and all GPU users are included; growth alone does not establish a leak.',
            'No transcript reference means no ASR or translation accuracy score.',
            'Counter differences are unavailable when the backend PID changed.'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding='utf-8').splitlines() if line]
    result = summarize(rows)
    output = args.input.with_suffix('.analysis.json')
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, indent=2, ensure_ascii=False))
