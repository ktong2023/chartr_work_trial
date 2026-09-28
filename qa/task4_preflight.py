"""Check the local Task 4 checkout and host before dispatching paid trials (standard library only).

    python3 qa/task4_preflight.py EXPECTED_VERSION        e.g.  python3 qa/task4_preflight.py 0.3.5

Exits 1 unless task.toml, the service and the verifier baseline all carry EXPECTED_VERSION, every catalogued ECG file is
pinned for the image build, chartr_task4/ has no uncommitted changes, the adapter supports opt-in prompt caching, and no
other ChartR trial containers are running (Task 4 runs are long; a concurrent batch contends for the same CPUs and
memory). Prints the commit to record with the job.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_task4'


def run(*cmd):
    # Fail closed: a missing git or unreachable Docker must not read as a clean checkout or an idle host.
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, str(exc)
    return (out.stdout if out.returncode == 0 else None), out.stderr.strip()


def main():
    want = sys.argv[1]
    toml = re.search(r'^version = "(.+)"', (TASK / 'task.toml').read_text(), re.M).group(1)
    service = re.search(r"^VERSION = '(.+)'", (TASK / 'environment/service/store.py').read_text(), re.M).group(1)
    baseline = json.loads((TASK / 'tests/baseline.json').read_text())
    expected = json.loads((TASK / 'tests/expected.json').read_text())
    overlay = json.loads((TASK / 'environment/service/overlay/overlay.json').read_text())
    pinned = {line.split()[1] for line in (TASK / 'environment/service/overlay/pinned.sha256').read_text().splitlines()}
    catalog = {f"mimic-iv-ecg-demo/0.1/{e['path']}{ext}" for e in overlay['ecg_catalog'] for ext in ('.hea', '.dat')}
    adapter = (ROOT / 'anthropic_agent.py').read_text()
    status, _ = run('git', 'status', '--porcelain', '--', str(TASK))
    commit, _ = run('git', 'rev-parse', '--short', 'HEAD')
    names, docker_err = run('docker', 'ps', '--format', '{{.Names}}')
    host, _ = run('docker', 'info', '--format', '{{.NCPU}} CPUs {{.MemTotal}} bytes')
    others = [n for n in (names or '').split() if n.startswith('chartr_')]
    checks = {
        f'task.toml version is {want}': toml == want,
        f'service version is chartr-task4-{want}': service == f'chartr-task4-{want}',
        f'baseline version is chartr-task4-{want}': baseline['version'] == f'chartr-task4-{want}',
        'every catalogued ECG file is pinned': catalog <= pinned,
        'answer key has items and interpretations': bool(expected['items']) and bool(expected['interpretations']),
        'git available and chartr_task4/ has no uncommitted changes': status is not None and commit is not None and not status.strip(),
        'adapter supports --ak prompt_cache=true': 'prompt_cache: bool' in adapter,
        'docker reachable': names is not None and host is not None and not host.startswith('0 '),
        'no other ChartR trial containers running': names is not None and not others,
    }
    for name, ok in checks.items():
        print(('ok    ' if ok else 'FAIL  ') + name)
    if others:
        print('running:', ' '.join(sorted(others)))
    if names is None:
        print('docker error:', docker_err)
    print(f"commit {(commit or '?').strip()}; {len(expected['items'])} items, {len(expected['interpretations'])} interpretations; "
          f"docker {(host or '?').strip()}")
    sys.exit(0 if all(checks.values()) else 1)


if __name__ == '__main__':
    main()
