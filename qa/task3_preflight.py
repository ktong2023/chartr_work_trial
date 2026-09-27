"""Check the local Task 3 checkout before dispatching paid trials (standard library only).

    python3 qa/task3_preflight.py EXPECTED_VERSION        e.g.  python3 qa/task3_preflight.py 0.2.1

Exits 1 unless task.toml, the service fixture and the verifier baseline all carry EXPECTED_VERSION, the fixture matches
the baseline digest, and chartr_task3/ has no uncommitted changes. Prints the commit and patient count to record with
the job. (The 0.2.0 pilot folder held 0.1.1 runs because the checkout was never updated; this catches that.)
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_task3'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def main():
    want = sys.argv[1]
    toml = re.search(r'^version = "(.+)"', (TASK / 'task.toml').read_text(), re.M).group(1)
    fixture = json.loads((TASK / 'environment/service/fixture.json').read_text())
    baseline = json.loads((TASK / 'tests/baseline.json').read_text())
    dirty = subprocess.run(['git', 'status', '--porcelain', '--', str(TASK)], cwd=ROOT, capture_output=True, text=True).stdout
    commit = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    checks = {
        f'task.toml version is {want}': toml == want,
        f'fixture version is {want}': fixture['version'] == f'chartr-cohort-audit-{want}',
        f'baseline version is {want}': baseline['version'] == f'chartr-cohort-audit-{want}',
        'fixture matches baseline digest': digest(fixture) == baseline['initial_digest'],
        'chartr_task3/ has no uncommitted changes': not dirty.strip(),
    }
    for name, ok in checks.items():
        print(('ok    ' if ok else 'FAIL  ') + name)
    print(f'commit {commit}; {len(fixture["episodes"])} patients; {len(fixture["sources"])} records')
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
