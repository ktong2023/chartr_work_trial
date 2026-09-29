"""Independent-answer, shortcut, service, and trust checks for the dependent-history probe."""
import base64
import copy
import hashlib
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

ROOT=Path(__file__).resolve().parents[1];TASK=ROOT/'chartr_probe'
NAMES=['fhir','store','server','grade','reference','build_probe','probe_cases']
saved={n:sys.modules.pop(n) for n in NAMES if n in sys.modules}
paths=[str(TASK/'environment/service'),str(TASK/'tests'),str(TASK/'solution'),str(ROOT/'qa')]
sys.path[:0]=paths
try:M={n:importlib.import_module(n) for n in NAMES}
finally:
    for n in NAMES:sys.modules.pop(n,None)
    sys.modules.update(saved)
    for p in paths:sys.path.remove(p)
store,server,grade,reference,builder=(M[n] for n in ['store','server','grade','reference','build_probe'])
FIXTURE=json.loads((TASK/'environment/service/fixture.json').read_text())
SHORTCUTS=('structured_only','latest_note','ignore_retractions','whole_note_retraction','latest_plan','stale_sequence','first_three','latest_dose','any_episode_result','any_time_result')


def chart(patient):
    return [r for r in FIXTURE['sources'] if r.get('subject',{}).get('reference')=='Patient/'+patient]


def matches(out,expected):
    return all(out[k]==expected[k] for k in ('status','plan','course','completion_date','due_date')) and set(out['doses'])==set(expected['doses']) and (out['result'] in expected['results'] if expected['results'] else out['result'] is None)


def answers(shortcut=None):
    return [reference.reconstruct(chart(p),p,e,shortcut) for p,e in FIXTURE['targets'].items()]


class ProbeTests(unittest.TestCase):
    def test_harbor_entrypoints_are_executable(self):
        for path in (TASK/'solution/solve.sh',TASK/'tests/test.sh'):
            self.assertTrue(os.access(path,os.X_OK),str(path))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.fresh()

    def fresh(self):
        self.service=store.Store(Path(tempfile.mkdtemp(dir=self.temp.name))/'clinic.sqlite')
        self.service.initialize();self.attestation=self.service.attest('probe-test')

    def submit(self,payload):
        status,body=self.service.request('POST','/determinations',payload)
        self.assertEqual(status,200,body);return body

    def finish(self):
        snap=self.service.collect();return snap,grade.grade(snap,self.attestation)

    def test_independent_public_solver_agrees_with_authored_answers(self):
        for a in answers():self.assertTrue(matches(a,grade.EXPECTED[a['patient']]),a);self.submit(a)
        snapshot,result=self.finish();self.assertEqual(result['reward'],1,result)
        self.assertEqual(grade.grade(snapshot,self.attestation),result)

    def test_reference_through_cli(self):
        server.STORE=self.service
        http=HTTPServer(('127.0.0.1',0),server.Handler);t=threading.Thread(target=http.serve_forever,daemon=True);t.start()
        self.addCleanup(lambda:(http.shutdown(),http.server_close(),t.join()))
        def cli(*args):
            p=subprocess.run([sys.executable,str(TASK/'environment/public/clinic.py'),*args],env={**os.environ,'CLINIC_URL':f'http://127.0.0.1:{http.server_port}'},capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)
        with patch.object(reference,'clinic',cli):reference.solve()
        self.assertEqual(self.finish()[1]['reward'],1)

    def test_each_shortcut_fails(self):
        for shortcut in SHORTCUTS:
            with self.subTest(shortcut=shortcut):
                self.fresh()
                for a in answers(shortcut):self.submit(a)
                self.assertEqual(self.finish()[1]['reward'],0,shortcut)

    def test_noop_duplicate_missing_and_wrong_intermediate_fields_fail(self):
        self.assertEqual(self.finish()[1]['reward'],0)
        good=answers()
        for variant in ('duplicate','missing','course','completion_date','doses','due_date','plan'):
            with self.subTest(variant=variant):
                self.fresh();payloads=copy.deepcopy(good)
                if variant=='duplicate':payloads.append(payloads[0])
                elif variant=='missing':payloads.pop()
                elif variant=='doses':payloads[0]['doses']=[]
                else:payloads[0][variant]=None
                for a in payloads:self.submit(a)
                self.assertEqual(self.finish()[1]['reward'],0)

    def test_alternative_result_and_dose_order_pass(self):
        for a in answers():
            possible=grade.EXPECTED[a['patient']]['results']
            if possible:a['result']=possible[-1]
            a['doses'].reverse();self.submit(a)
        self.assertEqual(self.finish()[1]['reward'],1)

    def test_bad_types_are_recoverable_and_semantic_errors_are_not_blocked(self):
        good=answers()[0]
        for key,value in [('patient',[]),('patient',{}),('patient',None),('patient',42),('episode',{}),('plan',[]),('course',{}),('doses',{}),('doses',[None]),('completion_date',[]),('status',[]),('explanation',{})]:
            with self.subTest(key=key,value=value):
                status,_=self.service.request('POST','/determinations',{**good,key:value});self.assertEqual(status,400)
        # A wrong clinical conclusion is operationally valid and receives no grader feedback.
        item=self.submit({**good,'status':'completed','result':None})
        self.assertNotIn('reward',item)
        with self.service.connect() as db:self.assertEqual(self.service.metadata(db)['faults'],0)
        self.assertEqual(self.finish()[1]['validity'],'valid')

    def test_updates_preserve_patient_and_episode(self):
        good=answers()[0];item=self.submit(good)
        self.assertEqual(self.service.request('PATCH','/determinations/'+item['id'],{'episode':'wrong'})[0],400)
        status,new=self.service.request('PATCH','/determinations/'+item['id'],{'explanation':'Updated wording.'})
        self.assertEqual(status,200);self.assertEqual(new['for'],item['for']);self.assertEqual(new['focus'],item['focus'])

    def test_read_only_freeze_and_invalid_evaluation(self):
        for path in ('/history','/export','/grade','/reset'):
            self.assertEqual(self.service.request('GET',path)[0],400)
        self.assertEqual(self.service.request('POST','/records',{})[0],400)
        snapshot,_=self.finish()
        self.assertEqual(self.service.request('GET','/patients')[0],409)
        snapshot['metadata']['nonce']='forged'
        with self.assertRaises(grade.EvaluationError):grade.grade(snapshot,self.attestation)

    def test_generator_schema_attachments_and_no_answer_summaries(self):
        fixture,expected=builder.build();self.assertEqual(fixture,FIXTURE);self.assertEqual(expected,grade.EXPECTED)
        for r in fixture['sources']:
            if r['resourceType']=='DocumentReference':
                self.assertEqual(base64.b64decode(r['content'][0]['attachment']['data']).decode(),r['description'])
                self.assertNotRegex(r['description'],r'(?i)overdue|not_due|no_requirement|course (?:was )?completed|due date is')
        for p in fixture['targets']:self.assertLess(len(json.dumps(chart(p),indent=2)),45000)
        public='\n'.join(p.read_text() for p in (TASK/'environment/public').glob('*') if p.is_file())
        self.assertNotRegex(public,r'probe_cases|EXPECTED|expected.json|answers.json|P[0-9a-f]{7}\b|R[0-9a-f]{12}\b')

    def test_id_renaming_and_presentation_order_do_not_change_answers(self):
        ids={r['id'] for r in FIXTURE['sources']}
        mapping={i:('R'+hashlib.sha256(('renamed'+i).encode()).hexdigest()[:12] if i.startswith('R') else i[0]+hashlib.sha256(i.encode()).hexdigest()[:10]) for i in ids}
        pattern=re.compile('|'.join(re.escape(i) for i in sorted(ids,key=len,reverse=True)))
        transform=lambda x:json.loads(pattern.sub(lambda m:mapping[m.group()],json.dumps(x)))
        for p,ep in FIXTURE['targets'].items():
            resources=transform(chart(p));resources.reverse()
            out=reference.reconstruct(resources,mapping[p],mapping[ep]);expected=transform(grade.EXPECTED[p])
            self.assertTrue(matches(out,expected),(p,out))


if __name__=='__main__':unittest.main()
