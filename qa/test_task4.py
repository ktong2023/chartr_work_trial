"""Answer, wrong-algorithm, fairness, leakage, service and trust checks for Task 4 (chartr_task4).

Needs an assembled source database. Set T4_BUILD to a directory holding sources.sqlite and ecg/ (built by
environment/service/assemble.py); otherwise the suite assembles one from T4_DATA (default: <repo>/data/physionet).
Run with the pinned host venv:  T4_BUILD=... .venv/bin/python -m unittest qa.test_task4 -v
"""
import base64
import gzip
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
import zlib
import sqlite3
import datetime as dt
import uuid
from http.server import ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_task4'
OVERLAY = TASK / 'environment/service/overlay'
NAMES = ['store', 'server', 'grade', 'reference', 'assemble']
saved = {n: sys.modules.pop(n) for n in NAMES if n in sys.modules}
paths = [str(TASK / 'environment/service'), str(TASK / 'tests'), str(TASK / 'solution')]
sys.path[:0] = paths
try:
    M = {n: importlib.import_module(n) for n in NAMES}
finally:
    for n in NAMES:
        sys.modules.pop(n, None)
    sys.modules.update(saved)
    for p in paths:
        sys.path.remove(p)
store, server, grade, reference, assemble = (M[n] for n in NAMES)
EXPECTED = grade.EXPECTED
NS = uuid.uuid5(uuid.NAMESPACE_OID, 'MIMIC-IV')
PID = lambda subject: str(uuid.uuid5(uuid.uuid5(NS, 'Patient'), subject))
SHORTCUTS = {  # wrong algorithm -> the case it should break
    'af_codes_only': 'AF established only by a rhythm strip (10004235)',
    'include_deceased': 'deceased patients reviewed',
    'any_order_current': 'orders current without honouring stops and validity',
    'earliest_ecg': 'oldest ECG instead of most recent',
    'every_ecg': 'findings on every ECG',
    'any_location': 'watch-list starts outside the Cardiology Clinic',
    'first_memo_forever': '30-day ECG memo after its replacement',
    'latest_memo_always': '14-day ECG memo applied before it took effect',
    'ecg_before_start_counts': 'ECG before the start completes the follow-up',
    'ignore_unreceived': 'unreceived outside ECG ignored',
    'mention_is_dose_change': 'a note about warfarin dosing without a change counts as a dose change',
    'no_charted_rhythm': 'AF from codes and ECGs only, not rhythm charting or notes (10020306)',
    'trust_documented_qt': 'a note calling the QT acceptable overrides the ECG (10013049)',
    'no_comparison': 'interpretations without the comparison with the previous ECG',
    'prior_earliest': 'compared with the oldest ECG instead of the previous one',
    'no_conduction': 'conduction abnormalities not reported',
    'rhythm_any_day': 'sinus rhythm documented in paroxysmal AF counted as a conflict',
}
BUILD = {}
CACHE = {}


def setUpModule():
    build = os.environ.get('T4_BUILD')
    if not build:
        data = Path(os.environ.get('T4_DATA', ROOT / 'data/physionet'))
        BUILD['temp'] = tempfile.TemporaryDirectory()
        build = BUILD['temp'].name
        assemble.build(data / 'mimic-iv-fhir-demo/2.1.0/fhir', data / 'mimic-iv-ecg-demo/0.1', OVERLAY,
                       Path(build) / 'sources.sqlite', Path(build) / 'ecg')
    BUILD['dir'] = Path(build)


def tearDownModule():
    if 'temp' in BUILD:
        BUILD['temp'].cleanup()


def make_store(directory):
    s = store.Store(Path(directory) / 'state.sqlite', BUILD['dir'] / 'sources.sqlite', BUILD['dir'] / 'ecg')
    s.initialize()
    return s, s.attest('task4-test')


def in_process(service):
    """The reference's clinic() and search() served from the store directly (no HTTP); source reads memoized."""
    def req(method, path, body=None):
        status, out = service.request(method, path, body)
        if status != 200:
            raise RuntimeError(f'{status} {out}')
        return out

    def clinic(*args):
        if args[0] == 'patients':
            return req('GET', '/patients')
        if args[:2] == ('ecg', 'list'):
            return req('GET', '/ecg')
        if args[0] in ('item', 'interpretation') and args[1] == 'add':
            return req('POST', '/' + args[0] + 's', json.loads(args[3]))
        if args[0] in ('items', 'interpretations'):
            return req('GET', '/' + args[0])
        raise AssertionError(args)

    def search(rtype, patient=None, code=None):
        key = (rtype, patient, code)
        if key not in CACHE:
            rows, page = [], 1
            while True:
                q = '&'.join(f'{k}={v}' for k, v in (('type', rtype), ('patient', patient), ('code', code), ('page', page)) if v is not None)
                out = req('GET', '/search?' + q)
                rows += out['resources']
                if out['complete']:
                    break
                page += 1
            CACHE[key] = rows
        return CACHE[key]
    return clinic, search


class Task4Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service, self.attestation = make_store(tempfile.mkdtemp(dir=self.temp.name))

    def run_reference(self, shortcut=None, readings=None):
        clinic, search = in_process(self.service)
        with patch.object(reference, 'clinic', clinic), patch.object(reference, 'search', search), \
             patch.object(reference, 'READINGS', readings or reference.READINGS):
            items, findings = reference.solve_all(shortcut)
            for it in items:
                clinic('item', 'add', '--json', json.dumps(it))
            for f in findings:
                clinic('interpretation', 'add', '--json', json.dumps(f))
        snap = self.service.collect()
        return items, findings, grade.grade(snap, self.attestation)

    # ------------------------------------------------------------------ answers
    def test_harbor_entrypoints_are_executable(self):
        for path in (TASK / 'solution/solve.sh', TASK / 'tests/test.sh'):
            self.assertTrue(os.access(path, os.X_OK), str(path))

    def test_baseline_matches_assembled_sources(self):
        with sqlite3.connect(BUILD['dir'] / 'sources.sqlite') as db:
            digest = db.execute("SELECT value FROM meta WHERE key='sources_digest'").fetchone()[0]
        self.assertEqual(digest, grade.BASELINE['sources_digest'])
        self.assertEqual(grade.BASELINE['version'], store.VERSION)
        self.assertEqual(grade.BASELINE['evaluation_time'], store.NOW)

    def test_reference_through_real_cli_scores_one(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.shutdown)
        env = {**os.environ, 'CLINIC_URL': f'http://127.0.0.1:{http.server_port}'}

        def cli(*args):
            out = subprocess.run([sys.executable, str(TASK / 'environment/public/clinic.py'), *args], env=env,
                                 capture_output=True, text=True, check=True)
            return json.loads(out.stdout)
        with patch.object(server, 'STORE', self.service), patch.object(reference, 'clinic', cli):
            reference.solve()
        result = grade.grade(self.service.collect(), self.attestation)
        self.assertEqual(result['reward'], 1, json.dumps(result, indent=1)[:3000])

    def test_no_op_scores_zero(self):
        result = grade.grade(self.service.collect(), self.attestation)
        self.assertEqual(result['reward'], 0)
        self.assertFalse(result['components']['identification'])
        self.assertFalse(result['components']['ecg_interpretation'])

    def test_wrong_algorithms_fail(self):
        correct_items, correct_findings, result = self.run_reference()
        self.assertEqual(result['reward'], 1, result)
        report = {}
        for shortcut, why in SHORTCUTS.items():
            with self.subTest(shortcut=shortcut):
                self.setUp()
                items, findings, result = self.run_reference(shortcut)
                failed = sorted(k for k, ok in result['components'].items() if not ok)
                report[shortcut] = failed
                self.assertEqual(result['reward'], 0, f'{shortcut} ({why}) still scores 1')
        print('\nwrong algorithm -> failing components')
        for k, v in report.items():
            print(f'  {k:26s} {", ".join(v)}')

    def test_misreadings_fail(self):
        """Reading errors: an artifact read as AF on a current ECG, a remote bleed read as a contraindication."""
        catalog = {e['study_id']: e for e in json.loads((OVERLAY / 'overlay.json').read_text())['ecg_catalog']}
        latest = {}
        for e in catalog.values():
            if e['patient'] not in latest or e['ecg_time'] > latest[e['patient']]['ecg_time']:
                latest[e['patient']] = e
        truth = json.loads((ROOT / 'qa/task4/ecg_truth.json').read_text())
        artifacts = [k for k, v in truth.items() if (v.get('edit') or '').startswith('artifact') and v['label'] == 'NORMAL']
        current_artifacts = [k for k in artifacts if latest[catalog[k]['patient']]['study_id'] == k]
        self.assertTrue(current_artifacts, 'no artifact ECG is any patient\'s most recent ECG')
        readings = json.loads(json.dumps(reference.READINGS))
        for k in current_artifacts:
            readings['ecg'][k].update(label='AF', rhythm='AF', pr_ms=None, qtc_ms=None)
        _, _, result = self.run_reference(readings=readings)
        self.assertEqual(result['reward'], 0, 'artifact read as AF')
        # LBBB missed on a living patient's latest ECG; a transient RBBB on the previous ECG missed. (The paced ECG belongs to a
        # deceased patient and is optional since v0.3.2.)
        for sid, change in (('104941853', {'conduction': []}), ('106516875', {'conduction': []})):
            self.setUp()
            readings = json.loads(json.dumps(reference.READINGS))
            readings['ecg'][sid].update(change)
            _, _, result = self.run_reference(readings=readings)
            self.assertEqual(result['reward'], 0, (sid, change))
        # Remote bleed (10005348) read as a current contraindication.
        self.setUp()
        added = [json.loads(l) for l in gzip.open(OVERLAY / 'added.ndjson.gz', 'rt')]
        notes = [r for r in added if r['resourceType'] == 'DocumentReference'
                 and r.get('subject', {}).get('reference') == 'Patient/' + PID('10005348')
                 and re.search(r'bleed', base64.b64decode(r['content'][0]['attachment']['data']).decode(), re.I)]
        self.assertTrue(notes)
        readings = json.loads(json.dumps(reference.READINGS))
        for n in notes:
            readings['notes'][n['id']] = {'contraindication': 'recent_major_bleed', 'held': 'Warfarin'}
        _, _, result = self.run_reference(readings=readings)
        self.assertEqual(result['reward'], 0)

    def test_measurement_ranges_admit_every_agreeing_method(self):
        truth = json.loads((ROOT / 'qa/task4/ecg_truth.json').read_text())
        for f in EXPECTED['interpretations']:
            t = truth[f['ecg']]; rate = f['fields']['ventricular_rate']['range']
            for method, hr in t['hr_reads'].items():
                self.assertTrue(rate[0] <= hr <= rate[1], (f['ecg'], method, hr, rate))
            if (t.get('edit') or '').startswith('qt_'):
                reads = sorted(t['qtc_reads'].values())
                median = reads[len(reads) // 2]
                for method, q in t['qtc_reads'].items():
                    if abs(q - median) <= 60:
                        self.assertTrue(f['fields']['qtc_ms']['range'][0] <= q <= f['fields']['qtc_ms']['range'][1], (f['ecg'], method, q))
                self.assertGreaterEqual(min(q for q in reads if abs(q - median) <= 60), 505, f['ecg'])

    def test_qt_decisions_consistent_with_accepted_measurements(self):
        """Audit v0.3.6: an accepted QTc reading must never imply the opposite QT-safety disposition."""
        for i in EXPECTED['items']:
            if i['reason'] == 'PROLONGED_QTC_ON_WATCH_LIST_DRUG':
                self.assertGreaterEqual(i['fields']['qtc_ms']['range'][0], 500, i['subject'])
                latest = next(e for e in EXPECTED['interpretations'] if e['patient'] == i['patient'])
                self.assertGreaterEqual(latest['fields']['qtc_ms']['range'][0], 500, i['subject'])

    def test_serial_qtc_changes_consistent_with_accepted_readings(self):
        """Audit v0.3.6: any pair of individually accepted QTc readings must imply a change set the comparison accepts."""
        interp = json.loads((ROOT / 'qa/task4/ecg_interp.json').read_text())['ecg']
        checked = 0
        for e in EXPECTED['interpretations']:
            cur, prior = e['fields']['qtc_ms'], (interp[e['prior_ecg']]['qtc_ms'] if e['prior_ecg'] else None)
            if not prior or 'range' not in cur or 'range' not in prior:
                continue
            for c in cur['range']:
                for p in prior['range']:
                    derived = set(e['changes']['required']) - {'QTC_INCREASE_60', 'QTC_DECREASE_60'}
                    if c - p >= 60: derived.add('QTC_INCREASE_60')
                    if p - c >= 60: derived.add('QTC_DECREASE_60')
                    self.assertTrue(grade.field_ok(e['changes'], sorted(derived)), (e['subject'], c, p, e['changes']))
                    checked += 1
        self.assertGreater(checked, 20)

    # ------------------------------------------------------------------ separability
    def test_case_patients_not_separable_by_added_layer(self):
        """Per-patient features of the synthetic layer: cases vs living controls (Mann-Whitney AUC)."""
        added = [json.loads(l) for l in gzip.open(OVERLAY / 'added.ndjson.gz', 'rt')]
        cases = {i['patient'] for i in EXPECTED['items']}
        by = {}
        for r in added:
            p = assemble.patient_of(r)
            if p:
                by.setdefault(p, []).append(r)
        living = set(by)
        self.assertTrue(cases <= living)
        def text(r):
            return base64.b64decode(r['content'][0]['attachment']['data']).decode()
        features = {
            'resources': lambda rs: len(rs),
            'visits': lambda rs: sum(r['resourceType'] == 'Encounter' for r in rs),
            'orders': lambda rs: sum(r['resourceType'] == 'MedicationRequest' for r in rs),
            'stopped_orders': lambda rs: sum(r.get('status') == 'stopped' for r in rs),
            'labs': lambda rs: sum(r['resourceType'] == 'Observation' for r in rs),
            'notes': lambda rs: sum(r['resourceType'] == 'DocumentReference' for r in rs),
            'note_chars': lambda rs: sum(len(text(r)) for r in rs if r['resourceType'] == 'DocumentReference'),
            'non_clinician_notes': lambda rs: sum(r['resourceType'] == 'DocumentReference' and r['extension'][0]['valueCode'] != 'clinician' for r in rs),
            'first_added': lambda rs: min(assemble.when_of(r) or '9' for r in rs),
            # v0.4 (audit): structural features beyond totals
            'min_visit_gap': lambda rs: min([(b - a).days for a, b in zip(*(lambda d: (d, d[1:]))(sorted(
                dt.date.fromisoformat(r['period']['start'][:10]) for r in rs if r['resourceType'] == 'Encounter')))] or [9999]),
            'max_note_chars': lambda rs: max([len(text(r)) for r in rs if r['resourceType'] == 'DocumentReference'] or [0]),
            'max_note_lines': lambda rs: max([len(text(r).split('\n\n')[0].splitlines()) for r in rs if r['resourceType'] == 'DocumentReference'] or [0]),
            'outside_notes': lambda rs: sum(r['resourceType'] == 'DocumentReference' and r['type']['coding'][0]['code'] == '34133-9' for r in rs),
            'last_added': lambda rs: max(assemble.when_of(r) or '' for r in rs if (assemble.when_of(r) or '') <= '2026-09-24T12'),
        }
        aucs = {}
        for name, fn in features.items():
            values = {p: fn(rs) for p, rs in by.items()}
            case_v = [values[p] for p in cases]
            ctrl_v = [values[p] for p in living - cases]
            wins = sum((a > b) + 0.5 * (a == b) for a in case_v for b in ctrl_v)
            aucs[name] = round(wins / (len(case_v) * len(ctrl_v)), 2)
        print(f'\ncase vs control AUC ({len(cases)} cases, {len(living - cases)} living controls):', aucs)
        for name, auc in aucs.items():
            self.assertLess(abs(auc - 0.5), 0.3, (name, auc))
        # No simple structural rule may isolate a group of cases: a rule that flags >= 3 cases must also flag controls.
        rules = {'visit gap < 60 days': lambda rs: features['min_visit_gap'](rs) < 60,
                 'a note with 6+ content lines': lambda rs: features['max_note_lines'](rs) >= 6,
                 'an outside-records note': lambda rs: features['outside_notes'](rs) > 0}
        for name, rule in rules.items():
            hit_cases = sum(rule(by[p]) for p in cases); hit_ctrl = sum(rule(by[p]) for p in living - cases)
            print(f'  rule {name!r}: {hit_cases}/{len(cases)} cases, {hit_ctrl}/{len(living - cases)} controls')
            if hit_cases >= 3:
                self.assertGreater(hit_ctrl, 0, name)

    def test_added_resources_have_real_shapes(self):
        """Every added resource of a type the demo has matches the key structure of some real resource of that type."""
        def shape(obj, prefix=''):
            out = set()
            if isinstance(obj, dict):
                for k, v in obj.items():
                    out |= {prefix + '.' + k} | shape(v, prefix + '.' + k)
            elif isinstance(obj, list):
                for v in obj:
                    out |= shape(v, prefix + '[]')
            return out
        def stamp(value):
            return re.sub(r'\d', '9', value) if assemble.DATETIME.match(value) else None
        added = [json.loads(l) for l in gzip.open(OVERLAY / 'added.ndjson.gz', 'rt')]
        added_ids = {r['id'] for r in added}
        with sqlite3.connect(f"file:{BUILD['dir'] / 'sources.sqlite'}?mode=ro&immutable=1", uri=True) as db:
            for rtype in ('Encounter', 'MedicationRequest', 'Observation', 'Specimen'):
                mine = [r for r in added if r['resourceType'] == rtype]
                real_shapes, real_stamps = set(), set()
                codes = sorted({assemble.code_of(r) for r in mine})
                sql = 'SELECT id, json FROM resource WHERE type = ?' + (f" AND code IN ({','.join('?' * len(codes))})" if rtype == 'Observation' else '')
                for rid, blob in db.execute(sql, (rtype, *codes) if rtype == 'Observation' else (rtype,)):
                    if rid in added_ids:
                        continue
                    r = json.loads(zlib.decompress(blob))
                    real_shapes.add(frozenset(shape(r)))
                    real_stamps |= {stamp(v) for v in json.dumps(r).split('"') if stamp(v)}
                for r in mine:
                    self.assertIn(frozenset(shape(r)), real_shapes, (rtype, r['id']))
                    got = {stamp(v) for v in json.dumps(r).split('"') if stamp(v)}
                    self.assertLessEqual(got, real_stamps, (rtype, r['id'], got - real_stamps))

    # ------------------------------------------------------------------ public surface
    def test_public_surface_has_no_answers_or_ecg_method(self):
        public = [TASK / 'instruction.md'] + sorted((TASK / 'environment/public').iterdir())
        text = '\n'.join(p.read_text() for p in public if p.is_file())
        for i in EXPECTED['items']:
            self.assertNotIn(i['subject'], text)
            self.assertNotIn(i['patient'], text)
        for f in EXPECTED['interpretations']:
            self.assertNotIn(f['ecg'], text)
        # 'Bazett' is allowed: it defines the reported qtc_ms field, not a way to measure it.
        for word in ('tangent', 'neurokit', 'delineat', 'Fridericia', 'Framingham', 'Hodges', 'RR interval', 'P wave',
                     'P-wave', 'irregularly irregular', 'lead II', 'median beat', 'T wave', 'T-wave', 'fibrillatory', 'machine'):
            self.assertNotIn(word.lower(), text.lower(), word)
        dockerignore = (TASK / 'environment/.dockerignore').read_text()
        dockerfile = (TASK / 'environment/Dockerfile').read_text()
        self.assertNotIn('solution', dockerfile)
        self.assertNotIn('tests', dockerfile)
        self.assertIn('Dockerfile', dockerignore)

    # ------------------------------------------------------------------ service contract and trust
    def request(self, method, path, body=None):
        return self.service.request(method, path, body)

    def test_service_rejects_malformed_and_foreign_writes(self):
        mine = PID('10039997')
        other_cond = next(r['id'] for r in self.request('GET', f'/search?type=Condition&patient={PID("10023771")}')[1]['resources'])
        base = {'patient': mine, 'category': 'ANTICOAGULATION', 'reason': 'UNTREATED_AF'}
        for body in ({**base, 'extra': 1}, {**base, 'reason': 'DUAL_ANTICOAGULATION'}, {**base, 'af_evidence': [other_cond]},
                     {**base, 'risk_score': 12}, {**base, 'risk_factors': ['OBESITY']}, {**base, 'status': 'done'},
                     {**base, 'due_date': '09/24/2026'}, {**base, 'qtc_ms': True}, {**base, 'patient': 'nobody'}, [], None,
                     {**base, 'explanation': 'x' * 4001}):
            status, _ = self.request('POST', '/items', body)
            self.assertEqual(status, 400, body if not isinstance(body, dict) else {k: str(v)[:40] for k, v in body.items()})
        e = next(f for f in EXPECTED['interpretations'] if f['prior_ecg'])
        other = next(f for f in EXPECTED['interpretations'] if f['patient'] != e['patient'])
        good = {'ecg': e['ecg'], 'rhythm': 'SINUS', 'ventricular_rate': 70}
        for body in ({'ecg': 'nope', 'rhythm': 'SINUS', 'ventricular_rate': 70}, {**good, 'rhythm': 'VT'}, {**good, 'axis': 'UP'},
                     {**good, 'conduction': ['LAFB']}, {**good, 'changes': ['NEW_AF', 'NEW_AF']}, {**good, 'prior_ecg': other['ecg']},
                     {**good, 'prior_ecg': e['ecg']}, {**good, 'ventricular_rate': None}, {**good, 'finding': 'AF'}, {**good, 'qrs_ms': -5}):
            self.assertEqual(self.request('POST', '/interpretations', body)[0], 400, body)
        self.assertEqual(self.request('POST', '/interpretations', {**good, 'prior_ecg': e['prior_ecg']})[0], 200)
        self.assertEqual(self.request('POST', '/findings', {'ecg': e['ecg'], 'finding': 'AF'})[0], 400)
        for method, path in (('POST', '/search'), ('PUT', '/items'), ('DELETE', '/items/I1'), ('POST', '/admin'),
                             ('GET', '/search?type=Condition&page=x'), ('GET', '/search?type=Condition&since=2026')):
            self.assertEqual(self.request(method, path, {})[0], 400, path)
        status, item = self.request('POST', '/items', base)
        self.assertEqual(status, 200)
        self.assertEqual(self.request('PATCH', '/items/' + item['id'], {'reason': 'DUAL_ANTICOAGULATION'})[0], 400)
        self.assertEqual(self.request('PATCH', '/items/' + item['id'], {'risk_score': 5})[0], 200)
        snap = self.service.collect()
        self.assertEqual(self.request('POST', '/items', base)[0], 409)
        grade.check_integrity(snap, self.attestation)  # rejected writes left state and audit consistent

    def test_forged_or_foreign_snapshots_are_invalid(self):
        _, _, _ = self.run_reference()
        snap = self.service.collect()
        forged = json.loads(json.dumps(snap)); forged['items'].append(dict(forged['items'][0], id='I999'))
        other = json.loads(json.dumps(snap)); other['metadata']['sources_digest'] = '0' * 64
        unfrozen = json.loads(json.dumps(snap)); unfrozen['metadata']['frozen'] = False
        faulty = json.loads(json.dumps(snap)); faulty['metadata']['faults'] = 1
        for bad in (forged, other, unfrozen, faulty):
            with self.assertRaises(grade.EvaluationError):
                grade.grade(bad, self.attestation)
        with self.assertRaises(grade.EvaluationError):
            grade.grade(snap, dict(self.attestation, nonce='other'))

    def test_concurrent_http_requests_are_atomic(self):
        """Parallel reads and writes over HTTP (audit v0.3.6 found duplicate audit sequence numbers and silent failures)."""
        import urllib.request
        from concurrent.futures import ThreadPoolExecutor
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.shutdown)
        base = f'http://127.0.0.1:{http.server_port}'
        mine = PID('10039997')

        def call(i):
            if i % 10 == 0:   # interleave writes with the reads
                body = json.dumps({'patient': mine, 'category': 'ANTICOAGULATION', 'reason': 'UNTREATED_AF', 'explanation': str(i)}).encode()
                req = urllib.request.Request(base + '/items', data=body, method='POST', headers={'Content-Type': 'application/json'})
            else:
                req = urllib.request.Request(base + ('/ecg' if i % 2 else '/search?type=Condition&patient=' + mine))
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status
        with patch.object(server, 'STORE', self.service), ThreadPoolExecutor(8) as pool:
            statuses = list(pool.map(call, range(80)))
        self.assertEqual(statuses, [200] * 80)
        snap = self.service.collect()
        self.assertEqual(snap['metadata']['faults'], 0)
        self.assertEqual([e['seq'] for e in snap['audit']], list(range(1, 81)))
        self.assertEqual(len(snap['items']), 8)
        grade.check_integrity(snap, self.attestation)

    def test_audit_failure_is_a_fault(self):
        with patch.object(self.service, 'audited_in_transaction', side_effect=sqlite3.OperationalError('disk I/O error')):
            status, _ = self.service.request('GET', '/ecg')
        self.assertEqual(status, 500)
        self.assertEqual(self.service.collect()['metadata']['faults'], 1)

    def test_http_body_limit(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=http.serve_forever, daemon=True).start()
        self.addCleanup(http.shutdown)
        import urllib.request, urllib.error
        with patch.object(server, 'STORE', self.service):
            body = json.dumps({'patient': PID('10039997'), 'explanation': 'x' * 20000}).encode()
            req = urllib.request.Request(f'http://127.0.0.1:{http.server_port}/items', data=body, method='POST',
                                         headers={'Content-Type': 'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(req, timeout=30)
            self.assertEqual(caught.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
