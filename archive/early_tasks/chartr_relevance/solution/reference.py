"""Private reference: reconstruct public records, then optimize a joint assignment.
Free-text notes and plan text are read through readings.json: the structured statements an expert
reader extracts from each note (which record, which fact, which value), keyed by public record ID.
Everything after reading (retractions, authority, clocks, schedules, allocation) is computed here.
Does not import the generator, authored cases, golden fields, or private grader.
"""
import calendar,datetime as dt,functools,itertools,json,re,subprocess
from pathlib import Path
READINGS=json.loads((Path(__file__).parent/'readings.json').read_text())
D=dt.date.fromisoformat
EVAL=D('2026-09-24');NOW='2026-09-24T12:00:00Z'

def ext(r,name):
    return [v for e in r.get('extension',[]) if e['url'].endswith('/'+name) for k,v in e.items() if k.startswith('value')]
def one(r,name):return ext(r,name)[0]
def ident(ref):return ref['reference'].split('/')[-1]
def day(value):return D(value[:10])

def reconstruct(resources,shortcut=None):
    facts={};notes={}
    for r in resources:
        rid=r['id'];kind=r['resourceType'];v={'kind':kind}
        if kind=='MedicationRequest':v.update(episode=ident(one(r,'episode')))
        elif kind=='MedicationAdministration':
            if 'effectivePeriod' in r:v.update(course=ident(r['request']),date=None,range=(r['effectivePeriod']['start'][:10],r['effectivePeriod']['end'][:10]),status=r['status'])
            else:v.update(course=ident(r['request']),date=r['effectiveDateTime'][:10],status=r['status'])
        elif kind=='Basic':
            period=one(r,'pause-period');v.update(start=period['start'],end=period['end'],courses=[ident(x) for x in ext(r,'course')],status=one(r,'pause-status'))
        elif kind=='Specimen':v.update(date=r['collection']['collectedDateTime'][:10],courses=[ident(x) for x in ext(r,'course')],status=r['status'])
        elif kind=='Observation':v.update(specimen=ident(r['specimen']),status=r['status'],issued=r['issued'],titer=r['valueInteger'],test=r['code']['text'])
        elif kind=='ServiceRequest':
            v.update(courses=[ident(x) for x in r['supportingInfo']],status=r['status'],replaces=ident(one(r,'replaces')) if ext(r,'replaces') else None,**READINGS['plan:'+rid])
        elif kind=='DocumentReference':
            if r.get('docStatus')!='final' or 'authenticator' not in r or r['date']>NOW:continue
            reading=READINGS[rid]
            if reading.get('unreceived'):facts[rid]={'kind':'Unreceived','date':reading['unreceived']}
            if reading.get('hold') and one(r,'author-role')=='clinician':
                facts[rid]={'kind':'Basic','status':'active',**reading['hold']}
            notes[rid]={'role':one(r,'author-role'),'date':r['date'],'clauses':[tuple(x) for x in reading['clauses']]}
            continue
        else:continue
        facts[rid]=v
    blocked=set();seen=set()
    if shortcut!='original_fields':
        for nid,note in sorted(notes.items(),key=lambda pair:(pair[1]['date'],pair[0]),reverse=True):
            for num,action,target,field,value in reversed(note['clauses']):
                if (nid,num) in blocked or (nid,'*') in blocked:continue
                if action=='withdraw':
                    if shortcut=='ignore_withdrawals':continue
                    if target in notes and notes[target]['role']==note['role']:
                        blocked.add((target,'*' if shortcut=='whole_note_withdrawal' else field))
                    continue
                fact=facts[target]
                authority='laboratory' if fact['kind'] in ('Specimen','Observation') else 'clinician'
                if shortcut!='all_authors' and note['role']!=authority:continue
                if (target,field) in seen:continue
                if field=='courses':value=value.split(',')
                if field in ('routine','accelerated'):value=list(map(int,value.split(',')))
                if field=='titer':value=int(value)
                fact[field]=value;seen.add((target,field))
    return facts


def merged_pauses(facts,course,shortcut=None):
    spans=sorted((day(v['start']),day(v['end'])) for v in facts.values() if v['kind']=='Basic' and v['status']=='active' and course in v['courses'])
    if shortcut=='ignore_pauses':return []
    if shortcut=='double_count_pauses':return spans
    merged=[]
    for start,end in spans:
        if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
        else:merged.append((start,end))
    return merged


def paused(spans,start,end):return sum(max(0,(min(b,end)-max(a,start)).days) for a,b in spans)
def due_date(anchor,months,spans,shortcut=None):
    n=anchor.year*12+anchor.month-1+months;y,m=divmod(n,12)
    base=dt.date(y,m+1,min(anchor.day,calendar.monthrange(y,m+1)[1]));due=base
    for _ in range(1000):
        p=paused(spans,anchor,due);updated=base+dt.timedelta(days=p)
        if shortcut=='one_pass_clock':return updated,p
        if updated==due:return due,p
        due=updated
    raise ValueError('Unbounded pause clock')


def report_valid(report,facts):
    specimen=facts[report['specimen']]
    return report['status'] in ('final','corrected') and report['test']=='RPR' and report['issued']<=NOW and specimen['status']=='available' and day(specimen['date'])<=EVAL


def states_and_reports(resources,patient,episodes,shortcut=None):
    facts=reconstruct(resources,shortcut);rows=[]
    reports={rid:{'specimen':v['specimen'],'date':facts[v['specimen']]['date'],'courses':facts[v['specimen']]['courses'],'eligible':report_valid(v,facts)} for rid,v in facts.items() if v['kind']=='Observation'}
    for ep in episodes:
        plans=[(rid,v) for rid,v in facts.items() if v['kind']=='ServiceRequest' and v['status']=='active' and any(facts[c]['episode']==ep for c in v['courses'])]
        replaced={v['replaces'] for _,v in plans};plans=[(r,v) for r,v in plans if r not in replaced]
        base={'patient':patient,'episode':ep,'plan':None,'course':None,'branch':None,'doses':[],'completion_date':None,'due_date':None,'paused_days':None,'result':None,'status':'no_requirement','explanation':'Reconstructed effective records and reconciled the joint checkpoint allocation.'}
        if len(plans)!=1:
            if plans:base['status']='unclear'
            rows.extend({**base,'checkpoint':cp,'separation':0} for cp in ('first','second'));continue
        plan,p=plans[0];course=p['courses'][0]
        baseline,comparison=facts[p['baseline']],facts[p['comparison']]
        valid=all(report_valid(v,facts) and v['titer']>0 for v in (baseline,comparison))
        if not valid:
            base['status']='unclear';rows.extend({**base,'checkpoint':cp,'separation':p['separation']} for cp in ('first','second'));continue
        # Every titer the comparison specimen's valid reports allow; the branch must agree across all of them.
        values={v['titer'] for v in facts.values() if v['kind']=='Observation' and v['specimen']==comparison['specimen'] and report_valid(v,facts) and v['titer']>0}
        if shortcut=='best_guess':values={comparison['titer']}
        later=facts[comparison['specimen']]['date']>facts[baseline['specimen']]['date']
        branches={'accelerated' if later and t>=4*baseline['titer'] else 'routine' for t in values}
        if len(branches)>1 or (shortcut=='abstain_any_gap' and len(values)>1):
            base['status']='unclear';rows.extend({**base,'checkpoint':cp,'separation':p['separation']} for cp in ('first','second'));continue
        branch=branches.pop()
        if shortcut=='always_routine':branch='routine'
        spans=merged_pauses(facts,course,shortcut)
        given=[(rid,v) for rid,v in facts.items() if v['kind']=='MedicationAdministration' and v['course']==course and v['status']=='completed']
        ranged=[(rid,v['range']) for rid,v in given if v['date'] is None]
        if shortcut=='abstain_any_gap' and ranged:
            base['status']='unclear';rows.extend({**base,'checkpoint':cp,'separation':p['separation']} for cp in ('first','second'));continue
        options=[[lo] if shortcut=='best_guess' else [(day(lo)+dt.timedelta(days=n)).isoformat() for n in range((day(hi)-day(lo)).days+1)] for _,(lo,hi) in ranged]
        outcomes=set()
        for world in itertools.product(*options):
            dated={rid:d for (rid,_),d in zip(ranged,world)}
            administrations=sorted((day(v['date'] or dated[rid]),rid) for rid,v in given if day(v['date'] or dated[rid])<=EVAL)
            seq=[];previous=None;anchor=None
            for date,rid in administrations:
                gap=(date-previous).days-paused(spans,previous,date) if previous else 0
                if previous and gap>14:seq=[]
                seq.append(rid);previous=date
                if len(seq)==3:anchor=date;break
            outcomes.add((tuple(sorted(seq)),anchor))
        if len(outcomes)>1:
            base['status']='unclear';rows.extend({**base,'checkpoint':cp,'separation':p['separation']} for cp in ('first','second'));continue
        seq,anchor=outcomes.pop();seq=list(seq)
        base.update(plan=plan,course=course,branch=branch,doses=seq,completion_date=anchor.isoformat() if anchor else None,status='not_due',paused_days=0)
        for i,cp in enumerate(('first','second')):
            r={**base,'checkpoint':cp,'separation':p['separation']}
            if anchor:
                due,pause=due_date(anchor,p[branch][i],spans,shortcut);r.update(due_date=due.isoformat(),paused_days=pause)
            rows.append(r)
    unreceived=sorted(v['date'] for v in facts.values() if v['kind']=='Unreceived')
    return rows,reports,unreceived


def candidates(row,reports):
    if row['due_date'] is None:return []
    due=day(row['due_date']);anchor=day(row['completion_date'])
    return sorted((rid for rid,v in reports.items() if v['eligible'] and row['course'] in v['courses'] and anchor<day(v['date']) and due-dt.timedelta(days=21)<=day(v['date'])<=due+dt.timedelta(days=35)),key=lambda rid:(reports[rid]['date'],rid))


def allocation(rows,reports,shortcut=None):
    ordered=sorted(range(len(rows)),key=lambda i:(rows[i]['checkpoint']=='second',rows[i]['episode']))
    choices={i:candidates(rows[i],reports) for i in ordered}
    # Equivalent copies of one specimen are interchangeable in this solver, but grading accepts either.
    for i in choices:
        seen=set();choices[i]=[r for r in choices[i] if not (reports[r]['specimen'] in seen or seen.add(reports[r]['specimen']))]
    episodes=sorted({r['episode'] for r in rows});ei={e:i for i,e in enumerate(episodes)}
    @functools.lru_cache(None)
    def search(pos,used,firsts):
        if pos==len(ordered):return 0,()
        i=ordered[pos];row=rows[i];idx=ei[row['episode']];best=(-1,())
        for rid in choices[i]+[None]:
            if rid:
                rep=reports[rid]
                if shortcut!='reuse_specimens' and rep['specimen'] in used:continue
                if row['checkpoint']=='second' and shortcut!='ignore_prerequisite':
                    if firsts[idx] is None or (day(rep['date'])-day(firsts[idx])).days<row['separation']:continue
            fs=list(firsts)
            if row['checkpoint']=='first':fs[idx]=reports[rid]['date'] if rid else None
            score,tail=search(pos+1,tuple(sorted(set(used)|({reports[rid]['specimen']} if rid else set()))),tuple(fs))
            candidate=(score+bool(rid),(rid,)+tail)
            if candidate[0]>best[0]:best=candidate
            if shortcut=='greedy' and (rid or best[0]>=0):break
        return best
    score,chosen=search(0,(),tuple(None for _ in episodes))
    return score,{i:r for i,r in zip(ordered,chosen)}


def solve_patient(resources,patient,episodes,shortcut=None):
    rows,reports,unreceived=states_and_reports(resources,patient,episodes,shortcut)
    _,chosen=allocation(rows,reports,shortcut)
    firsts={r['episode']:chosen[i] for i,r in enumerate(rows) if r['checkpoint']=='first'}
    def could_complete(row,d):
        due=day(row['due_date']);d=day(d)
        if not (day(row['completion_date'])<d and due-dt.timedelta(days=21)<=d<=due+dt.timedelta(days=35)):return False
        if row['checkpoint']=='first':return True
        first=firsts[row['episode']]
        return bool(first) and (d-day(reports[first]['date'])).days>=row['separation']
    for i,row in enumerate(rows):
        rid=chosen[i];row['result']=rid
        if rid:row['status']='completed'
        elif row['due_date']:
            if shortcut=='abstain_any_gap' and unreceived:row['status']='cannot_determine'
            elif shortcut!='best_guess' and any(could_complete(row,d) for d in unreceived):row['status']='cannot_determine'
            elif row['checkpoint']=='second' and not firsts[row['episode']]:row['status']='blocked'
            else:row['status']='overdue' if day(row['due_date'])<=EVAL else 'not_due'
        row.pop('separation')
    return rows

def clinic(*args):return json.loads(subprocess.check_output(['clinic',*args],text=True))
def solve():
    for entry in clinic('patients')['patients']:
        p=entry['patient']['id'];chart=clinic('records',p)['resources']
        for row in solve_patient(chart,p,entry['target_episodes']):clinic('determine','--json',json.dumps(row))
    return clinic('determinations')
if __name__=='__main__':print(json.dumps(solve(),indent=2))
