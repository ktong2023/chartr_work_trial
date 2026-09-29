"""Render private authored ledgers and golden intermediate facts. No reference-solver imports."""
import base64,calendar,datetime as dt,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TASK=ROOT/'chartr_graph'
sys.path[:0]=[str(TASK/'environment/service'),str(ROOT/'qa')]
from fhir import extension,validate,digest,VERSION,NOW
from graph_cases import CASES
D=dt.date.fromisoformat

def rid(key):return 'R'+hashlib.sha256(('graph-v1:'+key).encode()).hexdigest()[:12]
def plus(d,n):return (D(d)+dt.timedelta(days=n)).isoformat()

def golden_due(anchor,months,intervals):
    # Independent calendar enumeration from authored effective pause intervals.
    a=D(anchor);ix=a.year*12+a.month-1+months;y,m=divmod(ix,12)
    target=dt.date(y,m+1,min(a.day,calendar.monthrange(y,m+1)[1]));remaining=(target-a).days
    day=a;paused=0
    while remaining:
        if any(D(s)<=day<D(e) for s,e in intervals):paused+=1
        else:remaining-=1
        day+=dt.timedelta(days=1)
    return day.isoformat(),paused


def build():
    sources=[];targets={};expected={}
    for ci,c in enumerate(CASES):
        ref=lambda k:rid(c['key']+'.'+k)
        pid='P'+rid(c['key'])[1:8];eps={k:'E'+ref('ep'+k)[1:] for k in 'abc'}
        targets[pid]=list(eps.values());sources.append({'resourceType':'Patient','id':pid,'name':[{'text':c['name']}]})
        for k,start in zip('abc',c['starts']):
            sources.append({'resourceType':'EpisodeOfCare','id':eps[k],'status':'active','patient':{'reference':'Patient/'+pid},'period':{'start':start}})
        def add(kind,key,day,**attrs):
            r={'resourceType':kind,'id':ref(key),'subject':{'reference':'Patient/'+pid},'extension':[extension('event-time','DateTime',day+'T08:00:00Z')],**attrs};sources.append(r);return r
        for k,start,offsets in zip('abc',c['starts'],c['days']):
            r=add('MedicationRequest',k,start,status='active',intent='order',authoredOn=start+'T08:00:00Z',medicationCodeableConcept={'text':'Benzathine penicillin G'},dosageInstruction=[{'text':'Three documented administrations; reconcile according to the review protocol.'}])
            r['extension'].append(extension('episode','Reference',{'reference':'EpisodeOfCare/'+eps[k]}))
            for i,off in enumerate(offsets,1):
                day=plus(start,off)
                add('MedicationAdministration',k+str(i),day,status='completed',effectiveDateTime=day+'T09:00:00Z',medicationCodeableConcept={'text':'Benzathine penicillin G'},request={'reference':'MedicationRequest/'+ref(k)},dosage={'text':'Recorded injection.'})
        for h,start,end,courses in c['holds']:
            r=add('Basic',h,start,code={'text':'Review-clock pause'},created=start)
            r['extension'] += [extension('pause-period','Period',{'start':start,'end':end}),extension('pause-status','Code','active')]+[extension('course','Reference',{'reference':'MedicationRequest/'+ref(k)}) for k in courses]
        # Comparison reports are designated by plans, not offered as checkpoint completion evidence.
        for key,day,value in [('base','2025-12-01',4),('marker','2025-12-10',8),('marker2','2025-12-12',8)]:
            specimen=add('Specimen',key+'spec',day,status='available',collection={'collectedDateTime':day+'T08:00:00Z'})
            add('Observation',key,day,status='final',code={'text':'RPR'},effectiveDateTime=day+'T08:00:00Z',issued=day+'T16:00:00Z',specimen={'reference':'Specimen/'+specimen['id']},valueInteger=value)
        for k,sch,marker in zip('abc',c['schedules'],c.get('marker_for',['marker','marker','marker2'])):
            routine,accelerated,separation=sch
            r=add('ServiceRequest','p'+k,c['starts']['abc'.index(k)],status='active',intent='plan',code={'text':'Serial RPR follow-up'},authoredOn=c['starts']['abc'.index(k)]+'T11:00:00Z',supportingInfo=[{'reference':'MedicationRequest/'+ref(k)}],note=[{'text':f'Use the accelerated schedule only when comparison report {ref(marker)} has a titer at least four times baseline report {ref("base")}, with a later specimen date. Routine checkpoints: {routine[0]}, {routine[1]} calendar months. Accelerated checkpoints: {accelerated[0]}, {accelerated[1]} calendar months. Minimum specimen separation: {separation} days.'}])
            if c.get('extra_plan') and k=='a':
                for label,prev in [('pa2','pa'),('pa3','pa2')]:
                    v=json.loads(json.dumps(r));v['id']=ref(label);v['authoredOn']=plus(c['starts'][0],2 if label=='pa2' else 4)+'T11:00:00Z';v['extension'].append(extension('replaces','Reference',{'reference':'ServiceRequest/'+ref(prev)}));sources.append(v)
        for key,day,courses in c['labs']:
            r=add('Specimen',key,day,status='available',collection={'collectedDateTime':day+'T08:00:00Z'})
            r['extension'] += [extension('course','Reference',{'reference':'MedicationRequest/'+ref(k)}) for k in courses]
            issued='2026-06-08T16:00:00Z' if c['key']=='meadow' and key=='s1' else day+'T16:00:00Z'
            add('Observation',key+'obs',day,status='final',code={'text':'RPR'},effectiveDateTime=day+'T08:00:00Z',issued=issued,specimen={'reference':'Specimen/'+ref(key)},valueInteger=8)
            if key in c.get('duplicates',[]):
                add('Observation',key+'copy',day,status='final',code={'text':'RPR'},effectiveDateTime=day+'T08:00:00Z',issued=issued,specimen={'reference':'Specimen/'+ref(key)},valueInteger=8,note=[{'text':'Report copy from the same accession.'}])
        for j,(key,role,clauses) in enumerate(c['edits']):
            chunks=[]
            for i,(target,field,value) in enumerate(clauses,1):
                if target=='withdraw':body=f'Withdraw clause {value} of note {ref(field)}.'
                else:
                    if field=='course':value=ref(value)
                    if field=='courses':value=','.join(ref(k) for k in value)
                    body=(f'For entry {ref(target)}, {field} is {value}.' if (j+ci)%2 else f'Entry {ref(target)}: correct {field} to {value}.')
                chunks.append(f'[{i}] {body}')
            text=' '.join(chunks);day=plus('2026-09-02',j*2)
            r=add('DocumentReference',key,day,status='current',docStatus='final',date=day+'T10:00:00Z',description=text,author=[{'display':['Imani Shaw','Noah Patel','Mina Cho','Elias Green'][(j+ci)%4]}],content=[{'attachment':{'contentType':'text/plain','data':base64.b64encode(text.encode()).decode()}}])
            r['authenticator']=r['author'][0];r['extension'].append(extension('author-role','Code',role))
        # Variable ordinary entries and amendments that do not announce whether they matter.
        for j in range(ci%3+1):
            text=['Telephone contact details confirmed.','Prescription collection confirmed by patient.','Records received from the referring clinic.'][j]
            day=plus('2026-08-21',j*3)
            r=add('DocumentReference','routine'+str(j),day,status='current',docStatus='final',date=day+'T15:00:00Z',description=text,author=[{'display':'Mina Cho'}],content=[{'attachment':{'contentType':'text/plain','data':base64.b64encode(text.encode()).decode()}}])
            r['extension'].append(extension('author-role','Code','nurse'))
        rows={};labfacts={}
        for key,day,courses in c['labs']:
            effective={'date':day,'courses':courses,'status':'available',**c.get('effective_labs',{}).get(key,{})}
            for suffix in ['obs']+(['copy'] if key in c.get('duplicates',[]) else []):
                labfacts[ref(key+suffix)]={'specimen':ref(key),'date':effective['date'],'courses':[ref(k) for k in effective['courses']],
                   'eligible':effective['status']=='available' and day<'2026-09-24'}
        for k,g,sch in zip('abc',c['gold'],c['schedules']):
            plan,branch,doses,anchor,months,holds=g
            for idx,checkpoint in enumerate(('first','second')):
                unavailable=plan in ('unclear','no_requirement')
                due,paused=golden_due(anchor,months[idx],holds) if anchor else (None,None)
                rows[eps[k]+':'+checkpoint]={'episode':eps[k],'checkpoint':checkpoint,'plan':ref(plan) if not unavailable else None,
                    'course':ref(k) if not unavailable else None,'branch':branch,'doses':[ref(d) for d in doses],
                    'completion_date':anchor,'due_date':due,'paused_days':paused,'fixed_status':plan if unavailable else None,'separation':sch[2]}
        expected[pid]={'rows':rows,'reports':labfacts,'optimum':c['optimum']}
    sources.sort(key=lambda r:r['id'])
    for r in sources:validate(r)
    assert len(sources)==len({r['id'] for r in sources})
    return {'version':VERSION,'evaluation_time':NOW,'targets':targets,'sources':sources},expected


def main():
    fixture,expected=build()
    (TASK/'environment/service/fixture.json').write_text(json.dumps(fixture,indent=2)+'\n')
    (TASK/'tests/expected.json').write_text(json.dumps(expected,indent=2)+'\n')
    (TASK/'tests/baseline.json').write_text(json.dumps({'version':VERSION,'evaluation_time':NOW,'initial_digest':digest(fixture),'sources_digest':digest(fixture['sources'])},indent=2)+'\n')
    print('Built',len(expected),'patients;',len(fixture['sources']),'resources;',sum(len(x['rows']) for x in expected.values()),'determinations')
if __name__=='__main__':main()
