import base64, collections, concurrent.futures, datetime as dt, importlib.util, json, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('t4store',ROOT/'chartr_task4/environment/service/store.py');mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
expected=json.loads((ROOT/'chartr_task4/tests/expected.json').read_text())
with tempfile.TemporaryDirectory() as tmp:
 s=mod.Store(Path(tmp)/'state.sqlite',ROOT/'assembled/sources.sqlite',ROOT/'assembled/ecg');s.initialize();s.attest('supplement')
 def search(typ):
  out=[];page=1
  while True:
   status,v=s.request('GET',f'/search?type={typ}&page={page}')
   assert status==200,(status,v)
   out+=v['resources']
   if v['complete']:return out
   page+=1
 pts=search('Patient');locs=search('Location');enc=search('Encounter');notes=search('DocumentReference')
 subject={p['id']:p['identifier'][0]['value'] for p in pts}
 live={p['id'] for p in pts if not p.get('deceasedDateTime') or p['deceasedDateTime']>'2026-09-24T12:00:00-04:00'}
 cases={i['patient'] for i in expected['items']};controls=live-cases
 clinic={r['id'] for r in locs if r.get('name')=='Cardiology Clinic'}
 dates=collections.defaultdict(list)
 for r in enc:
  if any(l['location']['reference'].split('/')[-1] in clinic for l in r.get('location',[])):
   dates[r['subject']['reference'].split('/')[-1]].append(dt.date.fromisoformat(r['period']['start'][:10]))
 flagged=set();gaps={}
 for p,ds in dates.items():
  ds=sorted(set(ds));gs=[(b-a).days for a,b in zip(ds,ds[1:])]
  if gs:
   gaps[p]=min(gs)
   if min(gs)<60:flagged.add(p)
 def classify(g):return {'cases':[subject[p] for p in sorted(g&cases)],'controls':[subject[p] for p in sorted(g&controls)]}
 lens=collections.defaultdict(list);six=set()
 for n in notes:
  p=n.get('subject',{}).get('reference','').split('/')[-1]
  if p not in live:continue
  if any(e.get('valueCode')=='clinician' for e in n.get('extension',[])) and n['type']['coding'][0]['code']=='11506-3':
   txt=base64.b64decode(n['content'][0]['attachment']['data']).decode();lens[p].append(len(txt))
   if len(txt.splitlines())==8:six.add(p)
 vals={p:max(lens[p],default=0) for p in live}
 auc=sum((vals[a]>vals[b])+.5*(vals[a]==vals[b]) for a in cases for b in controls)/(len(cases)*len(controls))
 result={'scope':'Feature extraction only through Store.request public read routes; private labels used solely to evaluate association. Not a complete solver.', 'living':len(live),'cases':len(cases),'controls':len(controls),'visit_gap_under_60_days':classify(flagged),'six_content_line_progress_notes':classify(six),'max_progress_note_length_auc':auc}
with tempfile.TemporaryDirectory() as tmp:
 s=mod.Store(Path(tmp)/'state.sqlite',ROOT/'assembled/sources.sqlite',ROOT/'assembled/ecg');s.initialize();s.attest('concurrency')
 def once(i):
  try:return {'status':s.request('GET','/ecg')[0]}
  except Exception as exc:return {'error_type':type(exc).__name__,'error':str(exc)}
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:outs=list(pool.map(once,range(40)))
 snap=s.collect()
 result['concurrent_read_probe']={'attempts':len(outs),'errors':[x for x in outs if 'error' in x],'successes':sum(x.get('status')==200 for x in outs),'audit_events':len(snap['audit']),'faults':snap['metadata']['faults']}
(ROOT/'audit-supplement.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
