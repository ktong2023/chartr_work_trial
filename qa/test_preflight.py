"""The pre-dispatch checks fail closed (v0.3.1 and v0.3.6 audits; release validation F6).

A checkout they cannot prove clean, a wrong version, or an unreachable Docker host must never pass. Each case runs the real
script as a subprocess against a copy of the task outside any Git repository, or with Docker pointed at a missing socket.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CURRENT = {'task3': '0.3.1', 'task4': '0.4.2'}


def copy_without_git(task):
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / f'chartr_{task}', tmp / f'chartr_{task}', ignore=shutil.ignore_patterns('__pycache__'))
    (tmp / 'qa').mkdir()
    shutil.copy(ROOT / f'qa/{task}_preflight.py', tmp / 'qa')
    shutil.copy(ROOT / 'anthropic_agent.py', tmp)
    return tmp


def preflight(root, task, version, **env):
    return subprocess.run([sys.executable, str(root / f'qa/{task}_preflight.py'), version], cwd=root, capture_output=True,
                          text=True, timeout=120, env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(root.parent), **env})


class Preflight(unittest.TestCase):
    def test_outside_git_fails(self):
        for task, version in CURRENT.items():
            root = copy_without_git(task)
            self.addCleanup(shutil.rmtree, root)
            out = preflight(root, task, version)
            self.assertEqual(out.returncode, 1, (task, out.stdout))
            self.assertRegex(out.stdout, r'FAIL +git', task)

    def test_wrong_version_fails(self):
        for task in CURRENT:
            out = preflight(ROOT, task, '9.9.9')
            self.assertEqual(out.returncode, 1, (task, out.stdout))
            self.assertIn('FAIL  task.toml version is 9.9.9', out.stdout)

    def test_unreachable_docker_fails(self):
        out = preflight(ROOT, 'task4', CURRENT['task4'], DOCKER_HOST='unix:///nonexistent-chartr-preflight.sock')
        self.assertEqual(out.returncode, 1, out.stdout)
        self.assertIn('FAIL  docker reachable', out.stdout)


if __name__ == '__main__':
    unittest.main()
