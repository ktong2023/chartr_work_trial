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
NAMES = ['fhir', 'store', 'server', 'grade', 'task3_cases', 'task3_families', 'task3_cohort', 'task3_rules', 'build_task3']
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
store, server, grade, cases, cohort, rules, builder = (M[n] for n in ['store', 'server', 'grade', 'task3_cases', 'task3_cohort', 'task3_rules', 'build_task3'])
CORE = {p['key'] for p in cases.PATIENTS}
FIXTURE = json.loads((TASK / 'environment/service/fixture.json').read_text())
EXPECTED = json.loads((TASK / 'tests/expected.json').read_text())
ANSWERS = json.loads((TASK / 'solution/answers.json').read_text())
KEYS = {v['patient_key']: k.split('|')[:2] for k, v in EXPECTED['candidates'].items()}

# Core candidates each wrong algorithm must get wrong: (patient key, issue prefix). Derived from the design, and
# asserted to be exactly the algorithm's errors on the hand-authored core.
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
        for p in cohort.PATIENTS:
            got = rules.disposition(p)
            for issue in cases.ISSUES:
                self.assertEqual(got[issue], p['truth'].get(issue, ('not_an_issue', None)), (p['key'], issue))
        fixture, expected, answers = builder.build()
        self.assertEqual(fixture, FIXTURE)
        self.assertEqual(expected, EXPECTED)
        self.assertEqual(answers, ANSWERS)

    def test_design_counts(self):
        c = list(EXPECTED['candidates'].values())
        self.assertEqual(len(c), 300 * 4)
        core = [x for x in c if x['patient_key'] in CORE]
        self.assertEqual(sum(x['disposition'] == 'confirmed' for x in core), 12)
        self.assertEqual(sum(x['disposition'] == 'cannot_determine' for x in core), 9)
        codes = {x['code'] for x in c if x['disposition'] == 'cannot_determine'}
        self.assertEqual(codes, {'RESULT_PENDING', 'OUTSIDE_RECORD_NOT_RECEIVED', 'UNRESOLVED_SOURCE_CONFLICT'})
        requested = [x for x in c if x['requested']]
        self.assertGreaterEqual(len(requested), 30)
        self.assertEqual({x['disposition'] for x in requested}, {'confirmed', 'not_an_issue', 'cannot_determine'})
        # Weighted toward chained cases: most non-control candidates are chains.
        hard = [x for x in c if x['kind'] != 'control']
        chained = [x for x in hard if x['kind'].startswith('chain')]
        self.assertGreater(len(chained), 0.45 * len(hard))

    def test_chained_families_point_both_ways(self):
        by_family = {}
        for p in cohort.PATIENTS[len(cases.PATIENTS):]:
            for issue, kind in p['kinds'].items():
                if kind.startswith('chain'):
                    by_family.setdefault(p['family'], set()).add(p['truth'].get(issue, ('not_an_issue', None))[0])
        for family, dispositions in by_family.items():
            self.assertIn('not_an_issue', dispositions, family)
            self.assertTrue(dispositions - {'not_an_issue'}, family)
        # No identical twins: within a family variant, no two instances share a chart skeleton (record kinds and dates).
        seen = {}
        for p in cohort.PATIENTS[len(cases.PATIENTS):]:
            sig = (p['family'], p['variant'], tuple(sorted((r[0], r[1]) for r in p['records'])))
            self.assertNotIn(sig, seen, p['key'])
            seen[sig] = p['key']
        self.assertEqual(len({p['name'] for p in cohort.PATIENTS}), len(cohort.PATIENTS))

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
                self.assertEqual(len(json.loads(cli('requests').stdout)['requests']),
                                 sum(v['requested'] for v in EXPECTED['candidates'].values()))
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
            self.assertEqual({w for w in wrong if w[0] in CORE}, TARGETS[algorithm], algorithm)
            if algorithm not in ('pending_not_obtained', 'nonpregnant_interval_in_pregnancy', 'default_late'):
                self.assertTrue({w for w in wrong if w[0] not in CORE}, algorithm + ' fails no generated case')
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
        conflicts = sum(1 for v in EXPECTED['candidates'].values() if v['code'] == 'UNRESOLVED_SOURCE_CONFLICT')
        self.assertEqual(self.run_items(wrong_code)['errors'], {'wrong_code': conflicts})

    def test_evidence_validity(self):
        allowed, _ = grade.admissible(FIXTURE['sources'])
        pid = {k: v[0] for k, v in KEYS.items()}
        # Links the grader computes from rendered records equal the identity relationships the cases were written
        # with: no link is missing (0.2.0: accessioning-entry-only links) and none is spurious (0.2.0: accession collisions).
        want, linking = set(), {}
        for p in cohort.PATIENTS:
            for n, r in enumerate(p['records']):
                if r[0] in ('rpr', 'hcg'):
                    owner = r[3].get('owner', p['key'])
                    named = {pid[k] for k in (p['key'], owner, r[3].get('accession_owner', owner)) if k in pid}
                    for x in named:
                        for y in named - {x}:
                            want.add((x, y))
                            linking.setdefault(x, []).extend([builder.rid(p['key'], str(n), 'Observation'), builder.rid(p['key'], f'{n}s', 'Specimen'),
                                                              builder.rid(p['key'], str(n), 'accession'), y, *EXPECTED['charts'][y][:2]])
        got = {(x, y) for x, ids in allowed.items() for y in allowed if x != y and y in ids}
        self.assertEqual(got, want)
        self.assertIn((pid['p14'], pid['p15']), got)
        self.assertGreater(len(linking), 40)
        # Every linked patient may cite the linking result, its specimen and accessioning entry, and the other patient's
        # Patient record and chart, on a real item, whichever chart holds them.
        answers = [dict(a) for a in ANSWERS]
        for x, cited in linking.items():
            mine = [a for a in answers if a['patient'] == x]
            if not mine:
                eid = next(k.split('|')[1] for k in EXPECTED['candidates'] if k.startswith(x + '|'))
                mine = [{'patient': x, 'episode': eid, 'issue': 'MISFILED_RESULT', 'disposition': 'not_an_issue',
                         'missing_evidence': None, 'explanation': 'x'}]
                answers += mine
            mine[0]['evidence'] = list(dict.fromkeys(cited))[:30]
        result = self.run_items(answers)
        self.assertEqual(result['reward'], 1, result['failed_candidates'])
        # Own patient/episode records and the answered review request are valid (pilot 0.1.1).
        pid14, eid14 = KEYS['p14']
        request_ids = [r['id'] for r in FIXTURE['sources'] if r['resourceType'] == 'Task' and r['for']['reference'] == 'Patient/' + pid14]
        own = [dict(a, evidence=[pid14, eid14] + request_ids) if a['patient'] == pid14 and a['issue'] == 'MISFILED_RESULT' else a
               for a in ANSWERS]
        self.assertEqual(self.run_items(own)['reward'], 1)
        # An unlinked patient's record is not.
        foreign = EXPECTED['charts'][pid['p27']][0]
        bad = [dict(a, evidence=[foreign]) if a['patient'] == pid['p15'] else a for a in ANSWERS]
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
        self.assertEqual(set(audit['result']), {'digest'})
        self.assertLess(len(json.dumps(snapshot['audit'])), 20000)

    def test_audit_is_linear_and_tampering_is_detected(self):
        self.fresh()
        for payload in ANSWERS:
            self.assertEqual(self.post(payload)[0], 200)
        for _ in range(20):
            self.store.request('GET', '/items')
        snapshot = self.store.collect()
        # Audit size grows with the number of requests, not requests x saved items.
        self.assertLess(len(json.dumps(snapshot['audit'])), 3000 * len(snapshot['audit']))
        self.assertEqual(grade.grade(snapshot, self.meta)['reward'], 1)
        forged = json.loads(json.dumps(snapshot))
        forged['items'][0]['businessStatus']['coding'][0]['code'] = 'not_an_issue'
        with self.assertRaises(grade.EvaluationError):
            grade.grade(forged, self.meta)
        forged = json.loads(json.dumps(snapshot))
        forged['audit'][-25]['changed']['description'] = 'edited'
        with self.assertRaises(grade.EvaluationError):
            grade.grade(forged, self.meta)

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

    def test_every_result_has_unique_identity_evidence(self):
        by_id = {r['id']: r for r in FIXTURE['sources']}
        entries = [grade.ext(r, 'accession') for r in FIXTURE['sources'] if r['resourceType'] == 'Basic']
        specimens = [r['accessionIdentifier']['value'] for r in FIXTURE['sources'] if r['resourceType'] == 'Specimen']
        results = [r['identifier'][0]['value'] for r in FIXTURE['sources'] if r['resourceType'] == 'Observation']
        # One accession number per specimen, result and accessioning entry (0.2.0 had four colliding numbers).
        self.assertEqual(sorted(entries), sorted(set(entries)))
        self.assertEqual(sorted(entries), sorted(specimens))
        self.assertEqual(sorted(entries), sorted(results))
        for r in FIXTURE['sources']:
            if r['resourceType'] == 'Observation':
                spec = by_id[r['specimen']['reference'].split('/')[1]]
                self.assertEqual(spec['accessionIdentifier']['value'], r['identifier'][0]['value'])

    def test_stage_inference_charts_name_no_stage(self):
        inferred = [p for p in cohort.PATIENTS if p['facts'].get('stage_recorded') is False]
        self.assertGreaterEqual(len(inferred), 18 + 3)
        words = re.compile(r'\b(primary|secondary|latent|early|late|duration|chancre|staging)\b', re.I)
        for p in inferred:
            chart = [r for r in FIXTURE['sources'] if (r.get('subject') or r.get('patient') or {}).get('reference') == 'Patient/' + KEYS[p['key']][0]]
            self.assertFalse([r for r in chart if r['resourceType'] == 'Condition'], p['key'])
            for r in chart:
                text = json.dumps({k: v for k, v in r.items() if k != 'content'})
                self.assertIsNone(words.search(text), (p['key'], r['id'], text[:200]))
        # Matched pair: the prior nonreactive test is within 12 months of diagnosis exactly when one dose is adequate.
        for p in inferred:
            if p.get('variant') in ('early1', 'lapsed1'):
                prior = next(r[1] for r in p['records'] if r[0] == 'rpr' and r[2] == 'NR')
                within = (rules.D(p['dx']) - rules.D(prior)).days <= 365
                self.assertEqual(within, p['variant'] == 'early1', p['key'])
                self.assertEqual(p['truth'].get('INADEQUATE_TREATMENT', ('not_an_issue', None))[0] == 'confirmed', not within, p['key'])

    def test_id_renaming_and_order_do_not_change_answers(self):
        with patch.object(builder, 'SALT', 'renamed-v2'):
            fixture, expected, _ = builder.build()
        self.assertNotEqual({r['id'] for r in fixture['sources']} & {r['id'] for r in FIXTURE['sources']}, None)
        self.assertFalse({r['id'] for r in fixture['sources']} & {r['id'] for r in FIXTURE['sources']})
        strip = lambda e: sorted((v['patient_key'], k.split('|')[2], v['disposition'], v['code']) for k, v in e['candidates'].items())
        self.assertEqual(strip(expected), strip(EXPECTED))
        reordered = [dict(p, records=list(reversed(p['records']))) for p in cohort.PATIENTS]
        for p in reordered:
            self.assertEqual(rules.disposition(p), rules.disposition(rules.BY_KEY[p['key']]), p['key'])


if __name__ == '__main__':
    unittest.main()
