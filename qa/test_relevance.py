"""Answer, relevance, allocation, shortcut, service and trust checks for the relevance probe."""
import base64
import copy
import hashlib
import importlib
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_relevance'
NAMES = ['fhir', 'store', 'server', 'grade', 'reference', 'build_relevance', 'graph_cases']
saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
paths = [str(TASK / 'environment/service'), str(TASK / 'tests'), str(TASK / 'solution'), str(ROOT / 'qa')]
sys.path[:0] = paths
try:
    M = {n: importlib.import_module(n) for n in NAMES}
finally:
    for n in NAMES:
        sys.modules.pop(n, None)
    sys.modules.update(saved)
    for p in paths:
        sys.path.remove(p)
store, server, grade, reference, builder = (M[n] for n in ['store', 'server', 'grade', 'reference', 'build_relevance'])
FIXTURE = json.loads((TASK / 'environment/service/fixture.json').read_text())
SHORTCUTS = ('original_fields', 'ignore_withdrawals', 'whole_note_withdrawal', 'all_authors', 'ignore_pauses',
             'double_count_pauses', 'one_pass_clock', 'always_routine', 'reuse_specimens', 'ignore_prerequisite', 'greedy',
             'best_guess', 'abstain_any_gap')


def chart(patient):
    return [r for r in FIXTURE['sources']
            if r['id'] == patient or r.get('subject', r.get('patient', {})).get('reference') == 'Patient/' + patient]


def answers(shortcut=None):
    return [row for p, eps in FIXTURE['targets'].items() for row in reference.solve_patient(chart(p), p, eps, shortcut)]


def maximum_assignments(patient):
    """Every valid joint assignment reaching the patient's optimum, by brute force over grader facts."""
    expected = grade.EXPECTED[patient]
    keys = [k for k, r in expected['rows'].items() if not r['fixed_status']]
    options = [[None] + [rid for rid, rep in expected['reports'].items() if grade.candidate(expected['rows'][k], rep)]
               for k in keys]
    found = []
    for combo in itertools.product(*options):
        chosen = {k: r for k, r in zip(keys, combo) if r}
        specimens = [expected['reports'][r]['specimen'] for r in chosen.values()]
        if len(specimens) != len(set(specimens)) or len(chosen) != expected['optimum']:
            continue
        ok = True
        for k, r in chosen.items():
            row = expected['rows'][k]
            if row['checkpoint'] == 'second':
                first = chosen.get(row['episode'] + ':first')
                ok &= bool(first) and (grade.day(expected['reports'][r]['date'])
                                       - grade.day(expected['reports'][first]['date'])).days >= row['separation']
        if ok:
            found.append(chosen)
    return found


def rows_for(patient, chosen):
    """Reference rows rewritten to a given assignment, with statuses derived as the policy says."""
    rows = [r for r in answers() if r['patient'] == patient]
    for row in rows:
        key = row['episode'] + ':' + row['checkpoint']
        if row['status'] in ('unclear', 'no_requirement'):
            continue
        row['result'] = chosen.get(key)
        expected = grade.EXPECTED[patient]
        if row['result']:
            row['status'] = 'completed'
        elif any(grade.unreceived_fits(expected['rows'][key], d, chosen.get(row['episode'] + ':first'), expected)
                 for d in expected['unreceived']):
            row['status'] = 'cannot_determine'
        elif row['checkpoint'] == 'second' and not chosen.get(row['episode'] + ':first'):
            row['status'] = 'blocked'
        else:
            row['status'] = 'overdue' if row['due_date'] <= '2026-09-24' else 'not_due'
    return rows


class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.fresh()

    def fresh(self):
        self.service = store.Store(Path(tempfile.mkdtemp(dir=self.temp.name)) / 'clinic.sqlite')
        self.service.initialize()
        self.attestation = self.service.attest('relevance-test')

    def submit(self, payload):
        status, body = self.service.request('POST', '/determinations', payload)
        self.assertEqual(status, 200, body)
        return body

    def finish(self):
        snap = self.service.collect()
        return snap, grade.grade(snap, self.attestation)

    def wrong_patients(self, result):
        return sorted(p for p, v in result['patients'].items()
                      if not (v['allocation'] and all(v['allocation'].values())
                              and all(all(r.values()) for r in v['rows'].values())))

    def test_harbor_entrypoints_are_executable(self):
        for path in (TASK / 'solution/solve.sh', TASK / 'tests/test.sh'):
            self.assertTrue(os.access(path, os.X_OK), str(path))

    def test_independent_solver_agrees_with_authored_answers(self):
        for row in answers():
            key = row['episode'] + ':' + row['checkpoint']
            expected = grade.EXPECTED[row['patient']]['rows'][key]
            for field in grade.ROW_FIELDS:
                self.assertEqual(row[field], expected[field], (key, field))
            self.assertEqual(set(row['doses']), set(expected['doses']), key)
            self.submit(row)
        snapshot, result = self.finish()
        self.assertEqual(result['reward'], 1, result)
        self.assertEqual(grade.grade(snapshot, self.attestation), result)

    def test_reference_through_cli(self):
        server.STORE = self.service
        http = HTTPServer(('127.0.0.1', 0), server.Handler)
        t = threading.Thread(target=http.serve_forever, daemon=True)
        t.start()
        self.addCleanup(lambda: (http.shutdown(), http.server_close(), t.join()))

        def cli(*args):
            p = subprocess.run([sys.executable, str(TASK / 'environment/public/clinic.py'), *args],
                               env={**os.environ, 'CLINIC_URL': f'http://127.0.0.1:{http.server_port}'},
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        with patch.object(reference, 'clinic', cli):
            reference.solve()
        self.assertEqual(self.finish()[1]['reward'], 1)

    def test_every_maximum_assignment_passes(self):
        for patient in FIXTURE['targets']:
            options = maximum_assignments(patient)
            self.assertTrue(options, patient)
            for chosen in options:
                with self.subTest(patient=patient, chosen=chosen):
                    self.fresh()
                    for row in answers():
                        if row['patient'] != patient:
                            self.submit(row)
                    for row in rows_for(patient, chosen):
                        self.submit(row)
                    self.assertEqual(self.finish()[1]['reward'], 1)

    def test_valid_but_smaller_assignment_fails(self):
        for patient in FIXTURE['targets']:
            chosen = maximum_assignments(patient)[0]
            if not chosen:
                continue
            # Drop a second checkpoint if one is assigned, else a first: still valid, one fewer.
            key = next((k for k in chosen if k.endswith(':second')), next(iter(chosen)))
            smaller = {k: v for k, v in chosen.items() if k != key and not (key.endswith(':first') and k == key.replace(':first', ':second'))}
            with self.subTest(patient=patient):
                self.fresh()
                for row in answers():
                    if row['patient'] != patient:
                        self.submit(row)
                for row in rows_for(patient, smaller):
                    self.submit(row)
                result = self.finish()[1]
                self.assertEqual(result['reward'], 0)
                self.assertFalse(result['patients'][patient]['allocation']['maximum'])

    def test_each_shortcut_fails(self):
        report = {}
        for shortcut in SHORTCUTS:
            with self.subTest(shortcut=shortcut):
                self.fresh()
                for row in answers(shortcut):
                    self.submit(row)
                result = self.finish()[1]
                report[shortcut] = self.wrong_patients(result)
                self.assertEqual(result['reward'], 0, shortcut)
        print('\nshortcut -> patients wrong:', {k: len(v) for k, v in report.items()})

    def test_noop_duplicate_missing_and_wrong_fields_fail(self):
        self.assertEqual(self.finish()[1]['reward'], 0)
        good = answers()
        variants = ('duplicate', 'missing', 'doses', 'due_date', 'paused_days', 'branch', 'status', 'reuse')
        for variant in variants:
            with self.subTest(variant=variant):
                self.fresh()
                payloads = copy.deepcopy(good)
                target = next(p for p in payloads if p['status'] == 'completed')
                if variant == 'duplicate':
                    payloads.append(payloads[0])
                elif variant == 'missing':
                    payloads.pop()
                elif variant == 'doses':
                    target['doses'] = target['doses'][:2]
                elif variant == 'due_date':
                    target['due_date'] = '2026-01-01'
                elif variant == 'paused_days':
                    target['paused_days'] += 1
                elif variant == 'branch':
                    target['branch'] = 'routine' if target['branch'] == 'accelerated' else 'accelerated'
                elif variant == 'status':
                    target['status'] = 'overdue'
                else:  # one specimen used by two checkpoints
                    other = next(p for p in payloads if p is not target and p['patient'] == target['patient'] and p['status'] == 'completed')
                    other['result'] = target['result']
                for p in payloads:
                    self.submit(p)
                self.assertEqual(self.finish()[1]['reward'], 0)

    def test_bad_types_are_recoverable(self):
        good = answers()[0]
        for key, value in [('patient', []), ('patient', {}), ('patient', None), ('episode', {}), ('checkpoint', 'third'),
                           ('checkpoint', []), ('plan', []), ('doses', {}), ('doses', [None]), ('branch', 'fast'),
                           ('paused_days', -1), ('paused_days', True), ('due_date', '2026-9-1'), ('status', [])]:
            with self.subTest(key=key, value=value):
                status, _ = self.service.request('POST', '/determinations', {**good, key: value})
                self.assertEqual(status, 400)
        with self.service.connect() as db:
            self.assertEqual(self.service.metadata(db)['faults'], 0)
        item = self.submit({**good, 'status': 'blocked'})
        self.assertNotIn('reward', item)
        self.assertEqual(self.finish()[1]['validity'], 'valid')

    def test_updates_keep_identity_fields(self):
        item = self.submit(answers()[0])
        for key, value in (('episode', 'wrong'), ('checkpoint', 'second'), ('patient', 'P0')):
            self.assertEqual(self.service.request('PATCH', '/determinations/' + item['id'], {key: value})[0], 400)
        status, new = self.service.request('PATCH', '/determinations/' + item['id'], {'explanation': 'Updated.'})
        self.assertEqual(status, 200)
        self.assertEqual((new['for'], new['focus']), (item['for'], item['focus']))

    def test_read_only_freeze_and_invalid_evaluation(self):
        for path in ('/history', '/export', '/grade', '/reset'):
            self.assertEqual(self.service.request('GET', path)[0], 400)
        snapshot, _ = self.finish()
        self.assertEqual(self.service.request('GET', '/patients')[0], 409)
        snapshot['metadata']['nonce'] = 'forged'
        with self.assertRaises(grade.EvaluationError):
            grade.grade(snapshot, self.attestation)

    def test_generator_attachments_sizes_and_public_surface(self):
        fixture, expected, readings = builder.build()
        self.assertEqual(fixture, FIXTURE)
        self.assertEqual(expected, grade.EXPECTED)
        self.assertEqual(json.loads(json.dumps(readings)), reference.READINGS)
        for r in fixture['sources']:
            if r['resourceType'] == 'DocumentReference':
                text = r['description']
                self.assertEqual(base64.b64decode(r['content'][0]['attachment']['data']).decode(), text)
                # Free text only: no record IDs, clause numbers, or computed conclusions.
                self.assertNotRegex(text, r'(?i)R[0-9a-f]{12}|\[\d\]|overdue|not_due|blocked|due date|course complet')
                self.assertIn(r['id'], reference.READINGS)
        for r in fixture['sources']:
            if r['resourceType'] == 'ServiceRequest':
                self.assertNotRegex(r['note'][0]['text'], r'R[0-9a-f]{12}')
        for p in fixture['targets']:
            self.assertLess(len(json.dumps({'complete': True, 'resources': chart(p)}, indent=2)), 90000)
        public = '\n'.join(p.read_text() for p in (TASK / 'environment/public').glob('*') if p.is_file())
        public += (TASK / 'instruction.md').read_text()
        self.assertNotRegex(public, r'graph_cases|readings|EXPECTED|expected\.json|optimum|P[0-9a-f]{7}\b|R[0-9a-f]{12}\b')

    def test_id_renaming_and_presentation_order_do_not_change_answers(self):
        ids = {r['id'] for r in FIXTURE['sources']}
        mapping = {i: (i[0] + hashlib.sha256(('renamed' + i).encode()).hexdigest()[:len(i) - 1]) for i in ids}
        pattern = re.compile('|'.join(re.escape(i) for i in sorted(ids, key=len, reverse=True)))
        transform = lambda x: json.loads(pattern.sub(lambda m: mapping[m.group()], json.dumps(x)))
        renamed = {(mapping[k] if k in mapping else 'plan:' + mapping[k[5:]]): transform(v) for k, v in reference.READINGS.items()}
        for p, eps in FIXTURE['targets'].items():
            resources = transform(chart(p))
            resources.reverse()
            with patch.object(reference, 'READINGS', renamed):
                got = reference.solve_patient(resources, mapping[p], [mapping[e] for e in eps])
            want = transform([r for r in answers() if r['patient'] == p])
            # Row facts must be identical; the allocation may land on a different, equally large maximum.
            strip = lambda rows: sorted((r['episode'], r['checkpoint'], r['plan'], r['course'], r['branch'],
                                         tuple(sorted(r['doses'])), r['completion_date'], r['due_date'], r['paused_days'])
                                        for r in rows)
            self.assertEqual(strip(got), strip(want), p)
            self.assertEqual(sum(r['status'] == 'completed' for r in got), grade.EXPECTED[p]['optimum'], p)


if __name__ == '__main__':
    unittest.main()
