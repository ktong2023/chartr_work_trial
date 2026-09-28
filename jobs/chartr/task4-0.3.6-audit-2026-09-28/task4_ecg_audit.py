"""Read-only Task4 ECG key consistency audit; stdlib only; not a clinical adjudication.
Synthetic valid-envelope fixtures exercise grade.grade directly, not a controller-backed run.
Run: python task4_ecg_audit.py /tmp/chartr-task4-v036-audit.A9xR9P
"""
from pathlib import Path
import copy, importlib.util, json, sys
root=Path(sys.argv[1]).resolve()
load=lambda path:json.loads((root/path).read_text())
spec=importlib.util.spec_from_file_location('task4_grade', root/'chartr_task4/tests/grade.py')
grade=importlib.util.module_from_spec(spec);spec.loader.exec_module(grade)
ex=grade.EXPECTED; ints=load('qa/task4/ecg_interp.json'); reads=load('qa/task4/ecg_reads.json')
def pick(s):
    if 'any' in s:return None
    if 'required' in s:return s['required']
    if 'exact' in s:return s['exact']
    if 'null' in s:return None
    if 'one_of' in s:return s['one_of'][0]
    if 'subset_of' in s:return s['subset_of'][:1]
    if 'set' in s:return s['set']
    if 'range' in s:return sum(s['range'])/2
    if 'set_one_of' in s:return s['set_one_of'][0]
    if 'cover' in s:return list({g[0] for g in s['cover']})
    raise ValueError(s)
items=[{**{k:e[k] for k in ('patient','category','reason')},**{k:pick(s) for k,s in e['fields'].items()}} for e in ex['items']]
interps=[{'ecg':e['ecg'],'patient':e['patient'],**{k:pick(s) for k,s in e['fields'].items()},'prior_ecg':e['prior_ecg'],'changes':e['changes']['required']} for e in ex['interpretations']]
def evaluate(it,inter):
    att={**grade.BASELINE,'trial_id':'synthetic-audit-fixture','nonce':'synthetic-audit-fixture'}
    state={'items':it,'interpretations':inter}
    snap={**state,'metadata':{**att,'frozen':True,'faults':0},'audit':[{'seq':1,'method':'POST','status':200,'before':{'items':[],'interpretations':[]},'after':state}]}
    return grade.grade(snap,att)
report={'scope':'Synthetic valid-envelope unit fixtures invoking actual grader; not controller-backed Harbor runs or physiological diagnoses. Values are accepted by private specs; that alone is not proof of clinical accuracy.','baseline_reward':evaluate(items,interps)['reward'],'cases':[]}
for sid,cur,prev,pv,changes in [('104821039',510,'107149156',480,[]),('102172660',450,'105362569',500,[]),('103036945',450,'102616671',380,['QTC_INCREASE_60'])]:
    it=copy.deepcopy(items);inter=copy.deepcopy(interps)
    next(i for i in inter if i['ecg']==sid).update(qtc_ms=cur,changes=changes)
    for i in it:
        if i.get('ecg')==sid:i['qtc_ms']=cur
    res=evaluate(it,inter)
    report['cases'].append({'kind':'comparison_inconsistency','current_ecg':sid,'current_qtc':cur,'prior_ecg':prev,'prior_qtc':pv,'current_value_accepted':grade.field_ok(ints['ecg'][sid]['qtc_ms'],cur),'prior_value_accepted':grade.field_ok(ints['ecg'][prev]['qtc_ms'],pv),'delta_ms':cur-pv,'submitted_changes':changes,'reward':res['reward'],'failed_comparisons':{k:v for k,v in res['ecg_comparison'].items() if not all(v.values())},'components':res['components']})
for sid in ['108018814','106885519','101515306']:
    it=[copy.deepcopy(i) for i in items if not(i.get('ecg')==sid and i['reason']=='PROLONGED_QTC_ON_WATCH_LIST_DRUG')]
    inter=copy.deepcopy(interps);next(i for i in inter if i['ecg']==sid)['qtc_ms']=495
    res=evaluate(it,inter)
    report['cases'].append({'kind':'threshold_inconsistency','ecg':sid,'qtc_ms':495,'reward':res['reward'],'components':res['components'],'missing':res['identification']['missing']})
report['reader_value_rejections']={}
for name in ['M','N','G']:
    failures=[]
    for e in ex['interpretations']:
        sid=e['ecg'];r=reads[sid][name] or {}
        for f,k in [('ventricular_rate','hr'),('qrs_ms','qrs'),('qtc_ms','qt')]:
            v=r.get(k)
            if v is None:continue
            if f=='qtc_ms':v=v/(60/r['hr'])**0.5
            if not grade.field_ok(e['fields'][f],v):failures.append({'subject':e['subject'],'ecg':sid,'field':f,'value':v,'spec':e['fields'][f]})
    report['reader_value_rejections'][name]=failures
report['all_serial_tolerance_mismatches']=[]
for e in ex['interpretations']:
    cur=e['fields']['qtc_ms'].get('range');prior=e['prior_ecg'];prev=ints['ecg'][prior]['qtc_ms'].get('range') if prior else None
    if not cur or not prev:continue
    mn=cur[0]-prev[1];mx=cur[1]-prev[0];allowed=e['changes']['allowed']+e['changes']['required'];mismatch=[]
    if mx>=60 and 'QTC_INCREASE_60' not in allowed:mismatch.append('increase forbidden despite allowable delta>=60')
    if mn<=-60 and 'QTC_DECREASE_60' not in allowed:mismatch.append('decrease forbidden despite allowable delta<=-60')
    if mn<60 and 'QTC_INCREASE_60' in e['changes']['required']:mismatch.append('increase required despite allowable delta<60')
    if mx>-60 and 'QTC_DECREASE_60' in e['changes']['required']:mismatch.append('decrease required despite allowable delta>-60')
    if mismatch:report['all_serial_tolerance_mismatches'].append({'subject':e['subject'],'ecg':e['ecg'],'prior':prior,'current_range':cur,'prior_range':prev,'delta_range':[mn,mx],'change_spec':e['changes'],'mismatch':mismatch})
Path('/tmp/task4-ecg-grader-counterexamples.json').write_text(json.dumps(report,indent=2)+'\n')
print('baseline_reward',report['baseline_reward'],'fixtures',len(report['cases']),'serial_mismatches',len(report['all_serial_tolerance_mismatches']))
print('reader rejection counts',{k:len(v) for k,v in report['reader_value_rejections'].items()})
