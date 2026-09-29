"""Focused fixture, persistence, clinical acceptance, anti-shortcut, and trust-boundary checks."""
import copy
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'chartr_task/environment/service'), str(ROOT / 'chartr_task/tests'),
               str(ROOT / 'chartr_task/solution'), str(ROOT / 'qa')]
import build_fixture
import fhir
import grade
import reference
import server
from store import Store

rid = build_fixture.rid
SKIP = 'skip'
FIELDS = ('item', 'reason', 'status', 'evidence', 'alternative', 'explanation')
TR, FU = 'treatment_review', 'follow_up'
FIXTURE = json.loads((ROOT / 'chartr_task/environment/service/fixture.json').read_text())
COHORT = {r['id'] for r in FIXTURE['sources'] if r['resourceType'] == 'Patient'}
EXPECTED = {key: value for key, value in grade.EXPECTED.items() if key[0] in COHORT}


def variant(key, **changes):
    """A reference case with some fields replaced; evidence is given as private record keys."""
    fields = dict(zip(FIELDS, reference.CASES[key]))
    if 'evidence' in changes:
        changes['evidence'] = [rid(k) for k in changes['evidence']]
    fields.update(changes)
    return tuple(fields[f] for f in FIELDS)


class ClinicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.http = HTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_http)
        self.env = {**os.environ, 'CLINIC_URL': f'http://127.0.0.1:{self.http.server_port}'}
        self.fresh()

    def fresh(self):
        # New trial state behind the same listener; the handler reads server.STORE per request.
        self.store = Store(Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'clinic.sqlite')
        self.store.initialize()
        self.attestation = self.store.attest('offline-trial')
        server.STORE = self.store

    def stop_http(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()

    def cli(self, *args, error=False):
        result = subprocess.run([sys.executable, str(ROOT / 'chartr_task/environment/public/clinic.py'), *args],
                                env=self.env, capture_output=True, text=True)
        if error:
            self.assertEqual(result.returncode, 2, result.stderr)
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def direct(self, *args, error=False):
        """In-process twin of the clinic CLI for bulk variant tests; the CLI itself is tested separately."""
        command, rest = args[0], list(args[1:])
        if command == 'patients':
            call = ('GET', '/patients', None)
        elif command == 'records':
            call = ('GET', '/records/' + rest[0], None)
        elif command == 'reviews':
            call = ('GET', '/reviews' + ('/' + rest[1] if rest else ''), None)
        elif command == 'create':
            call = ('POST', '/reviews', json.loads(rest[1]))
        else:
            call = ('PATCH', '/reviews/' + rest[0], json.loads(rest[2]))
        status, body = self.store.request(*call)
        self.assertEqual(status, 400 if error else 200, body)
        return body

    def create(self, patient, category, reason, status, evidence, error=False, client=None):
        return (client or self.direct)('create', '--json', json.dumps({
            'patient': patient, 'episode': 'E' + patient[1:], 'category': category, 'reason': reason,
            'destination': reference.DESTINATIONS[category], 'status': status,
            'evidence': [rid(k) for k in evidence], 'explanation': 'The cited records support this review item.'}),
            error=error)

    def solve(self, changes=None, alternative=False, order=None, client=None):
        cases = {k: v for k, v in {**reference.CASES, **(changes or {})}.items() if v != SKIP}
        with patch.object(reference, 'clinic', client or self.direct), patch.object(reference, 'CASES', cases):
            reference.solve(order=order, alternative=alternative)

    def finish(self):
        snapshot = self.store.collect()
        for resource in snapshot['sources'] + snapshot['queue']:
            fhir.validate(resource)
        return snapshot, grade.grade(snapshot, self.attestation)

    def assert_variants_fail(self, variants):
        for name, (changes, extra) in variants.items():
            if not {key[0] for key in changes} | {args[0] for args in extra} <= COHORT:
                continue  # Case switched off for calibration.
            with self.subTest(name):
                self.fresh()
                self.solve(changes)
                for args in extra:
                    self.create(*args)
                self.assertEqual(self.finish()[1]['reward'], 0)

    def test_reference_same_interface_and_regrade(self):
        self.solve(client=self.cli)
        snapshot, result = self.finish()
        self.assertEqual(result['reward'], 1)
        self.assertEqual(grade.grade(snapshot, self.attestation), result)

    def test_equivalent_evidence_and_reversed_order(self):
        self.solve(alternative=True, order=list(reversed(list(reference.CASES))))
        self.assertEqual(self.finish()[1]['reward'], 1)

    def test_noop_fails(self):
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_paraphrase_repeated_citations_and_corrected_intermediate_state_pass(self):
        self.solve({('P101', TR): variant(('P101', TR), evidence=['S03', 'S02', 'S04', 'S04']), ('P107', FU): SKIP})
        item = self.create('P107', FU, 'FOLLOW_UP_TIMING_UNCLEAR', 'resolved', ['P107.planA', 'P107.planB'])
        self.direct('update', item['id'], '--json', json.dumps({
            'status': 'needs_clarification',
            'explanation': 'The 3-month and 6-month RPR plans are both current. A clinician must pick one timing.'}))
        self.assertEqual(self.finish()[1]['reward'], 1)

    def test_treatment_review_errors_fail(self):
        k = {p: (p, TR) for p in ('P101', 'P102', 'P103', 'P114', 'P117', 'P119')}
        self.assert_variants_fail({
            'Samantha omitted': ({k['P101']: SKIP}, ()),
            'Samantha created resolved': ({k['P101']: variant(k['P101'], status='resolved')}, ()),
            'Darrow left open': ({k['P102']: SKIP}, ()),
            'Darrow replaced by a new item': (
                {k['P102']: SKIP}, [('P102', TR, 'UNRESOLVED_TREATMENT_CONCERN', 'resolved', ['D03', 'D04'])]),
            'Morgan resolved by choosing a regimen': ({k['P103']: variant(k['P103'], status='resolved')}, ()),
            'Morgan filed as an unresolved concern': (
                {k['P103']: variant(k['P103'], reason='UNRESOLVED_TREATMENT_CONCERN', status='open')}, ()),
            'Morgan duplicated': ({}, [('P103', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['M02', 'M04'])]),
            'Structurally valid conflict on the wrong patient': (
                {k['P103']: SKIP}, [('P104', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['P104.rx', 'P104.plan'])]),
            'P111 discontinued order still read as active': (
                {}, [('P111', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['P111.rxA', 'P111.rxB'])]),
            'P114 pregnancy result taken as resolution': ({k['P114']: SKIP}, ()),
            'P114 created resolved': ({k['P114']: variant(k['P114'], status='resolved')}, ()),
            'P117 regimen conflict omitted': ({k['P117']: SKIP}, ()),
            'P117 regimen chosen': ({k['P117']: variant(k['P117'], status='resolved')}, ()),
            'P118 addressed missed dose flagged': (
                {}, [('P118', TR, 'UNRESOLVED_TREATMENT_CONCERN', 'open', ['P118.nurse'])]),
            'P121 later reassessment taken as superseding': ({('P121', TR): SKIP}, ()),
            'P122 normal CSF taken as cancelling the IV order': ({('P122', TR): SKIP}, ()),
            'P123 explicit cancellation missed': (
                {}, [('P123', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['P123.rxA', 'P123.rxB'])]),
            'P125 held order still read as current': (
                {}, [('P125', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['P125.rxA', 'P125.rxB'])]),
            'P129 resumption missed': ({('P129', TR): SKIP}, ()),
            'P130 retraction ignored': ({('P130', TR): SKIP}, ()),
            'P130 new item instead of reopening': (
                {('P130', TR): SKIP}, [('P130', TR, 'UNRESOLVED_TREATMENT_CONCERN', 'open', ['P130.nurse'])]),
            'P119 resolved on the allergy note': (
                {k['P119']: variant(k['P119'], status='resolved', evidence=['P119.tel', 'P119.note2'])}, ()),
        })

    def test_follow_up_errors_fail(self):
        k = {p: (p, FU) for p in ('P105', 'P106', 'P107', 'P108', 'P109', 'P110', 'P112', 'P113', 'P116', 'P117')}
        self.assert_variants_fail({
            'P104 due date counted from the first dose': (
                {}, [('P104', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P104.plan'])]),
            'P105 resolved on recall removal and patient report': (
                {k['P105']: variant(k['P105'], status='resolved', evidence=['P105.recall', 'P105.msg1'])}, ()),
            'P106 treated as scheduled': ({k['P106']: SKIP}, ()),
            'P106 injection soreness flagged': (
                {}, [('P106', TR, 'UNRESOLVED_TREATMENT_CONCERN', 'open', ['P106.nurse'])]),
            'P107 treated as overdue': (
                {k['P107']: variant(k['P107'], reason='OVERDUE_FOLLOW_UP', status='open')}, ()),
            'P107 later plan taken as controlling': ({k['P107']: SKIP}, ()),
            'P107 filed as a treatment conflict': (
                {k['P107']: SKIP},
                [('P107', TR, 'CONFLICTING_ACTIVE_PLANS', 'needs_clarification', ['P107.planA', 'P107.planB'])]),
            'P108 left open after completion': ({k['P108']: SKIP}, ()),
            'P108 twelve-month plan flagged': ({}, [('P108', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P108.plan12'])]),
            'P109 unrelated visit taken as completion': ({k['P109']: SKIP}, ()),
            'P110 left open': ({k['P110']: SKIP}, ()),
            'P110 stale plan read as a timing conflict': (
                {k['P110']: SKIP},
                [('P110', FU, 'FOLLOW_UP_TIMING_UNCLEAR', 'needs_clarification', ['P110.plan1', 'P110.plan2'])]),
            'P110 replacement plan flagged': ({}, [('P110', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P110.plan2'])]),
            'P110 addressed treatment concern recorded as a new item': (
                {}, [('P110', TR, 'UNRESOLVED_TREATMENT_CONCERN', 'resolved', ['P110.tel', 'P110.note2'])]),
            'Darrow planned serology flagged': (
                {}, [('P102', FU, 'FOLLOW_UP_TIMING_UNCLEAR', 'needs_clarification', ['D09'])]),
            'P112 plan record read over the addendum': ({k['P112']: SKIP}, ()),
            'P113 outside result not accepted': ({k['P113']: SKIP}, ()),
            'P115 completed six-month plan flagged': (
                {}, [('P115', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P115.plan6'])]),
            'P116 resolved on the misfiled result': (
                {k['P116']: variant(k['P116'], status='resolved', evidence=['P116.plan', 'P116.misfiled'])}, ()),
            'P117 follow-up omitted': ({k['P117']: SKIP}, ()),
            'P117 follow-up filed as timing unclear': (
                {k['P117']: variant(k['P117'], reason='FOLLOW_UP_TIMING_UNCLEAR', status='needs_clarification')}, ()),
            'P118 wrong anchor or superseded interval': (
                {}, [('P118', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P118.planA'])]),
            'P118 replaced plan read as a timing conflict': (
                {}, [('P118', FU, 'FOLLOW_UP_TIMING_UNCLEAR', 'needs_clarification', ['P118.planA', 'P118.planB'])]),
            'P124 unstated revision assumed': ({('P124', FU): SKIP}, ()),
            'P124 earlier plan taken as controlling': (
                {('P124', FU): variant(('P124', FU), reason='OVERDUE_FOLLOW_UP', status='open')}, ()),
            'P126 retracted revision applied': ({('P126', FU): SKIP}, ()),
            'P126 retracted plan read as a timing conflict': (
                {('P126', FU): variant(('P126', FU), reason='FOLLOW_UP_TIMING_UNCLEAR', status='needs_clarification')}, ()),
            'P127 duplicate and not-given doses counted': (
                {}, [('P127', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P127.plan'])]),
            'P128 corrected result read as invalid': ({('P128', FU): SKIP}, ()),
            'P128 resolved on the rejected result': (
                {('P128', FU): variant(('P128', FU), evidence=['P128.rpr1', 'P128.plan'])}, ()),
            'P131 nurse revision applied': ({}, [('P131', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P131.nplan'])]),
            'P132 erroneous restart used': ({('P132', FU): SKIP}, ()),
            'P120 nurse recall read as a requirement': (
                {}, [('P120', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P120.nplan'])]),
            'P120 nurse recall read as a timing conflict': (
                {}, [('P120', FU, 'FOLLOW_UP_TIMING_UNCLEAR', 'needs_clarification', ['P120.plan', 'P120.nplan'])]),
        })

    def test_insufficient_evidence_fails(self):
        for key, evidence in ((('P101', TR), ['S01']), (('P107', FU), ['P107.planA', 'P107.note2']),
                              (('P108', FU), ['P108.plan6', 'P108.order']), (('P110', FU), ['P110.plan2']),
                              (('P112', FU), ['P112.plan', 'P112.dose']), (('P113', FU), ['P113.plan', 'P113.msg1']),
                              (('P117', FU), ['P117.rxA', 'P117.rxB'])):
            if key[0] not in COHORT:
                continue
            with self.subTest(key):
                self.fresh()
                self.solve({key: variant(key, evidence=evidence)})
                result = self.finish()[1]
                self.assertEqual(result['reward'], 0)
                self.assertFalse(result['cases']['/'.join(key)]['evidence'])

    def test_extraneous_record_citation_fails(self):
        for key, extra in ((('P101', TR), 'S07'), (('P106', FU), 'P106.cnote'), (('P108', FU), 'P108.stires'),
                           (('P102', TR), 'D09'), (('P114', TR), 'P114.rpr0'), (('P119', TR), 'P119.msg')):
            if key[0] not in COHORT:
                continue
            with self.subTest(key):
                self.fresh()
                evidence = [k for k, v in grade.R.items() if v in EXPECTED[key]['allowed']] + [extra]
                self.solve({key: variant(key, evidence=evidence)})
                result = self.finish()[1]
                self.assertEqual(result['reward'], 0)
                self.assertFalse(result['cases']['/'.join(key)]['evidence'])

    def test_all_relevant_records_pass_but_whole_chart_fails(self):
        every = {key: variant(key, evidence=[k for k, v in grade.R.items() if v in expected['allowed']])
                 for key, expected in EXPECTED.items()}
        self.solve(every)
        self.assertEqual(self.finish()[1]['reward'], 1)
        self.fresh()
        chart = [r['id'] for r in self.direct('records', 'P129')['resources'] if 'subject' in r]
        item, reason, status, _, alternative, explanation = reference.CASES[('P129', TR)]
        self.solve({('P129', TR): (item, reason, status, chart, alternative, explanation)})
        result = self.finish()[1]
        self.assertEqual(result['reward'], 0)
        self.assertFalse(result['cases']['P129/treatment_review']['evidence'])

    def test_records_chronological_and_charts_fit_tool_output(self):
        for entry in self.cli('patients')['patients']:
            patient = entry['patient']['id']
            output = subprocess.run([sys.executable, str(ROOT / 'chartr_task/environment/public/clinic.py'),
                                     'records', patient], env=self.env, capture_output=True, text=True).stdout
            times = [next((e['valueDateTime'] for e in r.get('extension', []) if e['url'].endswith('/event-time')), '')
                     for r in json.loads(output)['resources']]
            self.assertEqual(times, sorted(times), patient)
            self.assertLess(len(output), 20000, patient)

    def test_no_id_type_role_label_or_author_shortcut(self):
        sources = self.store.collect()['sources']
        clinical = [r for r in sources if 'subject' in r]
        self.assertTrue(all(re.fullmatch(r'R\d{6}', r['id']) for r in clinical))
        self.assertEqual(len({r['id'] for r in clinical}), len(clinical))
        citable = {p: set() for p in {r['subject']['reference'][8:] for r in clinical}}
        for (patient, _), expected in EXPECTED.items():
            citable[patient] |= expected['allowed']
        every_citable = set().union(*citable.values())

        def event(r):
            return next(e['valueDateTime'] for e in r['extension'] if e['url'].endswith('/event-time'))
        for patient, allowed in citable.items():
            chart = [r for r in clinical if r['subject']['reference'] == 'Patient/' + patient]
            self.assertNotEqual([event(r) for r in sorted(chart, key=lambda r: r['id'])],
                                sorted(event(r) for r in chart), patient)
            inside = [int(i[1:]) for i in allowed]
            outside = [int(r['id'][1:]) for r in chart if r['id'] not in allowed]
            if inside and outside:
                self.assertFalse(max(outside) < min(inside) or max(inside) < min(outside), patient)

        def features(r):
            found = {('type', r['resourceType']),
                     ('role', next(e['valueCode'] for e in r['extension'] if e['url'].endswith('/author-role')))}
            if r['resourceType'] == 'DocumentReference':
                found |= {('label', r['type']['text']), ('author', r['author'][0]['display'])}
            return found
        on_citable = set().union(*(features(r) for r in clinical if r['id'] in every_citable))
        elsewhere = set().union(*(features(r) for r in clinical if r['id'] not in every_citable))
        self.assertEqual(on_citable - elsewhere, set())
        self.assertGreaterEqual(sum(r.get('docStatus') == 'final' for r in clinical if r['id'] not in every_citable), 4)

    def test_grader_and_reference_ids_match_generator(self):
        self.assertEqual({k: rid(k) for k in grade.R}, grade.R)
        cited = {i for case in reference.CASES.values() for group in (case[3], case[4]) if group for i in group}
        self.assertLessEqual(cited, set(grade.R.values()))
        self.assertEqual(set(reference.CASES), set(grade.EXPECTED))

    def test_wrong_patient_episode_combinations_and_immutable_seeded_items(self):
        original = self.cli('reviews')['items']
        self.cli('update', 'Q2146', '--json', '{"patient":"P101"}', error=True)
        self.cli('update', 'Q2146', '--json', json.dumps({'evidence': [rid('S01')]}), error=True)
        self.cli('update', 'Q2146', '--json', '{"status":"invented"}', error=True)
        bad = {'patient': 'P101', 'episode': 'E102', 'reason': 'UNRESOLVED_TREATMENT_CONCERN',
               'category': 'treatment_review', 'destination': 'clinical_review', 'status': 'open',
               'evidence': [rid('S01')], 'explanation': 'Concern'}
        self.cli('create', '--json', json.dumps(bad), error=True)
        for category, destination, reason in (('follow_up', 'clinical_review', 'OVERDUE_FOLLOW_UP'),
                                              ('treatment_review', 'clinical_review', 'OVERDUE_FOLLOW_UP'),
                                              ('follow_up', 'follow_up_coordination', 'CONFLICTING_ACTIVE_PLANS'),
                                              ('billing', 'clinical_review', 'UNRESOLVED_TREATMENT_CONCERN')):
            self.cli('create', '--json', json.dumps({**bad, 'episode': 'E101', 'category': category,
                                                     'destination': destination, 'reason': reason}), error=True)
        self.assertEqual(self.cli('reviews')['items'], original)
        self.solve()
        saved = {r['id']: r for r in self.direct('reviews')['items']}
        for seeded in grade.BASELINE['queue']:
            for key in ('id', 'for', 'focus', 'authoredOn', 'reasonCode', 'code', 'owner'):
                self.assertEqual(saved[seeded['id']][key], seeded[key])

    def test_typed_evidence_references_accepted_when_type_matches(self):
        item = self.direct('update', 'Q2146', '--json', json.dumps({
            'status': 'resolved', 'evidence': ['DocumentReference/' + rid('D03'), rid('D04')],
            'explanation': 'The clinician replaced the penicillin order.'}))
        self.assertEqual(sorted(i['valueReference']['reference'] for i in item['input']),
                         sorted(['DocumentReference/' + rid('D03'), 'MedicationRequest/' + rid('D04')]))
        self.direct('update', 'Q2146', '--json', json.dumps({'evidence': ['MedicationRequest/' + rid('D03')]}), error=True)

    def test_unsupported_whitespace_is_recoverable_validation_error(self):
        bad = {'patient':'P101','episode':'E101','reason':'UNRESOLVED_TREATMENT_CONCERN',
               'category':'treatment_review','destination':'clinical_review','status':'open',
               'evidence':[rid('S01'), rid('S02'), rid('S04')],'explanation':'Pending pregnancy result.'}
        self.cli('create', '--json', json.dumps(bad), error=True)
        for text in ('Pending review.', 'a b', 'a b', 'a\fb'):
            self.cli('update', 'Q2146', '--json', json.dumps({'explanation': text}), error=True)
        self.solve()
        snapshot, result = self.finish()
        self.assertEqual(snapshot['metadata']['faults'], 0)
        self.assertEqual((result['validity'], result['reward']), ('valid', 1))

    def test_source_readonly_no_admin_and_frozen(self):
        for path in ('/reset', '/admin', '/export', '/records/' + rid('S01'), '/grade'):
            status, _ = self.store.request('POST', path, {})
            self.assertEqual(status, 400)
        with self.store.connect() as db:
            for sql in ("UPDATE source SET resource='{}'", "DELETE FROM source", "INSERT INTO source VALUES ('X','{}')"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        before, _ = self.finish()
        status, _ = self.store.request('PATCH', '/reviews/Q2146', {'status':'resolved'})
        self.assertEqual(status, 409)
        with self.store.connect() as db:
            self.assertEqual(self.store.rows(db, 'queue'), before['queue'])

    def test_reset_fresh_identity_and_fixture(self):
        first = self.attestation
        self.solve()
        with self.assertRaises(RuntimeError):
            self.store.initialize()
        self.fresh()
        self.assertEqual(self.attestation['initial_digest'], first['initial_digest'])
        self.assertNotEqual(self.attestation['nonce'], first['nonce'])
        self.assertEqual(self.store.collect()['queue'], grade.BASELINE['queue'])
        self.fresh()
        next_id = 'Q' + str(max(int(q['id'][1:]) for q in grade.BASELINE['queue']) + 1)
        self.assertEqual(self.create('P112', FU, 'OVERDUE_FOLLOW_UP', 'open', ['P112.addendum'])['id'], next_id)

    def test_invalid_evaluation_distinct_from_failure(self):
        snapshot, result = self.finish()
        self.assertEqual(result['validity'], 'valid')
        for key, value in (('nonce','wrong'), ('frozen',False), ('faults',1), ('initial_digest','wrong')):
            altered = copy.deepcopy(snapshot)
            altered['metadata'][key] = value
            with self.assertRaises(grade.EvaluationError):
                grade.grade(altered, self.attestation)
        with self.assertRaises(grade.EvaluationError):
            grade.grade({}, self.attestation)
        with tempfile.TemporaryDirectory() as out:
            (Path(out)/'reward.txt').write_text('0')
            result = subprocess.run([sys.executable, str(ROOT/'chartr_task/tests/grade.py'),
                                     str(Path(out)/'missing.json'), str(Path(out)/'missing-attestation.json'),out])
            self.assertEqual(result.returncode, 2)
            self.assertFalse((Path(out)/'reward.txt').exists())
            self.assertEqual(json.loads((Path(out)/'diagnostics.json').read_text())['validity'], 'evaluation_error')

    def test_r4_schema_rejects_invented_status(self):
        resource = copy.deepcopy(grade.BASELINE['queue'][0])
        resource['status'] = 'needs_clarification'
        with self.assertRaises(Exception):
            fhir.validate(resource)


if __name__ == '__main__':
    unittest.main()
