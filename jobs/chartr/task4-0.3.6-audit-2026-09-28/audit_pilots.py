import importlib.util,json,hashlib,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
repo=Path('/Users/kyletong/Documents/Coding Projects/work_trial_chartr-task4')
batch=Path('/Users/kyletong/Documents/Coding Projects/work_trial_chartr/jobs/chartr/task4-0.3.5-1790617318')
spec=importlib.util.spec_from_file_location('grade',ROOT/'chartr_task4/tests/grade.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
new=g.EXPECTED
old=json.loads(subprocess.check_output(['git','show','d86dabb:chartr_task4/tests/expected.json'],cwd=repo))
originalbase=json.loads(subprocess.check_output(['git','show','d86dabb:chartr_task4/tests/baseline.json'],cwd=repo))
g.BASELINE=originalbase
summary={}
for p in sorted((batch/'opus-pilot').glob('chartr_task4__*')):
 snap=json.loads((p/'artifacts/evidence/snapshot.json').read_text());att=json.loads((p/'controller/attestation.json').read_text())
 term=json.loads((p/'controller/anthropic/termination.json').read_text());man=json.loads((p/'controller/run-manifest.json').read_text())
 expectedhash={f:hashlib.sha256(subprocess.check_output(['git','show','d86dabb:chartr_task4/'+f],cwd=repo)).hexdigest() for f in man['task_files_sha256']}
 g.EXPECTED=old;raw=g.grade(snap,att)
 saved=json.loads((p/'verifier/diagnostics.json').read_text())
 g.EXPECTED=new;res=g.grade(snap,att)
 failures=[]
 for exp in new['interpretations']:
  key=exp['subject']+'|'+exp['ecg'];got=next((i for i in snap['interpretations'] if i['ecg']==exp['ecg']),{})
  for field,ok in res['ecg_interpretation']['checks'][key].items():
   if not ok:failures.append({'subject':exp['subject'],'ecg':exp['ecg'],'field':field,'got':got.get(field),'spec':exp['fields'].get(field)})
  for field,ok in res['ecg_comparison'][key].items():
   if not ok:failures.append({'subject':exp['subject'],'ecg':exp['ecg'],'field':field,'got':got.get(field),'spec':exp.get(field)})
 usage={'api_retries':0,'tool_output_truncations':0,'parallel_commands':[],'service_transport_errors':[]}
 for lineno,line in enumerate((p/'controller/anthropic/events.jsonl').open(),1):
  e=json.loads(line);event=e['event']
  if event=='api_retry':usage['api_retries']+=1
  if event=='tool_output_truncated':usage['tool_output_truncations']+=1
  if event=='tool_start' and re.search(r'ThreadPool|ProcessPool|concurrent\.futures|asyncio\.gather|xargs.*-P',e.get('command','')):
   usage['parallel_commands'].append(lineno)
  if event=='tool_result' and any(t in str(e) for t in ('RemoteDisconnected','UNIQUE constraint failed: audit.seq','Internal service error; evaluation infrastructure fault')):
   usage['service_transport_errors'].append(lineno)
 summary[p.name]={'raw':raw['reward'],'raw_diag_identical':raw==saved,'raw_differences':{k:{'computed':v,'saved':saved.get(k)} for k,v in raw.items() if v!=saved.get(k)},'rescored':res['reward'],'manifests_match_d86dabb':man['task_files_sha256']==expectedhash,'manifest_file_count':len(expectedhash),'termination':term,'faults':snap['metadata']['faults'],'missing':res['identification']['missing'],'extra':res['identification']['extra'],'failures':failures,'trace_checks':usage}
(ROOT/'audit-pilots.json').write_text(json.dumps(summary,indent=2)+'\n')
for k,v in summary.items():print(k, 'raw',v['raw'],'rescored',v['rescored'],'manifest',v['manifests_match_d86dabb'],'raw_exact',v['raw_diag_identical'],v['trace_checks'],json.dumps(v['failures']))
