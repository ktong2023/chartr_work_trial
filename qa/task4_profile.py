"""Private designer aid: per-patient clinical profile of the re-anchored real data (case selection and screening)."""
import datetime as dt, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import task4_data as T

ICD = {
    'af': r'^(I48|42731|42732)',
    'chf': r'^(I50|I11\.0|I13\.[02]|428)',
    'htn': r'^(I1[0-6]|40[1-5])',
    'dm': r'^(E1[013]|250)',
    'stroke': r'^(I63|I64|G45|I74|Z86\.73|433.1|434|435|444|V1254)',
    'vascular': r'^(I21|I22|I25\.2|I70|I71|I73\.9|410|412|440|441|443\.9)',
    'bleed': r'^(I6[0-2]|K92\.[0-2]|K25\.[0246]|K26\.[0246]|K27\.[0246]|K28\.[0246]|D68\.3|430|431|432|578|531\.[0246]|532\.[0246])',
    'hiv': r'^(B20|042)',
}
ANTICOAG = r'warfarin|coumadin|apixaban|eliquis|rivaroxaban|xarelto|dabigatran|pradaxa|edoxaban'
QT_KNOWN = r'amiodarone|sotalol|dofetilide|haloperidol|methadone|citalopram|escitalopram|ondansetron|azithromycin|levofloxacin|ciprofloxacin|moxifloxacin|fluconazole|chlorpromazine|droperidol|erythromycin|clarithromycin|procainamide|quinidine|disopyramide|donepezil|pentamidine'


def codes(r):
    return [c.get('code', '').replace('.', '') if 'icd9' in c.get('system', '') else c.get('code', '') for c in r.get('code', {}).get('coding', [])]


def med_name(r, meds):
    ref = (r.get('medicationReference') or {}).get('reference', '').split('/')[-1]
    return (json.dumps(meds.get(ref, {})) + json.dumps(r.get('medicationCodeableConcept', {}))).lower()


def profile():
    data, subject = T.load_demo(); ecgs = T.ecg_records(); off = T.anchors(data, subject, ecgs)
    labels = json.loads((Path(__file__).parent / 'task4/ecg_labels.json').read_text())
    meds = {m['id']: m for m in data['MimicMedication']}
    out = {}
    for p in data['MimicPatient']:
        s = p['identifier'][0]['value']
        birth = dt.date.fromisoformat(T.shift_value(p['birthDate'], off[s]))
        death = T.shift_value(p['deceasedDateTime'], off[s])[:10] if p.get('deceasedDateTime') else None
        out[s] = {'pid': p['id'], 'sex': p['gender'], 'age': (T.EVAL.date() - birth).days // 365, 'death': death,
                  'dx': {k: False for k in ICD}, 'anticoag': [], 'qt_drugs': [], 'k': None, 'mg': None, 'ecgs': []}
    for name in ('MimicCondition', 'MimicConditionED'):
        for c in data[name]:
            s = T.owner(c, subject)
            for code in codes(c):
                for k, pat in ICD.items():
                    if re.match(pat, code): out[s]['dx'][k] = True
    for name in ('MimicMedicationRequest', 'MimicMedicationDispense', 'MimicMedicationAdministration'):
        for r in data[name]:
            s = T.owner(r, subject); nm = med_name(r, meds)
            when = T.shift_value((r.get('authoredOn') or r.get('whenHandedOver') or r.get('effectiveDateTime') or '')[:10] or '1900-01-01', off[s])
            for pat, key in ((ANTICOAG, 'anticoag'), (QT_KNOWN, 'qt_drugs')):
                m = re.search(pat, nm)
                if m: out[s][key].append((when, m.group(0)))
    for o in data['MimicObservationLabevents']:
        disp = o['code']['coding'][0].get('display', '')
        if disp in ('Potassium', 'Magnesium') and o.get('valueQuantity'):
            s = T.owner(o, subject); key = 'k' if disp == 'Potassium' else 'mg'
            when = T.shift_value(o['effectiveDateTime'], off[s])
            if not out[s][key] or when > out[s][key][0]: out[s][key] = (when, o['valueQuantity']['value'])
    for e in T.shifted_ecgs(ecgs, off):
        lab = labels.get(e['study_id'], {})
        out[e['subject_id']]['ecgs'].append((e['ecg_time'], e['study_id'], lab.get('label'), lab.get('hr')))
    for s, v in out.items():
        v['ecgs'].sort(); v['anticoag'] = sorted(set(v['anticoag'])); v['qt_drugs'] = sorted(set(v['qt_drugs']))
        d = v['dx']; age = v['age']
        v['cha2ds2vasc'] = (d['chf'] + d['htn'] + (2 if age >= 75 else 1 if age >= 65 else 0) + d['dm'] + 2 * d['stroke']
                            + d['vascular'] + (v['sex'] == 'female'))
    return out, off


if __name__ == '__main__':
    prof, _ = profile()
    Path(__file__).parent.joinpath('task4/profile.json').write_text(json.dumps(prof, indent=1, default=str) + '\n')
    alive = {s: v for s, v in prof.items() if not v['death']}
    print('alive', len(alive), 'deceased', len(prof) - len(alive))
    for s, v in sorted(alive.items(), key=lambda kv: (-kv[1]['dx']['af'], -kv[1]['cha2ds2vasc'])):
        clean = [e for e in v['ecgs'] if e[2] in ('AF', 'NORMAL', 'QTC_PROLONGED')]
        latest = clean[-1] if clean else None
        print(f"{s} {v['sex'][0]} {v['age']:3d} AFdx={int(v['dx']['af'])} score={v['cha2ds2vasc']} bleed={int(v['dx']['bleed'])} "
              f"anticoag={[a[1] for a in v['anticoag']][-2:]} qt={[q[1] for q in v['qt_drugs']][-3:]} "
              f"K={v['k'][1] if v['k'] else None} Mg={v['mg'][1] if v['mg'] else None} "
              f"ecgs={len(v['ecgs'])} AFecg={sum(e[2]=='AF' for e in v['ecgs'])} latestclean={latest[2] if latest else None}")
