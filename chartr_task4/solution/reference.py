"""Private reference for Task 4. Reads only public clinic responses (via the CLI) plus readings.json: what an expert
reader extracts from each free-text note and clinic document, and an expert reading of each ECG. All clinical rules
(current medications, CHA2DS2-VASc, memo applicability, windows, most recent ECG) are computed here, independently of
the generator. Does not import the generator, the authored answers or the grader.
"""
import base64, datetime as dt, json, re, subprocess, tempfile
from pathlib import Path

READINGS = json.loads((Path(__file__).parent / 'readings.json').read_text())
EVAL = '2026-09-24T12:00:00-04:00'
EVAL_DAY = dt.date(2026, 9, 24)
AF = re.compile(r'^(I48|42731|42732)')
RISK = {'CHF': r'^(I50|I110|I13[02]|428)', 'HYPERTENSION': r'^(I1[0-6]|40[1-5])', 'DIABETES': r'^(E1[013]|250)',
        'STROKE_TIA': r'^(I63|I64|G45|I74|Z8673|4331|434|435|444|V1254)', 'VASCULAR': r'^(I21|I22|I252|I70|I71|I739|410|412|440|441|4439)'}
ANTICOAGULANTS = {'Warfarin', 'Apixaban', 'Rivaroxaban', 'Dabigatran Etexilate', 'Edoxaban'}


def clinic(*args):
    return json.loads(subprocess.check_output(['clinic', *args], text=True))


def search(rtype, patient=None, code=None):
    with tempfile.NamedTemporaryFile(suffix='.ndjson') as f:
        args = ['search', rtype, '--all', '--out', f.name] + (['--patient', patient] if patient else []) + (['--code', code] if code else [])
        clinic(*args)
        return [json.loads(l) for l in Path(f.name).read_text().splitlines()]


def text(doc):
    return base64.b64decode(doc['content'][0]['attachment']['data']).decode()


def day(value):
    return dt.date.fromisoformat(value[:10])


def load():
    patients = clinic('patients')['resources']
    meds = {m['id']: next((i['value'] for i in m['identifier'] if i['system'].endswith('medication-name')), None) for m in search('Medication')}
    locations = {l['id']: l['name'] for l in search('Location')}
    docs = {d['id']: {**READINGS['notes'][d['id']], 'date': d['date'], 'text': text(d)} for d in search('DocumentReference', patient='')}
    ecgs = clinic('ecg', 'list')['ecgs']
    return patients, meds, locations, docs, ecgs


def memo_rules(docs):
    rules = {'windows': [], 'watch': set(), 'threshold': None, 'inr': None, 'dose_roles': set()}
    for d in sorted(docs.values(), key=lambda d: d['date']):
        if 'watch_list' in d:
            rules['watch'] = set(d['watch_list']); rules['threshold'] = d['qtc_threshold']
        if 'post_start_ecg_days' in d:
            rules['windows'].append((d['effective'], d['post_start_ecg_days'], d['id'] if 'id' in d else None))
        if 'inr_days' in d:
            rules['inr'] = (d['effective'], d['inr_days'])
        if 'authority' in d:
            rules['dose_roles'] = set(d['authority']['warfarin_dose'])
    return rules


def interpret(ecg, prior, shortcut=None, documented_ok=()):
    r = READINGS['ecg'][ecg]
    out = {'ecg': ecg, 'rhythm': r['rhythm'], 'ventricular_rate': r['hr'], 'pr_ms': r['pr_ms'], 'qrs_ms': r['qrs_ms'], 'qtc_ms': r['qtc_ms'],
           'axis': r['axis'], 'conduction': [] if shortcut == 'no_conduction' else list(r['conduction']), 'prior_ecg': prior, 'changes': [],
           'explanation': 'Reference.'}
    if shortcut == 'trust_documented_qt' and ecg in documented_ok:
        out['qtc_ms'] = 440
    if prior:
        q = READINGS['ecg'][prior]
        for rhythm, name in (('AF', 'AF'), ('ATRIAL_FLUTTER', 'ATRIAL_FLUTTER'), ('PACED', 'PACED_RHYTHM')):
            if r['rhythm'] == rhythm and q['rhythm'] != rhythm:
                out['changes'].append('NEW_' + name)
            if q['rhythm'] == rhythm and r['rhythm'] != rhythm:
                out['changes'].append('RESOLVED_' + name)
        bbb = lambda x: bool(set(x['conduction']) & {'RBBB', 'LBBB'})
        if bbb(r) and not bbb(q):
            out['changes'].append('NEW_BUNDLE_BRANCH_BLOCK')
        if bbb(q) and not bbb(r):
            out['changes'].append('RESOLVED_BUNDLE_BRANCH_BLOCK')
        if r['qtc_ms'] and q['qtc_ms'] and r['rhythm'] == q['rhythm'] == 'SINUS':
            if r['qtc_ms'] - q['qtc_ms'] >= 60:
                out['changes'].append('QTC_INCREASE_60')
            if q['qtc_ms'] - r['qtc_ms'] >= 60:
                out['changes'].append('QTC_DECREASE_60')
    return out


def solve_all(shortcut=None):
    """`shortcut` names a plausible wrong algorithm (QA only; None is the reference)."""
    patients, meds, locations, docs, ecgs = load()
    for i, d in docs.items():
        d['id'] = i
    rules = memo_rules(docs)
    memo_id = lambda key, value: next(i for i, d in docs.items() if d.get(key) == value)
    inr_memo = next(i for i, d in docs.items() if 'inr_days' in d)
    items, findings = [], []   # findings: ECG interpretations
    documented_ok = {n['ecg'] for n in READINGS['notes'].values() if n.get('qt_assessment') == 'acceptable'}  # shortcut only
    by_patient_ecgs = {}
    for e in ecgs:
        by_patient_ecgs.setdefault(e['patient'], []).append(e)
    for p in patients:
        pid = p['id']
        pe = sorted(by_patient_ecgs.get(pid, []), key=lambda e: e['time'])
        if shortcut == 'earliest_ecg':
            pe = pe[::-1]
        # Interpretation of the most recent ECG (all patients), compared with the previous ECG
        for i, cur in enumerate(pe if shortcut == 'every_ecg' else pe[-1:]):
            idx = pe.index(cur)
            prev = None if shortcut == 'earliest_ecg' else pe[0] if shortcut == 'prior_earliest' and idx > 0 else pe[idx - 1] if idx > 0 else None
            findings.append(interpret(cur['ecg'], prev['ecg'] if prev and shortcut != 'no_comparison' else None, shortcut, documented_ok))
        if p.get('deceasedDateTime') and p['deceasedDateTime'] <= EVAL and shortcut != 'include_deceased':
            continue
        conds = search('Condition', patient=pid)
        orders = search('MedicationRequest', patient=pid)
        encounters = {e['id']: e for e in search('Encounter', patient=pid)}
        notes = [{**READINGS['notes'][d['id']], 'id': d['id'], 'date': d['date'], 'role': next(x['valueCode'] for x in d['extension'] if x['url'].endswith('author-role'))}
                 for d in search('DocumentReference', patient=pid) if d['date'] <= EVAL]
        name = lambda o: meds.get((o.get('medicationReference') or {}).get('reference', '').split('/')[-1]) or \
            (o.get('medicationCodeableConcept') or {}).get('coding', [{}])[0].get('code')

        def current(drug):
            rows = sorted((o for o in orders if name(o) == drug and o['authoredOn'] <= EVAL), key=lambda o: o['authoredOn'])
            if shortcut == 'any_order_current':
                return [o['id'] for o in rows if o['status'] != 'stopped']
            if not rows or rows[-1]['status'] == 'stopped':
                return []
            end = lambda o: ((o.get('dispenseRequest') or {}).get('validityPeriod') or {}).get('end')
            return [o['id'] for o in rows if o['status'] != 'stopped' and end(o) and end(o) >= EVAL]
        anticoag = {d: current(d) for d in ANTICOAGULANTS if current(d)}
        codes = [(c['id'], c['code']['coding'][0]['code']) for c in conds]
        charted = [o['id'] for o in search('Observation', patient=pid, code='220048') if re.match(r'^(AF|A Flut)', o.get('valueString') or '')]
        af_records = [cid for cid, code in codes if AF.match(code)] + \
            ([] if shortcut == 'af_codes_only' else [e['ecg'] for e in pe if READINGS['ecg'][e['ecg']]['label'] == 'AF']) + \
            ([] if shortcut in ('af_codes_only', 'no_charted_rhythm') else charted)
        # Stroke-risk factors
        birth = dt.date.fromisoformat(p['birthDate'])
        age = EVAL_DAY.year - birth.year - ((EVAL_DAY.month, EVAL_DAY.day) < (birth.month, birth.day))
        factors = {k for k, pat in RISK.items() if any(re.match(pat, code) for _, code in codes)}
        factors |= {'AGE_75_PLUS'} if age >= 75 else {'AGE_65_74'} if age >= 65 else set()
        if p['gender'] == 'female': factors.add('FEMALE')
        score = sum(2 if f in ('STROKE_TIA', 'AGE_75_PLUS') else 1 for f in factors)
        item = lambda cat, reason, **kw: items.append({'patient': pid, 'category': cat, 'reason': reason, 'explanation': 'Reference.', **kw})
        threshold = 2 if shortcut == 'uniform_threshold' else 3 if 'FEMALE' in factors else 2
        if af_records and not anticoag and score >= threshold:
            item('ANTICOAGULATION', 'UNTREATED_AF', af_evidence=af_records[:20], risk_score=score, risk_factors=sorted(factors))
        for n in notes:
            if n.get('contraindication') and n.get('held') in anticoag:
                item('ANTICOAGULATION', 'ANTICOAGULANT_WITH_CONTRAINDICATION', anticoagulant=anticoag[n['held']][-1], contraindication=n['id'])
        if len(anticoag) > 1:
            item('CONTRADICTION', 'DUAL_ANTICOAGULATION', records=[ids[-1] for ids in anticoag.values()])
        for n in notes:
            if n.get('rhythm') == 'sinus':
                same = [e['ecg'] for e in pe if (e['time'][:10] == n['date'][:10] or shortcut == 'rhythm_any_day') and READINGS['ecg'][e['ecg']]['label'] == 'AF']
                if same:
                    item('CONTRADICTION', 'RHYTHM_DOCUMENTATION_CONFLICT', records=[n['id'], same[-1]])
        watch = {d: current(d) for d in rules['watch'] if current(d)}
        if watch and pe and READINGS['ecg'][pe[-1]['ecg']]['label'] == 'QTC_PROLONGED' and not (
                shortcut == 'trust_documented_qt' and pe[-1]['ecg'] in documented_ok):
            labs = lambda code: sorted((o for o in search('Observation', patient=pid, code=code) if o['effectiveDateTime'] <= EVAL),
                                       key=lambda o: o['effectiveDateTime'])
            drug = next(iter(watch))
            r = READINGS['ecg'][pe[-1]['ecg']]
            item('QT_SAFETY', 'PROLONGED_QTC_ON_WATCH_LIST_DRUG', ecg=pe[-1]['ecg'], qtc_ms=r['qtc_ms'], heart_rate=r['hr'],
                 qt_drug=watch[drug][-1], potassium=labs('50971')[-1]['id'], magnesium=labs('50960')[-1]['id'])
        # ECG after starting a watch-list drug at a Cardiology Clinic visit
        clinic_order = lambda o: any(locations.get(l['location']['reference'].split('/')[-1]) == 'Cardiology Clinic'
                                     for l in encounters.get(o.get('encounter', {}).get('reference', '').split('/')[-1], {}).get('location', []))
        for drug in rules['watch']:
            starts = sorted((o for o in orders if name(o) == drug and (clinic_order(o) or shortcut == 'any_location') and o['authoredOn'] <= EVAL),
                            key=lambda o: o['authoredOn'])
            if not starts:
                continue
            start = starts[0]
            applicable = [w for w in sorted(rules['windows']) if w[0] <= start['authoredOn'][:10]]
            if shortcut == 'first_memo_forever':
                applicable = sorted(rules['windows'])[:1]
            elif shortcut == 'latest_memo_always':
                applicable = sorted(rules['windows'])
            if not applicable:
                continue
            effective, days, _ = applicable[-1]
            memo = next(i for i, d in docs.items() if d.get('post_start_ecg_days') == days)
            due = day(start['authoredOn']) + dt.timedelta(days=days)
            done = [e['ecg'] for e in pe if (start['authoredOn'][:19] <= e['time'].replace(' ', 'T')[:19] or shortcut == 'ecg_before_start_counts')
                    and day(e['time']) <= due]
            unreceived = [n for n in notes if n.get('unreceived_ecg') and day(start['authoredOn']) <= dt.date.fromisoformat(n['unreceived_ecg']) <= due]
            if shortcut == 'ignore_unreceived':
                unreceived = []
            status = 'completed' if done else 'cannot_determine' if unreceived else 'overdue' if due <= EVAL_DAY else 'not_due'
            item('FOLLOW_UP', 'ECG_AFTER_WATCH_LIST_START', status=status, trigger=start['id'], requirement=memo, due_date=due.isoformat(),
                 completion_record=done[0] if done else None)
        # INR after a warfarin dose change
        for n in notes:
            changed = n.get('dose_change') == 'Warfarin' or (shortcut == 'mention_is_dose_change' and 'dose_change' in n)
            if changed and n['role'] in rules['dose_roles'] and n['date'][:10] >= rules['inr'][0]:
                due = day(n['date']) + dt.timedelta(days=rules['inr'][1])
                inrs = [o for o in search('Observation', patient=pid, code='51237') if n['date'] < o['effectiveDateTime'] and day(o['effectiveDateTime']) <= due]
                status = 'completed' if inrs else 'overdue' if due <= EVAL_DAY else 'not_due'
                item('FOLLOW_UP', 'INR_AFTER_WARFARIN_DOSE_CHANGE', status=status, trigger=n['id'], requirement=inr_memo, due_date=due.isoformat(),
                     completion_record=inrs[0]['id'] if inrs else None)
    return items, findings


def solve():
    items, findings = solve_all()
    for it in items:
        clinic('item', 'add', '--json', json.dumps(it))
    for f in findings:
        clinic('interpretation', 'add', '--json', json.dumps(f))
    return clinic('items'), clinic('interpretations')


if __name__ == '__main__':
    print(json.dumps(solve(), indent=2)[:2000])
