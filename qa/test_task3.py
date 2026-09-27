"""Task 3 (cohort audit) answer, calibration, shortcut, service and public-surface checks."""
import importlib
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
TASK = ROOT / 'chartr_task3'
NAMES = ['fhir', 'store', 'server', 'grade', 'task3_cases', 'task3_rules', 'build_task3']
saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
paths = [str(TASK / 'environment/service'), str(TASK / 'tests'), str(ROOT / 'qa')]
sys.path[:0] = paths
try:
    M = {n: importlib.import_module(n) for n in NAMES}
finally:
    for n in NAMES:
        sys.modules.pop(n, None)
    sys.modules.update(saved)
    for p in paths:
        sys.path.remove(p)
store, server, grade, cases, rules, builder = (M[n] for n in ['store', 'server', 'grade', 'task3_cases', 'task3_rules', 'build_task3'])
FIXTURE = json.loads((TASK / 'environment/service/fixture.json').read_text())
EXPECTED = json.loads((TASK / 'tests/expected.json').read_text())
ANSWERS = json.loads((TASK / 'solution/answers.json').read_text())
KEYS = {v['patient_key']: k.split('|')[:2] for k, v in EXPECTED['candidates'].items()}

# Candidates each wrong algorithm must get wrong: (patient key, issue prefix). Derived from the design, and
# asserted to be exactly the algorithm's errors.
TARGETS = {
    'never_abstain': {('p01', 'INA'), ('p06', 'INA'), ('p08', 'INA'), ('p12', 'INA'), ('p12', 'FOL'), ('p13', 'FOL'),
                      ('p16', 'FOL'), ('p16', 'MIS'), ('p19', 'PRE'), ('p20', 'INA'), ('p20', 'PRE'), ('p21', 'PRE')},
    'abstain_any_gap': {('p01', 'INA'), ('p01', 'FOL'), ('p02', 'INA'), ('p02', 'FOL'), ('p07', 'INA'), ('p07', 'FOL'),
                        ('p09', 'INA'), ('p10', 'INA'), ('p11', 'FOL'), ('p12', 'INA'), ('p12', 'FOL'), ('p18', 'PRE'),
                        ('p21', 'INA'), ('p22', 'PRE'), ('p23', 'INA'), ('p24', 'PRE'), ('p29', 'PRE')},
    'per_patient': {('p14', 'FOL'), ('p14', 'MIS'), ('p15', 'FOL'), ('p16', 'FOL'), ('p16', 'MIS')},
    'ignore_received': {('p09', 'INA'), ('p22', 'PRE'), ('p23', 'INA'), ('p24', 'PRE'), ('p29', 'PRE')},
    'ignore_unreceived': {('p08', 'INA'), ('p13', 'FOL'), ('p19', 'PRE')},
    'pending_negative': {('p20', 'INA'), ('p20', 'PRE'), ('p21', 'PRE')},
    'pending_not_obtained': {('p11', 'FOL')},
    'latest_wins': {('p06', 'INA'), ('p16', 'FOL'), ('p16', 'MIS'), ('p22', 'PRE')},
    'default_late': {('p12', 'INA'), ('p12', 'FOL')},
    'pep_is_treatment': {('p26', 'INA'), ('p26', 'FOL')},
    'nonpregnant_interval_in_pregnancy': {('p24', 'INA'), ('p24', 'PRE')},
    'structured_only': {('p05', 'INA'), ('p09', 'INA'), ('p23', 'INA')},
}


def items_for(dispositions):
    """Submissions an agent following these dispositions would save."""
    out = []
    for key, want in EXPECTED['candidates'].items():
        pid, eid, issue = key.split('|')
        disposition, code = dispositions[want['patient_key']][issue]
        if disposition == 'not_an_issue' and not want['requested']:
            continue
        out.append({'patient': pid, 'episode': eid, 'issue': issue, 'disposition': disposition,
                    'missing_evidence': code, 'evidence': EXPECTED['charts'][pid][:2], 'explanation': 'x'})
    return out


class Task3(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fresh()

    def fresh(self):
        self.store = store.Store(Path(self.tmp.name) / f'{os.urandom(4).hex()}.sqlite')
        self.store.initialize()
        self.meta = self.store.attest('trial-test')

    def post(self, payload):
        return self.store.request('POST', '/items', payload)

    def finish(self):
        snapshot = self.store.collect()
        return grade.grade(snapshot, self.meta)

    def run_items(self, payloads):
        self.fresh()
        for payload in payloads:
            status, body = self.post(payload)
            self.assertEqual(status, 200, body)
        return self.finish()

    # ------------------------------------------------------------------ answers
    def test_rules_agree_with_authored_truth_and_build_is_reproducible(self):
        for p in cases.PATIENTS:
            got = rules.disposition(p)
            for issue in cases.ISSUES:
                self.assertEqual(got[issue], p['truth'].get(issue, ('not_an_issue', None)), (p['key'], issue))
        fixture, expected, answers = builder.build()
        self.assertEqual(fixture, FIXTURE)
        self.assertEqual(expected, EXPECTED)
        self.assertEqual(answers, ANSWERS)

    def test_design_counts(self):
        c = list(EXPECTED['candidates'].values())
        self.assertEqual(len(c), 29 * 4)
        self.assertEqual(sum(x['disposition'] == 'confirmed' for x in c), 12)
        codes = [x['code'] for x in c if x['disposition'] == 'cannot_determine']
        self.assertEqual(len(codes), 9)
        self.assertEqual(set(codes), {'RESULT_PENDING', 'OUTSIDE_RECORD_NOT_RECEIVED', 'UNRESOLVED_SOURCE_CONFLICT'})
        requested = [x for x in c if x['requested']]
        self.assertEqual(len(requested), 8)
        self.assertEqual({x['disposition'] for x in requested}, {'confirmed', 'not_an_issue', 'cannot_determine'})
        # Each unknown decides at most one code; no world is left out of the unknown's options.
        for p in cases.PATIENTS:
            if p.get('unknown'):
                self.assertGreaterEqual(len(p['unknown']['options']), 1)

    def test_reference_passes_and_noop_fails(self):
        result = self.run_items(ANSWERS)
        self.assertEqual(result['reward'], 1, result['failed_candidates'])
        self.fresh()
        result = self.finish()
        self.assertEqual(result['reward'], 0)
        self.assertEqual(set(result['errors']), {'missed', 'overclaim', 'missing'})

    def test_reference_through_real_cli(self):
        with patch.object(server, 'STORE', self.store):
            http = HTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                env = {**os.environ, 'CLINIC_URL': f'http://127.0.0.1:{http.server_port}'}
                cli = lambda *a: subprocess.run([sys.executable, str(TASK / 'environment/public/clinic.py'), *a],
                                                env=env, capture_output=True, text=True)
                out = Path(self.tmp.name) / 'export'
                r = cli('export', '--dir', str(out))
                self.assertEqual(r.returncode, 0, r.stderr)
                manifest = json.loads((out / 'manifest.json').read_text())
                self.assertTrue(manifest['complete'])
                lines = sum(len((out / f'{k}.ndjson').read_text().splitlines()) for k in manifest['counts'])
                self.assertEqual(lines, len(FIXTURE['sources']))
                for answer in ANSWERS:
                    r = cli('item', '--json', json.dumps(answer))
                    self.assertEqual(r.returncode, 0, r.stderr)
                r = cli('item', '--json', json.dumps(ANSWERS[0]))
                self.assertEqual(r.returncode, 2)
                self.assertEqual(len(json.loads(cli('requests').stdout)['requests']), 8)
            finally:
                http.shutdown()
                http.server_close()
        self.assertEqual(self.finish()['reward'], 1)

    # ------------------------------------------------------------------ calibration and shortcuts
    def test_each_wrong_algorithm_fails_exactly_on_its_targets(self):
        truth = rules.cohort()
        for algorithm in rules.ALGORITHMS:
            result = self.run_items(items_for(rules.cohort(algorithm)))
            self.assertEqual(result['reward'], 0, algorithm)
            wrong = {(v['patient_key'], k.split('|')[2][:3]) for k, v in result['failed_candidates'].items()}
            if algorithm == 'flag_all':
                self.assertEqual(len(wrong), sum(1 for v in EXPECTED['candidates'].values() if v['disposition'] != 'confirmed'))
                continue
            self.assertEqual(wrong, TARGETS[algorithm], algorithm)
        self.assertTrue(truth)

    def test_zero_tolerance_and_absence_semantics(self):
        base = list(ANSWERS)
        confirmed = [a for a in base if a['disposition'] == 'confirmed']
        # One missed real issue fails.
        self.assertEqual(self.run_items([a for a in base if a is not confirmed[0]])['reward'], 0)
        # One extra plain flag fails.
        pid, eid = KEYS['p27']
        extra = {'patient': pid, 'episode': eid, 'issue': 'FOLLOW_UP_OVERDUE', 'disposition': 'confirmed',
                 'missing_evidence': None, 'evidence': EXPECTED['charts'][pid][:1], 'explanation': 'x'}
        self.assertEqual(self.run_items(base + [extra])['reward'], 0)
        # Explicit not_an_issue on an unrequested candidate equals absence.
        self.assertEqual(self.run_items(base + [{**extra, 'disposition': 'not_an_issue'}])['reward'], 1)
        # A requested candidate needs an explicit item even when the answer is not_an_issue.
        requested_no = [a for a in base if a['disposition'] == 'not_an_issue']
        result = self.run_items([a for a in base if a is not requested_no[0]])
        self.assertEqual(result['errors'], {'missing': 1})
        # Right disposition with the wrong code fails.
        wrong_code = [dict(a, missing_evidence='RESULT_PENDING') if a['missing_evidence'] == 'UNRESOLVED_SOURCE_CONFLICT' else a for a in base]
        self.assertEqual(self.run_items(wrong_code)['errors'], {'wrong_code': 3})

    def test_evidence_validity(self):
        pid14, _ = KEYS['p14']
        pid15, _ = KEYS['p15']
        linked = EXPECTED['linked'][pid14]
        ok = [dict(a, evidence=linked) if a['patient'] == pid14 and a['issue'] == 'MISFILED_RESULT' else a for a in ANSWERS]
        self.assertEqual(self.run_items(ok)['reward'], 1)
        foreign = EXPECTED['charts'][KEYS['p27'][0]][0]
        bad = [dict(a, evidence=[foreign]) if a['patient'] == pid15 else a for a in ANSWERS]
        result = self.run_items(bad)
        self.assertEqual(result['reward'], 0)
        self.assertFalse(result['global']['evidence_valid'])

    # ------------------------------------------------------------------ service contract
    def test_service_validation_is_recoverable(self):
        pid, eid = KEYS['p01']
        good = {'patient': pid, 'episode': eid, 'issue': 'INADEQUATE_TREATMENT', 'disposition': 'confirmed',
                'missing_evidence': None, 'evidence': EXPECTED['charts'][pid][:1], 'explanation': 'x'}
        bad = [dict(good, patient=[]), dict(good, patient={}), dict(good, episode='E0'), dict(good, issue='X'),
               dict(good, disposition='maybe'), dict(good, missing_evidence='RESULT_PENDING'),
               dict(good, disposition='cannot_determine'), dict(good, evidence=[]), dict(good, evidence=['R000']),
               dict(good, evidence='R1'), dict(good, explanation=' '), dict(good, explanation='a b'),
               {k: v for k, v in good.items() if k != 'explanation'}, dict(good, extra=1)]
        for payload in bad:
            status, body = self.post(payload)
            self.assertEqual(status, 400, (payload, body))
        status, created = self.post(good)
        self.assertEqual(status, 200)
        self.assertEqual(self.post(good)[0], 400)
        status, updated = self.store.request('PATCH', '/items/' + created['id'],
                                             {'disposition': 'cannot_determine', 'missing_evidence': 'RESULT_PENDING'})
        self.assertEqual(status, 200, updated)
        self.assertEqual(self.store.request('PATCH', '/items/' + created['id'], {'issue': 'MISFILED_RESULT'})[0], 400)
        for route in ('/reset', '/admin', '/grade', '/records/Zzz', '/items/Zzz'):
            self.assertEqual(self.store.request('GET', route)[0], 400)
        self.assertEqual(self.store.request('POST', '/export', {})[0], 400)
        self.assertEqual(self.store.collect()['metadata']['faults'], 0)

    def test_reads_export_and_freeze(self):
        status, export = self.store.request('GET', '/export')
        self.assertEqual(len(export['resources']), len(FIXTURE['sources']))
        pid, _ = KEYS['p14']
        chart = self.store.request('GET', '/records/' + pid)[1]['resources']
        self.assertTrue(all(r['resourceType'] != 'Basic' for r in chart))
        accession = [r for r in export['resources'] if r['resourceType'] == 'Basic']
        self.assertEqual(len(accession), len([r for r in FIXTURE['sources'] if r['resourceType'] == 'Observation']))
        snapshot = self.store.collect()
        self.assertEqual(self.store.request('GET', '/patients')[0], 409)
        audit = next(e for e in snapshot['audit'] if e['path'] == '/export')
        self.assertEqual(audit['result'], {'complete': True, 'resources': len(FIXTURE['sources'])})

    # ------------------------------------------------------------------ public surface and fairness
    def test_public_surface(self):
        public = ''.join((TASK / p).read_text() for p in ('instruction.md', 'environment/public/policy.md', 'environment/public/tools.md'))
        for word in ('p01', 'Whitfield', 'unknown duration', 'doxy', 'hemolyz', 'name change', 'twin', 'careful'):
            self.assertNotIn(word.lower(), public.lower(), word)
        ids = {r['id'] for r in FIXTURE['sources']}
        for r in FIXTURE['sources']:
            text = r.get('description', '') + ' '.join(n['text'] for n in r.get('note', []))
            self.assertFalse(set(re.findall(r'\b[RPEI][0-9a-f]{7,12}\b', text)) & ids, r['id'])
        dockerignore = (TASK / 'environment/.dockerignore').read_text().split()
        self.assertEqual(dockerignore, ['**', '!Dockerfile', '!public/', '!public/**'])
        for path in ('solution/solve.sh', 'tests/test.sh'):
            self.assertTrue(os.access(TASK / path, os.X_OK), path)

    def test_every_result_has_identity_evidence(self):
        by_id = {r['id']: r for r in FIXTURE['sources']}
        accessions = {next(e['valueString'] for e in r['extension'] if e['url'].endswith('/accession'))
                      for r in FIXTURE['sources'] if r['resourceType'] == 'Basic'}
        for r in FIXTURE['sources']:
            if r['resourceType'] == 'Observation':
                spec = by_id[r['specimen']['reference'].split('/')[1]]
                self.assertEqual(spec['accessionIdentifier']['value'], r['identifier'][0]['value'])
                self.assertIn(r['identifier'][0]['value'], accessions)

    def test_id_renaming_and_order_do_not_change_answers(self):
        with patch.object(builder, 'SALT', 'renamed-v2'):
            fixture, expected, _ = builder.build()
        self.assertNotEqual({r['id'] for r in fixture['sources']} & {r['id'] for r in FIXTURE['sources']}, None)
        self.assertFalse({r['id'] for r in fixture['sources']} & {r['id'] for r in FIXTURE['sources']})
        strip = lambda e: sorted((v['patient_key'], k.split('|')[2], v['disposition'], v['code']) for k, v in e['candidates'].items())
        self.assertEqual(strip(expected), strip(EXPECTED))
        reordered = [dict(p, records=list(reversed(p['records']))) for p in cases.PATIENTS]
        for p in reordered:
            self.assertEqual(rules.disposition(p), rules.disposition(rules.BY_KEY[p['key']]), p['key'])


if __name__ == '__main__':
    unittest.main()
