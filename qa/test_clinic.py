"""Focused fixture, persistence, clinical acceptance, and trust-boundary checks."""
import copy
import json
import os
from pathlib import Path
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
               str(ROOT / 'chartr_task/solution')]
import fhir
import grade
import reference
import server
from store import Store


class ClinicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / 'clinic.sqlite')
        self.store.initialize()
        self.attestation = self.store.attest('offline-trial')
        server.STORE = self.store
        self.http = HTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_http)
        self.env = {**os.environ, 'CLINIC_URL': f'http://127.0.0.1:{self.http.server_port}'}

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

    def write(self, patient, status=None, evidence=None):
        if patient == 'P102':
            return self.cli('update', 'Q102', '--json', json.dumps({
                'status': status or 'resolved', 'evidence': evidence or ['D03', 'D04'],
                'explanation': 'Explicit reconciliation addresses the original concern.'}))
        data = {'patient': patient, 'episode': 'E101' if patient == 'P101' else 'E103',
                'category': 'treatment_review', 'destination': 'clinical_review',
                'reason': 'UNRESOLVED_TREATMENT_CONCERN' if patient == 'P101' else 'CONFLICTING_ACTIVE_PLANS',
                'status': status or ('open' if patient == 'P101' else 'needs_clarification'),
                'evidence': evidence or (['S01', 'S02', 'S04'] if patient == 'P101' else ['M02', 'M04']),
                'explanation': 'The cited current documentation supports clinician review.'}
        return self.cli('create', '--json', json.dumps(data))

    def finish(self):
        snapshot = self.store.collect()
        for resource in snapshot['sources'] + snapshot['queue']:
            fhir.validate(resource)
        return snapshot, grade.grade(snapshot, self.attestation)

    def test_reference_same_interface_and_regrade(self):
        with patch.object(reference, 'clinic', self.cli):
            reference.solve()
        snapshot, result = self.finish()
        self.assertEqual(result['reward'], 1)
        self.assertEqual(grade.grade(snapshot, self.attestation), result)

    def test_equivalent_evidence_and_reversed_order(self):
        with patch.object(reference, 'clinic', self.cli):
            reference.solve(order=('P103', 'P102', 'P101'), alternative=True)
        self.assertEqual(self.finish()[1]['reward'], 1)

    def test_noop_fails(self):
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_paraphrase_and_corrected_intermediate_state_pass(self):
        self.write('P101', evidence=['S03', 'S02', 'S04', 'S04'])
        self.write('P102', evidence=['D01', 'D03'])
        morgan = self.write('P103', status='resolved')
        self.cli('update', morgan['id'], '--json', json.dumps({
            'status':'needs_clarification',
            'explanation':'The two still-active orders disagree on dose count. Clinician clarification is needed.'}))
        self.assertEqual(self.finish()[1]['reward'], 1)

    def test_missing_samantha_fails(self):
        self.write('P102'); self.write('P103')
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_unresolved_darrow_fails(self):
        self.write('P101'); self.write('P103')
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_incorrect_morgan_disposition_fails(self):
        self.write('P101'); self.write('P102'); self.write('P103', status='resolved')
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_duplicate_extra_item_fails(self):
        for patient in ('P101', 'P102', 'P103', 'P103'):
            self.write(patient)
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_insufficient_evidence_fails(self):
        self.write('P101', evidence=['S01']); self.write('P102'); self.write('P103')
        self.assertEqual(self.finish()[1]['reward'], 0)

    def test_wrong_patient_episode_and_immutable_q102(self):
        original = self.cli('reviews')['items']
        self.cli('update', 'Q102', '--json', '{"patient":"P101"}', error=True)
        self.cli('update', 'Q102', '--json', '{"evidence":["S01"]}', error=True)
        self.cli('update', 'Q102', '--json', '{"status":"invented"}', error=True)
        bad = {'patient':'P101','episode':'E102','reason':'UNRESOLVED_TREATMENT_CONCERN',
               'category':'treatment_review','destination':'clinical_review','status':'open',
               'evidence':['S01'],'explanation':'Concern'}
        self.cli('create','--json',json.dumps(bad),error=True)
        self.assertEqual(self.cli('reviews')['items'], original)
        self.write('P102')
        saved = self.cli('reviews')['items'][0]
        for key in ('id', 'for', 'focus', 'authoredOn', 'reasonCode', 'code', 'owner'):
            self.assertEqual(saved[key], original[0][key])

    def test_source_readonly_no_admin_and_frozen(self):
        for path in ('/reset', '/admin', '/export', '/records/S01', '/grade'):
            status, _ = self.store.request('POST', path, {})
            self.assertEqual(status, 400)
        with self.store.connect() as db:
            for sql in ("UPDATE source SET resource='{}'", "DELETE FROM source", "INSERT INTO source VALUES ('X','{}')"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        before, _ = self.finish()
        status, _ = self.store.request('PATCH', '/reviews/Q102', {'status':'resolved'})
        self.assertEqual(status, 409)
        with self.store.connect() as db:
            self.assertEqual(self.store.rows(db, 'queue'), before['queue'])

    def test_reset_fresh_identity_and_fixture(self):
        self.write('P101'); self.write('P102')
        with self.assertRaises(RuntimeError):
            self.store.initialize()
        fresh = Store(Path(self.tmp.name) / 'fresh.sqlite')
        fresh.initialize()
        fresh_attestation = fresh.attest('second-trial')
        self.assertEqual(fresh_attestation['initial_digest'], self.attestation['initial_digest'])
        self.assertNotEqual(fresh_attestation['nonce'], self.attestation['nonce'])
        snapshot = fresh.collect()
        self.assertEqual(snapshot['queue'], [grade.BASELINE['q102']])
        self.assertEqual(snapshot['audit'], [])
        self.assertEqual(snapshot['metadata']['next_id'], 103)

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
        resource = copy.deepcopy(grade.BASELINE['q102'])
        resource['status'] = 'needs_clarification'
        with self.assertRaises(Exception):
            fhir.validate(resource)


if __name__ == '__main__':
    unittest.main()
