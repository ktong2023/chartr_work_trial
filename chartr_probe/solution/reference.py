"""Private independent reconstruction from public clinic responses. No private labels/generator imports."""
import calendar
import copy
import datetime as dt
import json
import re
import subprocess

EVAL=dt.date(2026,9,24)
SET=re.compile(r'For entry (R[0-9a-f]+), set (date|course|months|status|replaces) to ([^ .]+)\.')
RETRACT=re.compile(r'Retract the (date|course|months|status|replaces|withdrawal) clause of amendment (R[0-9a-f]+)\.')


def extension(r,key):
    return next((v for e in r.get('extension',[]) if e['url'].endswith('/'+key) for k,v in e.items() if k.startswith('value')),None)


def identifier(ref):return ref['reference'].split('/')[-1]
def day(value):return dt.date.fromisoformat(value[:10])


def reconstruct(resources,patient,episode,shortcut=None):
    facts={};notes=[]
    for r in resources:
        kind=r['resourceType'];rid=r['id']
        if kind=='MedicationRequest':facts[rid]={'kind':'course','episode':identifier(extension(r,'episode'))}
        elif kind=='MedicationAdministration':facts[rid]={'kind':'dose','date':r['effectiveDateTime'][:10],'course':identifier(r['request']),'status':r['status']}
        elif kind=='ServiceRequest' and r.get('intent')=='plan':
            months=int(re.search(r'(\d+) calendar months',r['note'][0]['text']).group(1))
            old=extension(r,'replaces')
            facts[rid]={'kind':'plan','course':identifier(r['supportingInfo'][0]),'months':months,'status':r['status'],'replaces':identifier(old) if old else None,'documented':r['authoredOn']}
        elif kind=='Observation':facts[rid]={'kind':'result','course':identifier(r['basedOn'][0]),'date':r['effectiveDateTime'][:10],'issued':r['issued'],'status':r['status'],'test':r['code']['text']}
        elif kind=='DocumentReference' and r['date']<='2026-09-24T12:00:00Z' and extension(r,'author-role')=='treating-clinician':
            clauses=[('set',field,target,value) for target,field,value in SET.findall(r['description'])]
            clauses += [('withdraw','withdrawal',target,field) for field,target in RETRACT.findall(r['description'])]
            if clauses:notes.append((r['date'],rid,clauses))
    original=copy.deepcopy(facts)
    blocked=set();seen=set()
    if shortcut=='latest_note':notes=sorted(notes)[-1:]
    if shortcut!='structured_only':
        for timestamp,nid,clauses in sorted(notes,reverse=True):
            for action,field,target,value in clauses:
                if (nid,field) in blocked or (nid,'*') in blocked:continue
                if action=='withdraw':
                    if shortcut!='ignore_retractions':blocked.add((target,'*' if shortcut=='whole_note_retraction' else value))
                elif (target,field) not in seen:
                    if target not in facts:raise ValueError('Unknown amendment target: '+target)
                    facts[target][field]=int(value) if field=='months' else (None if value=='none' else value)
                    seen.add((target,field))
    plans=[(i,v) for i,v in facts.items() if v['kind']=='plan' and v['status']=='active' and facts[v['course']]['episode']==episode]
    replaced={p['replaces'] for _,p in plans}
    plans=[(i,p) for i,p in plans if i not in replaced]
    if shortcut=='latest_plan' and plans:plans=[max(plans,key=lambda ip:ip[1]['documented'])]
    out={'patient':patient,'episode':episode,'status':'no_requirement','plan':None,'course':None,'doses':[],
         'completion_date':None,'due_date':None,'result':None,'explanation':'Reconstructed effective source fields and applied the clinic protocol.'}
    if len(plans)!=1:
        if plans:out['status']='unclear'
        return out
    plan,p=plans[0];out.update(plan=plan,course=p['course'],status='not_due')
    doses=sorted((v['date'],i) for i,v in facts.items() if v['kind']=='dose' and v['status']=='completed' and v['course']==p['course'] and day(v['date'])<=EVAL)
    if shortcut=='stale_sequence':
        # Apply corrections to output dates but keep sequence membership selected from the original ledger.
        doses=sorted((v['date'],i) for i,v in original.items() if v['kind']=='dose' and v['status']=='completed' and v['course']==p['course'] and day(v['date'])<=EVAL)
    selected=[];previous=None
    for date,rid in doses:
        if previous is not None and (day(date)-day(previous)).days>14 and shortcut!='first_three':selected=[]
        selected.append(rid);previous=date
        if len(selected)==3:break
    out['doses']=selected
    if len(selected)<3:return out
    anchor=day(facts[selected[-1]]['date'])
    if shortcut=='latest_dose':anchor=max(day(date) for date,_ in doses)
    out['completion_date']=anchor.isoformat()
    month_index=anchor.year*12+anchor.month-1+p['months'];year,month0=divmod(month_index,12)
    due=dt.date(year,month0+1,min(anchor.day,calendar.monthrange(year,month0+1)[1]))
    out['due_date']=due.isoformat()
    valid=sorted((v['date'],i) for i,v in facts.items() if v['kind']=='result' and v['test']=='RPR'
                 and (v['course']==p['course'] or shortcut=='any_episode_result')
                 and v['status'] in ('final','corrected') and anchor<day(v['date'])<=EVAL
                 and (day(v['date'])>=due-dt.timedelta(days=30) or shortcut=='any_time_result')
                 and v['issued']<='2026-09-24T12:00:00Z')
    if valid:out.update(status='completed',result=valid[0][1])
    elif due<=EVAL:out['status']='overdue'
    return out


def clinic(*args):return json.loads(subprocess.check_output(['clinic',*args],text=True))


def solve():
    for entry in clinic('patients')['patients']:
        patient=entry['patient']['id']
        result=reconstruct(clinic('records',patient)['resources'],patient,entry['target_episode'])
        clinic('determine','--json',json.dumps(result))
    return clinic('determinations')

if __name__=='__main__':print(json.dumps(solve(),indent=2))
