"""Score a final confirmation batch under its predeclared protocol (standard library only; makes no model calls).

    python3 qa/confirm_summary.py TASK BATCH_DIR [--frozen COMMIT]      e.g.  python3 qa/confirm_summary.py chartr_task4 jobs/chartr/confirm-task4-0.4.1-20261001T120000Z

BATCH_DIR is the batch's unique jobs directory (every Harbor job inside it: the batch and any reruns). The script applies
the counting rules in the task README's "Final confirmation protocol" mechanically:
- provenance: every trial must have run the frozen task files (README.md excepted), provider and adapter, the protocol
  model and budgets. Any mismatch voids the batch;
- invalid attempts (no reward: API/adapter errors, interruptions, service or evidence faults) are not attempts;
- valid attempts are passes (reward 1) or failures; failures that ended on a budget (output truncation, turn, wall or
  tool timeout, context exhaustion) are counted and also listed as budget failures;
- the headline is passes out of the first 10 valid attempts in start order, complete only when there are 10.
Exits 0 only for a complete batch with clean provenance. Triage of each failure stays a human step.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = '19edc3b'
MODEL = 'claude-opus-5'
ADAPTER = '0.4.0'
PROTOCOL = {   # version and the exact --ak budgets of each task's confirmation command
    'chartr_task3': {'version': '0.3.1', 'limits': {'max_turns': 250, 'max_tokens': 64000, 'api_timeout_sec': 1800.0,
                                                   'wall_timeout_sec': 7000.0, 'tool_timeout_sec': 60.0, 'prompt_cache': True}},
    'chartr_task4': {'version': '0.4.1', 'limits': {'max_turns': 300, 'max_tokens': 64000, 'api_timeout_sec': 1800.0,
                                                   'wall_timeout_sec': 7000.0, 'tool_timeout_sec': 900.0, 'prompt_cache': True}},
}
COMPLETED = {'end_turn', 'stop_sequence', 'refusal'}
BUDGET = {'output_truncated', 'turn_exhaustion', 'wall_timeout', 'tool_timeout', 'context_exhausted'}


def frozen_sha(commit, path):
    out = subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=ROOT, capture_output=True)
    return hashlib.sha256(out.stdout).hexdigest() if out.returncode == 0 else None


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def trial_record(trial, task, commit):
    rec = {'trial': trial.name, 'problems': []}
    result = read(trial / 'result.json') or {}
    rec['started_at'] = result.get('started_at') or ''
    manifest = read(trial / 'controller/run-manifest.json')
    if manifest is None:
        rec['problems'].append('no run manifest')
    else:
        for rel, digest in manifest['task_files_sha256'].items():
            if rel != 'README.md' and digest != frozen_sha(commit, f'{task}/{rel}'):
                rec['problems'].append('task file differs from frozen commit: ' + rel)
        if manifest.get('provider_sha256') != frozen_sha(commit, 'chartr_environment.py'):
            rec['problems'].append('provider differs from frozen commit')
    events = (trial / 'controller/anthropic/events.jsonl')
    start = json.loads(events.read_text().splitlines()[0]) if events.exists() else None
    if start is None:
        rec['problems'].append('no adapter start event')
    else:
        if start.get('model') != MODEL:
            rec['problems'].append('model ' + str(start.get('model')))
        if start.get('driver') != ADAPTER or start.get('adapter_sha256') != frozen_sha(commit, 'anthropic_agent.py'):
            rec['problems'].append('adapter differs from frozen commit')
        for key, want in PROTOCOL[task]['limits'].items():
            if start['limits'].get(key) != want:
                rec['problems'].append(f'budget {key}={start["limits"].get(key)} (protocol {want})')
    termination = read(trial / 'controller/anthropic/termination.json') or {}
    diagnostics = read(trial / 'verifier/diagnostics.json') or {}
    reward_file = trial / 'verifier/reward.txt'
    rec['reason'] = termination.get('reason', 'none')
    valid = (termination.get('validity') == 'valid' and diagnostics.get('validity') == 'valid' and reward_file.exists())
    if not valid:
        rec['outcome'] = 'invalid'
        rec['why'] = diagnostics.get('error') or termination.get('reason') or (result.get('exception_info') or {}).get('exception_type') or 'no reward'
    else:
        rec['outcome'] = 'pass' if reward_file.read_text().strip() == '1' else 'fail'
        rec['budget'] = rec['outcome'] == 'fail' and rec['reason'] in BUDGET
        if rec['outcome'] == 'fail':
            rec['failed_components'] = sorted(k for k, v in (diagnostics.get('components') or {}).items() if not v) or \
                sorted({v['error'] for v in (diagnostics.get('failed_candidates') or {}).values()})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task', choices=sorted(PROTOCOL))
    ap.add_argument('batch_dir', type=Path)
    ap.add_argument('--frozen', default=FROZEN, help='frozen commit (default: the protocol commit)')
    args = ap.parse_args()
    trials = sorted((t for t in args.batch_dir.glob(f'*/{args.task}__*') if t.is_dir()),
                    key=lambda t: (read(t / 'result.json') or {}).get('started_at') or '')
    records = [trial_record(t, args.task, args.frozen) for t in trials]
    void = [r for r in records if r['problems']]
    valid = [r for r in records if r['outcome'] != 'invalid']
    counted = valid[:10]
    for r in records:
        extra = r.get('why') or ', '.join(r.get('failed_components') or [])
        flag = ' [budget]' if r.get('budget') else ''
        mark = '' if r in counted or r['outcome'] == 'invalid' else ' (beyond the first 10 valid; not counted)'
        print(f"{r['started_at'][:19]}  {r['trial']:24s} {r['outcome']:8s}{flag} {r['reason']:18s} {extra}{mark}")
        for p in r['problems']:
            print('    PROVENANCE: ' + p)
    passes = sum(r['outcome'] == 'pass' for r in counted)
    print(f"\n{len(records)} trials: {len(valid)} valid, {len(records) - len(valid)} invalid (rerun under the same command); "
          f"budget failures among counted: {sum(bool(r.get('budget')) for r in counted)}")
    if void:
        print(f'VOID: {len(void)} trial(s) did not run the frozen protocol; the batch does not count.')
        sys.exit(1)
    if len(counted) < 10:
        print(f'INCOMPLETE: {passes} passes / {len(counted)} valid; {10 - len(counted)} more valid attempt(s) needed.')
        sys.exit(1)
    print(f'HEADLINE ({args.task}, frozen commit {args.frozen}): {passes}/10 valid attempts pass.')


if __name__ == '__main__':
    main()
