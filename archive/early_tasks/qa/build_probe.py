"""Private renderer. Expected facts are authored in probe_cases, not computed by the solver."""
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_probe'
sys.path[:0] = [str(TASK/'environment/service'), str(ROOT/'qa')]
from fhir import extension, validate, VERSION, NOW, digest
from probe_cases import CASES


def rid(key):
    return 'R' + hashlib.sha256(('dependency-v1:' + key).encode()).hexdigest()[:12]


def build():
    sources=[];targets={};expected={}
    def date(start,offset):return (dt.date.fromisoformat(start)+dt.timedelta(days=offset)).isoformat()
    for c in CASES:
        key=c['key']; ref=lambda k:rid(key+'.'+k)
        pid='P'+hashlib.sha256(key.encode()).hexdigest()[:7]
        ep,old='E'+ref('episode')[1:],'E'+ref('previous')[1:]
        targets[pid]=ep
        sources.append({'resourceType':'Patient','id':pid,'name':[{'text':c['name']}]})
        for eid,start,status in [(ep,c['start'],'active'),(old,date(c['start'],-150),'finished')]:
            sources.append({'resourceType':'EpisodeOfCare','id':eid,'status':status,'patient':{'reference':'Patient/'+pid},'period':{'start':start}})
        def add(kind,k,day,**fields):
            r={'resourceType':kind,'id':ref(k),'subject':{'reference':'Patient/'+pid},
               'extension':[extension('episode','Reference',{'reference':'EpisodeOfCare/'+ep}),
                            extension('event-time','DateTime',day+'T10:00:00Z')],**fields}
            sources.append(r);return r
        def note(k,day,text,role='treating-clinician',label='Progress note'):
            r=add('DocumentReference',k,day,status='current',date=day+'T10:00:00Z',docStatus='final',
                  description=text,type={'text':label},author=[{'display':['Casey Nguyen','Jordan Blake','Hana Sato','Luis Ortega'][int(ref(k)[1:3],16)%4]}],
                  content=[{'attachment':{'contentType':'text/plain','data':base64.b64encode(text.encode()).decode()}}])
            r['extension'].append(extension('author-role','Code',role));r['authenticator']=r['author'][0];return r
        for course,eid,day in [('current',ep,c['start']),('old',old,date(c['start'],-140))]:
            r=add('MedicationRequest',course,day,status='active',intent='order',authoredOn=day+'T09:00:00Z',
                  medicationCodeableConcept={'text':'Benzathine penicillin G'},dosageInstruction=[{'text':'Three administrations; reconcile the administration ledger using the clinic review protocol.'}])
            r['extension'][0]=extension('episode','Reference',{'reference':'EpisodeOfCare/'+eid})
        for k,off,course in [(f'd{i}',v,'current') for i,v in enumerate(c['doses'],1)]+[(f'o{i}',v,'old') for i,v in enumerate([-140,-133,-126],1)]:
            day=date(c['start'],off)
            add('MedicationAdministration',k,day,status='completed',effectiveDateTime=day+'T10:00:00Z',
                medicationCodeableConcept={'text':'Benzathine penicillin G'},request={'reference':'MedicationRequest/'+ref(course)},
                dosage={'text':'Documented administration.'})
        for k,months,course,eid,replaces in [('p1',c.get('months',6),'current',ep,None),('oldplan',3,'old',old,None)]+([('p2',c['second'],'current',ep,'p1')] if 'second' in c else []):
            day=date(c['start'],45 if k=='p2' else (-140 if k=='oldplan' else 0))
            r=add('ServiceRequest',k,day,status='active',intent='plan',code={'text':'Repeat RPR'},authoredOn=day+'T10:00:00Z',
                  supportingInfo=[{'reference':'MedicationRequest/'+ref(course)}],note=[{'text':f'Repeat RPR {months} calendar months after course completion.'}])
            r['extension'][0]=extension('episode','Reference',{'reference':'EpisodeOfCare/'+eid})
            if replaces:r['extension'].append(extension('replaces','Reference',{'reference':'ServiceRequest/'+ref(replaces)}))
        # Current-looking events can belong to the earlier episode. Bindings are source facts.
        for k,day,course,status in c['results']:
            add('Observation',k,day,status=status,code={'text':'RPR'},effectiveDateTime=day+'T08:00:00Z',issued=day+'T16:00:00Z',
                valueString=['Reactive, 1:2','Reactive, 1:8','Reactive, 1:16'][int(ref(k)[-2:],16)%3],
                basedOn=[{'reference':'MedicationRequest/'+ref(course)}])
        # Scoped amendments name raw fields only; never give anchors, due dates, or dispositions.
        for i,(k,clauses) in enumerate(c['edits']):
            sentences=[]
            for target,field,value in clauses:
                if target=='withdraw':sentences.append(f'Retract the {value} clause of amendment {ref(field)}.')
                else:
                    if field=='date' and isinstance(value,int):value=date(c['start'],value)
                    if field in ('course','replaces') and value is not None:value=ref(value)
                    literal='none' if value is None else str(value)
                    sentences.append(f'For entry {ref(target)}, set {field} to {literal}.')
            note(k,date('2026-09-02',i*2),' '.join(sentences)+' Other fields remain unchanged.',label='Addendum')
        # Similar-looking irrelevant revisions and unauthorized proposals, not tagged as distractors.
        note('admin','2026-09-17',f'For entry {ref("p1")}, set months to 12. Other fields remain unchanged.',role='nurse',label='Addendum')
        note('contact','2026-09-19','Preferred contact time is afternoon. Address and pharmacy confirmed.',label='Progress note')
        note('oldcorr','2026-09-20',f'For entry {ref("oldplan")}, set months to 5. Other fields remain unchanged.',label='Addendum')
        status,plan,doses,anchor,due,results=c['expected']
        expected[pid]={'episode':ep,'status':status,'plan':ref(plan) if plan else None,
                       'course':ref('current') if plan else None,'doses':[ref(k) for k in doses],
                       'completion_date':anchor,'due_date':due,'results':[ref(k) for k in results]}
    sources.sort(key=lambda r:r['id'])
    assert len(sources)==len({r['id'] for r in sources})
    for r in sources:validate(r)
    fixture={'version':VERSION,'evaluation_time':NOW,'targets':targets,'sources':sources}
    return fixture,expected


def main():
    fixture,expected=build()
    (TASK/'environment/service/fixture.json').write_text(json.dumps(fixture,indent=2)+'\n')
    (TASK/'tests/expected.json').write_text(json.dumps(expected,indent=2)+'\n')
    (TASK/'tests/baseline.json').write_text(json.dumps({'version':VERSION,'evaluation_time':NOW,'initial_digest':digest(fixture),'sources_digest':digest(fixture['sources'])},indent=2)+'\n')
    print(f"Built {len(expected)} target episodes; {len(fixture['sources'])} R4 resources")
if __name__=='__main__':main()
