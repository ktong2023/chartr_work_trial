"""Private audit-only probe (from the v0.3.6 audit, jobs/chartr/task4-0.3.6-audit-2026-09-28), never copied to the task image; no
model calls. Checks private paths, blocked network, and 40 concurrent public reads (8 workers)."""
import json
from pathlib import Path
from qa.agents import BoundaryProbe

class AuditProbe(BoundaryProbe):
    async def run(self,instruction,environment,context):
        await super().run(instruction,environment,context)
        r=await environment.exec(command=r'''python - <<'INNER'
import concurrent.futures,json,pathlib,socket,urllib.request
out={'private_paths_present':[p for p in ['/data','/app/overlay','/app/readings.json','/app/expected.json'] if pathlib.Path(p).exists()]}
try:
 with socket.create_connection(('1.1.1.1',443),timeout=3): out['external_tcp']='connected'
except OSError as e: out['external_tcp']=type(e).__name__+': '+str(e)
try:
 with urllib.request.urlopen('https://physionet.org/files/mimic-iv-ecg-demo/0.1/RECORDS',timeout=3) as f:
  out['physionet_access']={'status':f.status,'read_bytes':len(f.read(64))}
except Exception as e:out['physionet_access']=type(e).__name__+': '+str(e)
def req(i):
 try:
  with urllib.request.urlopen('http://clinic:8000/ecg',timeout=10) as f:
   data=json.load(f);return {'status':f.status,'records':len(data['ecgs'])}
 except Exception as e:return {'error':type(e).__name__,'detail':str(e)}
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(req,range(40)))
out['concurrent_reads']={'attempts':40,'successes':sum(r.get('status')==200 for r in results),'errors':[r for r in results if 'error' in r]}
print(json.dumps(out))
INNER''')
        p=Path(self.logs_dir).parent/'controller'/'extended-audit-probe.json'
        p.write_text(json.dumps({'exit_code':r.return_code,'stdout':r.stdout,'stderr':r.stderr},indent=2))
        if r.return_code:raise RuntimeError('Audit probe execution failed')
