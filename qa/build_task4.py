"""Build Task 4 (chartr_task4): overlay on the pinned MIMIC-IV demo, private answers and reference readings.

Private. Everything a synthetic record needs is cloned from a real record of the same kind (same profile, field
presence, code systems, identifier systems and timestamp precision); IDs are MIMIC's own UUIDv5 scheme applied
to new identifier values. All living patients get the same kind of outpatient layer (clinic visits, a current
medication list, outpatient labs, progress and telephone notes), so the case patients are not separable by what
was added. Answers below are authored by hand; the reference solution recomputes them independently.

Run with the pinned host venv:  .venv/bin/python qa/build_task4.py   (the ECG catalog must be built first)
"""
import base64, copy, gzip, hashlib, json, random, re, sys, uuid
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TASK = ROOT / 'chartr_task4'
sys.path[:0] = [str(HERE), str(TASK / 'environment/service')]
import task4_data as T  # noqa: E402

EVAL = dt.datetime(2026, 9, 24, 12, 0, tzinfo=T.TZ)
NS = uuid.uuid5(uuid.NAMESPACE_OID, 'MIMIC-IV')
CLINIC = 'https://chartr.example/fhir/StructureDefinition/'
AF_CODE = re.compile(r'^(I48|42731|42732)')
RISK = {'CHF': r'^(I50|I11\.?0|I13\.?[02]|428)', 'HYPERTENSION': r'^(I1[0-6]|40[1-5])', 'DIABETES': r'^(E1[013]|250)',
        'STROKE_TIA': r'^(I63|I64|G45|I74|Z86\.?73|4331|434|435|444|V1254)', 'VASCULAR': r'^(I21|I22|I25\.?2|I70|I71|I73\.?9|410|412|440|441|4439)'}
VASCULAR_BROAD = r'^(I251|4140|Z951|Z955|V4581|V4582)'
WATCH = ('Citalopram', 'Escitalopram Oxalate', 'Haloperidol', 'Methadone', 'Amiodarone', 'Sotalol', 'Dofetilide')
ANTICOAGULANTS = ('Warfarin', 'Apixaban', 'Rivaroxaban', 'Dabigatran Etexilate', 'Edoxaban')
DOSES = {  # outpatient sig: (strength text, dose value, unit, frequency code)
    'Warfarin': ('5 mg Tab', 5, 'mg', 'DAILY'), 'Apixaban': ('5 mg Tab', 5, 'mg', 'BID'), 'Rivaroxaban': ('20 mg Tab', 20, 'mg', 'DAILY'),
    'Amiodarone': ('200 mg Tab', 200, 'mg', 'DAILY'), 'Citalopram': ('40 mg Tab', 40, 'mg', 'DAILY'),
    'Escitalopram Oxalate': ('10 mg Tab', 10, 'mg', 'DAILY'), 'Haloperidol': ('2 mg Tab', 2, 'mg', 'BID'),
    'Metoprolol Tartrate': ('25 mg Tab', 25, 'mg', 'BID'), 'Metoprolol Succinate XL': ('50 mg Tab', 50, 'mg', 'DAILY'),
    'Atorvastatin': ('40 mg Tab', 40, 'mg', 'DAILY'), 'Simvastatin': ('20 mg Tab', 20, 'mg', 'DAILY'), 'Pravastatin': ('40 mg Tab', 40, 'mg', 'DAILY'),
    'Lisinopril': ('10 mg Tab', 10, 'mg', 'DAILY'), 'Losartan Potassium': ('50 mg Tab', 50, 'mg', 'DAILY'), 'Amlodipine': ('5 mg Tab', 5, 'mg', 'DAILY'),
    'Furosemide': ('40 mg Tab', 40, 'mg', 'DAILY'), 'Aspirin': ('81 mg Tab', 81, 'mg', 'DAILY'), 'Carvedilol': ('6.25 mg Tab', 6.25, 'mg', 'BID'),
    'Levothyroxine Sodium': ('50 mcg Tab', 50, 'mcg', 'DAILY'), 'Pantoprazole': ('40 mg Tab', 40, 'mg', 'DAILY'), 'Omeprazole': ('20 mg Cap', 20, 'mg', 'DAILY'),
    'Sertraline': ('50 mg Tab', 50, 'mg', 'DAILY'), 'Gabapentin': ('300 mg Cap', 300, 'mg', 'TID'), 'Tamsulosin': ('0.4 mg Cap', 0.4, 'mg', 'DAILY'),
    'Allopurinol': ('100 mg Tab', 100, 'mg', 'DAILY'), 'Hydrochlorothiazide': ('25 mg Tab', 25, 'mg', 'DAILY'), 'Spironolactone': ('25 mg Tab', 25, 'mg', 'DAILY'),
    'Clopidogrel': ('75 mg Tab', 75, 'mg', 'DAILY'), 'Famotidine': ('20 mg Tab', 20, 'mg', 'BID'), 'MetFORMIN (Glucophage)': ('500 mg Tab', 500, 'mg', 'BID'),
}
CLINICIANS = ['Dr. Aisha Rahman', 'Dr. Paul Kessler', 'Dr. Mei Tanaka', 'Dr. Daniel Ortiz']
PHARMACISTS = ['L. Nguyen, PharmD', 'R. Patel, PharmD']
NURSES = ['K. Brooks, RN', 'S. Levine, RN']


def mid(kind, value):
    return str(uuid.uuid5(uuid.uuid5(NS, kind), str(value)))


def iso(d):
    return d.isoformat(timespec='seconds')


def at(day, hh, mm):
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=T.TZ)


class Builder:
    def __init__(self):
        self.data, self.subject = T.load_demo()
        self.pid = {v: k for k, v in self.subject.items()}          # MIMIC subject -> FHIR id
        self.ecgs = T.ecg_records()
        self.offsets = T.anchors(self.data, self.subject, self.ecgs)  # by subject
        self.catalog = json.loads((HERE / 'task4/ecg_catalog.json').read_text())
        self.truth = json.loads((HERE / 'task4/ecg_truth.json').read_text())
        self.rng = random.Random(4)
        self.added, self.removed, self.readings, self.notes_by_patient = [], [], {}, {}
        self.meds = {i['value']: m for m in self.data['MimicMedication'] for i in m['identifier'] if i['system'].endswith('mimic-medication-name')}
        self.org = self.data['MimicOrganization'][0]['id']
        # Outpatient visits get their own location; MIMIC's 'Cardiology' is an inpatient ward.
        clinic = copy.deepcopy(next(l for l in self.data['MimicLocation'] if l.get('name') == 'Cardiology'))
        clinic['id'] = mid('Location', 'Cardiology Clinic'); clinic['name'] = 'Cardiology Clinic'
        clinic['physicalType'] = {'coding': [{'code': 'area', 'system': clinic['physicalType']['coding'][0]['system'], 'display': 'Area'}]}
        self.cardiology = clinic['id']
        self.templates()
        self.counters = {'enc': 30_100_000, 'phid': 1 + max(int(i['value']) for r in self.data['MimicMedicationRequest'] for i in r['identifier']
                                                            if i['system'].endswith('medication-request-phid')),
                         'lab': 480_000, 'spec': 0}
        self.used_spec = {s['identifier'][0]['value'] for s in self.data['MimicSpecimenLab']}
        self.added.append(clinic)

    # ------------------------------------------------------------------ real-record templates
    def templates(self):
        enc = [e for e in self.data['MimicEncounter'] if e['class']['code'] == 'AMB']
        self.t_enc = copy.deepcopy(enc[0])
        mr = [r for r in self.data['MimicMedicationRequest'] if 'dispenseRequest' in r and 'dosageInstruction' in r and 'medicationReference' in r
              and r['dosageInstruction'][0].get('route', {}).get('coding', [{}])[0].get('code') == 'PO'
              and r['dosageInstruction'][0].get('doseAndRate')]
        self.t_mr = copy.deepcopy(mr[0])
        labs = self.data['MimicObservationLabevents']
        self.t_lab = {code: copy.deepcopy(next(o for o in labs if o['code']['coding'][0]['code'] == code and 'encounter' not in o and 'extension' in o))
                      for code in ('50971', '50960', '51237')}
        self.t_spec = copy.deepcopy(next(s for s in self.data['MimicSpecimenLab'] if s['type']['coding'][0]['code'] == 'Blood'))
        freqs = {r['dosageInstruction'][0]['timing']['code']['coding'][0]['code'] for r in mr[:3000] if r['dosageInstruction'][0].get('timing')}
        assert {'DAILY', 'BID'} <= freqs, freqs

    # ------------------------------------------------------------------ record factories (cloned shapes)
    def encounter(self, s, start, minutes=40):
        self.counters['enc'] += self.rng.randint(3, 997)
        e = copy.deepcopy(self.t_enc)
        e['id'] = mid('Encounter', self.counters['enc']); e['identifier'][0]['value'] = str(self.counters['enc'])
        e['subject'] = {'reference': 'Patient/' + self.pid[s]}
        end = start + dt.timedelta(minutes=minutes)
        e['period'] = {'end': iso(end), 'start': iso(start)}
        e['location'] = [{'period': {'end': iso(end), 'start': iso(start)}, 'location': {'reference': 'Location/' + self.cardiology}}]
        e['serviceType'] = {'coding': [{'code': 'CMED', 'system': 'http://mimic.mit.edu/fhir/mimic/CodeSystem/mimic-services'}]}
        e['hospitalization'] = {'admitSource': {'coding': [{'code': 'PHYSICIAN REFERRAL', 'system': e['hospitalization']['admitSource']['coding'][0]['system']}]},
                                'dischargeDisposition': {'coding': [{'code': 'HOME', 'system': e['hospitalization']['dischargeDisposition']['coding'][0]['system']}]}}
        e['priority'] = {'coding': [{'code': 'R', 'system': 'http://terminology.hl7.org/CodeSystem/v3-ActPriority', 'display': 'routine'}]}
        e['serviceProvider'] = {'reference': 'Organization/' + self.org}
        self.added.append(e)
        return e['id']

    def order(self, s, drug, when, enc, status='completed', days=180, sig=None):
        self.counters['phid'] += self.rng.randint(1, 40)
        r = copy.deepcopy(self.t_mr)
        r['id'] = mid('MedicationRequest', self.counters['phid']); r['identifier'][0]['value'] = str(self.counters['phid'])
        r['subject'] = {'reference': 'Patient/' + self.pid[s]}; r['encounter'] = {'reference': 'Encounter/' + enc}
        r['authoredOn'] = iso(when); r['status'] = status
        r['medicationReference'] = {'reference': 'Medication/' + self.meds[drug]['id']}
        text, value, unit, freq = sig or DOSES[drug]
        di = r['dosageInstruction'][0]
        di['text'] = text; di['timing']['code']['coding'][0]['code'] = freq
        di['doseAndRate'][0]['doseQuantity'].update({'code': unit, 'unit': unit, 'value': value})
        r['dispenseRequest'] = {'validityPeriod': {'end': iso(when + dt.timedelta(days=days)), 'start': iso(when)}}
        self.added.append(r)
        return r['id']

    def lab(self, s, code, value, when, enc=None):
        spec = copy.deepcopy(self.t_spec)
        while True:
            sv = str(self.rng.randint(10_000_000, 99_999_999))
            if sv not in self.used_spec: self.used_spec.add(sv); break
        spec['id'] = mid('SpecimenLab', sv); spec['identifier'][0]['value'] = sv
        spec['subject'] = {'reference': 'Patient/' + self.pid[s]}; spec['collection'] = {'collectedDateTime': iso(when)}
        self.counters['lab'] += self.rng.randint(1, 60)
        o = copy.deepcopy(self.t_lab[code])
        o['id'] = mid('ObservationLabevents', self.counters['lab']); o['identifier'][0]['value'] = str(self.counters['lab'])
        o['subject'] = {'reference': 'Patient/' + self.pid[s]}; o['specimen'] = {'reference': 'Specimen/' + spec['id']}
        o['effectiveDateTime'] = iso(when); o['issued'] = iso(when + dt.timedelta(minutes=self.rng.randint(55, 190)))
        o['valueQuantity']['value'] = value
        if enc:
            o['encounter'] = {'reference': 'Encounter/' + enc}
        self.added += [spec, o]
        return o['id']

    def note(self, s, key, when, kind, role, text, enc=None, reading=None):
        author = {'clinician': CLINICIANS, 'pharmacist': PHARMACISTS, 'nurse': NURSES}[role][int(hashlib.sha256((s + key).encode()).hexdigest(), 16) % 2]
        loinc = {'progress': ('11506-3', 'Progress note'), 'telephone': ('34748-2', 'Telephone encounter Note'),
                 'pharmacy': ('11506-3', 'Progress note'), 'outside': ('34133-9', 'Summary of episode note')}[kind]
        body = text + f'\n\nSigned: {author}'
        r = {'resourceType': 'DocumentReference', 'id': mid('DocumentReference', f'{s}:{key}'),
             'meta': {'profile': [CLINIC + 'clinic-note']}, 'status': 'current', 'docStatus': 'final',
             'type': {'coding': [{'system': 'http://loinc.org', 'code': loinc[0], 'display': loinc[1]}]},
             'subject': {'reference': 'Patient/' + self.pid[s]}, 'date': iso(when),
             'author': [{'display': author}], 'authenticator': {'display': author},
             'extension': [{'url': CLINIC + 'author-role', 'valueCode': role}],
             'content': [{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(body.encode()).decode()}}]}
        if enc:
            r['context'] = {'encounter': [{'reference': 'Encounter/' + enc}]}
        self.added.append(r)
        self.readings[r['id']] = reading or {}
        self.notes_by_patient.setdefault(s, []).append((when, r['id'], text))
        return r['id']

    def memo(self, key, day, title, text, reading):
        body = f'{title}\n{text}\n\nClinic Operations Committee'
        r = {'resourceType': 'DocumentReference', 'id': mid('DocumentReference', 'memo:' + key),
             'meta': {'profile': [CLINIC + 'clinic-note']}, 'status': 'current', 'docStatus': 'final',
             'type': {'coding': [{'system': 'http://loinc.org', 'code': '68608-9', 'display': 'Summary note'}]},
             'date': iso(at(day, 9, 0)), 'author': [{'display': 'Clinic Operations Committee'}],
             'extension': [{'url': CLINIC + 'clinic-document', 'valueBoolean': True}],
             'content': [{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(body.encode()).decode()}}]}
        self.added.append(r)
        self.readings[r['id']] = reading
        return r['id']

    # ------------------------------------------------------------------ real-data context per patient
    def context(self):
        info = {}
        for p in self.data['MimicPatient']:
            s = p['identifier'][0]['value']; off = self.offsets[s]
            birth = dt.date.fromisoformat(T.shift_value(p['birthDate'], off))
            death = T.shift_value(p['deceasedDateTime'], off)[:10] if p.get('deceasedDateTime') else None
            e = EVAL.date(); age = e.year - birth.year - ((e.month, e.day) < (birth.month, birth.day))
            info[s] = {'sex': p['gender'], 'age': age, 'death': death, 'last': '', 'dx': [], 'meds': {}, 'k': None, 'mg': None}
        for name, rows in self.data.items():
            for r in rows:
                s = r['identifier'][0]['value'] if r['resourceType'] == 'Patient' else T.owner(r, self.subject)
                if not s: continue
                for v in T.iter_dates(r):
                    if r['resourceType'] == 'Patient' and v == r.get('birthDate'): continue
                    if v[:10] > info[s]['last']: info[s]['last'] = v[:10]
                if name in ('MimicCondition', 'MimicConditionED'):
                    for c in r['code']['coding']:
                        info[s]['dx'].append((c.get('code', ''), c.get('display', ''), 'icd9' in c.get('system', ''), r['id']))
                if name == 'MimicMedicationRequest' and 'medicationReference' in r:
                    m = self.medname(r['medicationReference']['reference'].split('/')[-1])
                    if m in DOSES and m not in ANTICOAGULANTS and m not in WATCH:
                        info[s]['meds'][m] = info[s]['meds'].get(m, 0) + 1
                if name == 'MimicObservationLabevents' and r.get('valueQuantity'):
                    code = r['code']['coding'][0]['code']
                    if code in ('50971', '50960'):
                        key = 'k' if code == '50971' else 'mg'
                        if not info[s][key] or r['effectiveDateTime'] > info[s][key][0]:
                            info[s][key] = (r['effectiveDateTime'], r['valueQuantity']['value'])
        for s, v in info.items():
            v['last'] = (dt.date.fromisoformat(v['last']) + dt.timedelta(days=self.offsets[s])).isoformat()
        self.info = info

    def medname(self, med_id):
        if not hasattr(self, '_medname'):
            self._medname = {m['id']: n for n, m in self.meds.items()}
        return self._medname.get(med_id)

    def history(self, s):
        """Plain-language problem list from the patient's real coded diagnoses (most frequent first)."""
        counts = {}
        for code, disp, _, rid in self.info[s]['dx']:
            if not disp or rid in self.removed: continue
            if re.match(r'(?i)(long[- ]term|personal history of|history of|encounter for|other specified|unspecified place)', disp): continue
            counts[disp] = counts.get(disp, 0) + 1
        hist = [d[0].lower() + d[1:] if d[:2].isupper() is False else d for d, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:4]]
        return ([NOTE_AF[s]] + hist[:3]) if s in NOTE_AF else hist

    # ------------------------------------------------------------------ outpatient layer (every living patient)
    def outpatient(self, s, spec):
        info = self.info[s]
        last = dt.date.fromisoformat(info['last'])
        rng = random.Random('visits:' + s)
        first = last + dt.timedelta(days=rng.randint(21, 45))
        dates = []
        d = first
        cap = spec.get('last_visit') or EVAL.date() - dt.timedelta(days=rng.randint(6, 45))
        while d <= cap:
            dates.append(d); d += dt.timedelta(days=rng.randint(60, 130))
        if not dates:
            dates = [EVAL.date() - dt.timedelta(days=rng.randint(12, 40))]
        # A case's fixed visit takes the place of the routine visit nearest to it, so case charts are no busier than others.
        fixed = set(spec.get('visits', [])) | {x for _, start, stop in spec.get('drugs', []) for x in (start, stop) if x and x >= first}
        for f in sorted(fixed):
            near = [g for g in dates[1:] if abs((g - f).days) <= 50 and g not in fixed]
            if near:
                dates.remove(min(near, key=lambda g: abs((g - f).days)))
        visits = {d: None for d in dates}
        for d in spec.get('visits', []):
            visits[d] = None
        order = sorted(visits)
        home = [m for m, _ in sorted(info['meds'].items(), key=lambda kv: -kv[1])][:rng.randint(2, 5)] or ['Aspirin', 'Atorvastatin']
        chronic = {m: (order[0], None) for m in home}                                 # drug -> (start, stop)
        for drug, start, stop in spec.get('drugs', []):
            chronic[drug] = (start or order[0], stop)
            if start and start not in visits: visits[start] = None
            if stop and stop not in visits: visits[stop] = None
        order = sorted(visits)
        # Routine medication changes for every patient: a new maintenance drug, a discontinued home drug.
        routine = [m for m in DOSES if m not in chronic and m not in WATCH and m not in ANTICOAGULANTS and m in self.meds]
        later = [v for v in order[1:] if v not in fixed]
        if later and rng.random() < 0.45:
            chronic[rng.choice(routine)] = (rng.choice(later), None)
        stoppable = [m for m in home if m in chronic]
        if later and stoppable and rng.random() < 0.3:
            m = rng.choice(stoppable); chronic[m] = (chronic[m][0], rng.choice(later))
        k_base = info['k'][1] if info['k'] else 4.1
        mg_base = info['mg'][1] if info['mg'] else 2.0
        on_warfarin = any(d == 'Warfarin' for d in chronic)
        valid = {}
        for i, day in enumerate(order):
            hh, mm = rng.choice([(9, 0), (9, 40), (10, 20), (11, 0), (13, 30), (14, 10), (15, 0)])
            when = at(day, hh, mm)
            enc = self.encounter(s, when)
            visits[day] = (when, enc)
            nxt = order[i + 1] if i + 1 < len(order) else None
            for drug, (start, stop) in chronic.items():
                if stop == day:
                    self.keys[f'{s}:{drug}:stop'] = self.order(s, drug, when + dt.timedelta(minutes=26), enc, status='stopped', days=1)
                    valid.pop(drug, None)
                    continue
                active = start <= day and not (stop and stop <= day)
                if not active:
                    continue
                need = (nxt + dt.timedelta(days=30)) if nxt else (EVAL.date() + dt.timedelta(days=90))
                if start == day or valid.get(drug, day) < need:
                    kind = 'start' if start == day else 'refill'
                    oid = self.order(s, drug, when + dt.timedelta(minutes=25 if kind == 'start' else 27), enc, days=(need - day).days + rng.randint(0, 20))
                    self.keys[f'{s}:{drug}:{kind}' if kind == 'start' else f'{s}:{drug}:refill:{day}'] = oid
                    valid[drug] = need
            if i == 0 or rng.random() < 0.35:
                self.keys[f'{s}:K:{day}'] = self.lab(s, '50971', round(k_base + rng.uniform(-0.3, 0.3), 1), when + dt.timedelta(minutes=50), enc)
                if rng.random() < 0.6:
                    self.keys[f'{s}:Mg:{day}'] = self.lab(s, '50960', round(mg_base + rng.uniform(-0.15, 0.15), 1), when + dt.timedelta(minutes=50), enc)
            if (on_warfarin and chronic['Warfarin'][0] <= day and not (chronic['Warfarin'][1] and chronic['Warfarin'][1] <= day)
                    and day not in spec.get('no_inr', [])):
                inr = round(rng.uniform(2.0, 2.9), 1)
                self.lab(s, '51237', inr, when + dt.timedelta(minutes=20), enc)
                if rng.random() < 0.35 and day < D(2026, 7, 1):   # routine anticoagulation-clinic call, no dose change
                    call = at(day + dt.timedelta(days=rng.randint(1, 3)), rng.choice([10, 11, 14, 15]), rng.choice([5, 20, 40]))
                    self.note(s, f'inr-call:{day}', call, 'pharmacy', 'pharmacist', rng.choice([
                        f'Anticoagulation clinic (telephone). INR {inr} on {day.month}/{day.day}, in goal range. Continue warfarin 5 mg daily; no change. '
                        'Next INR with next clinic visit.',
                        f'Anticoagulation clinic. Reviewed INR {inr} from {day.month}/{day.day}: therapeutic. Warfarin dose unchanged (5 mg daily). '
                        'Patient reminded about consistent vitamin K intake.']), reading={'dose_change': None})
            current = [m for m, (st, sp) in chronic.items() if st <= day and not (sp and sp <= day)]
            extra = spec.get('visit_text', {}).get(day, '') or (spec.get('visit_text_first', '') if i == 0 else '')
            text = self.progress_text(s, day, current, rng, extra)
            self.note(s, f'visit:{day}', when + dt.timedelta(minutes=35), 'progress', 'clinician', text, enc,
                      reading=spec.get('visit_reading', {}).get(day) or (spec.get('visit_reading_first') if i == 0 else None))
        # Routine nurse telephone notes for every patient (refills, scheduling, questions).
        for n in range(rng.choice([0, 0, 1, 1, 2])):
            i = rng.randrange(len(order))
            day = order[i] + dt.timedelta(days=rng.randint(5, 40))
            if day >= EVAL.date() or (i + 1 < len(order) and day >= order[i + 1]):
                continue
            current = sorted(m for m, (st, sp) in chronic.items() if st <= day and not (sp and sp <= day))
            drug = rng.choice(current) if current else 'Aspirin'
            name = drug.split(' (')[0]
            text = rng.choice([f'Refill request for {name} received from pharmacy. Forwarded to provider; sent at current dose.',
                               'Patient called to reschedule follow-up appointment. Rescheduled; no clinical concerns reported.',
                               f'Patient called asking whether to take {name} with food. Advised to take as prescribed; no change.',
                               'Returned patient call regarding clinic letter. Questions answered.'])
            self.note(s, f'phone:{n}:{day}', at(day, rng.choice([9, 10, 13, 16]), rng.choice([0, 15, 30, 45])), 'telephone', 'nurse', text)
        self.visits[s] = visits
        return visits

    def progress_text(self, s, day, current, rng, extra):
        info = self.info[s]
        who = 'woman' if info['sex'] == 'female' else 'man'
        hist = self.history(s)
        sig = lambda m: f"{m.split(' (')[0]} {DOSES[m][0].replace(' Tab', '').replace(' Cap', '')} {DOSES[m][3].lower().replace('daily', 'daily').replace('bid', 'twice daily').replace('tid', 'three times daily')}"
        opener = rng.choice(['Cardiology clinic follow-up.', 'Seen in cardiology clinic for routine follow-up.', 'Clinic visit, cardiology.'])
        lines = [opener,
                 f"{info['age'] - (EVAL.date() - day).days // 365}-year-old {who}. History includes {', '.join(hist[:-1]) + (' and ' + hist[-1] if len(hist) > 1 else hist[0] if hist else 'no significant history')}." if hist else f"{info['age']}-year-old {who}.",
                 'Current medications: ' + ('; '.join(sig(m) for m in sorted(current)) if current else 'none') + '.',
                 f"BP {rng.randint(112, 148)}/{rng.randint(64, 88)}, weight stable. {rng.choice(['No chest pain or syncope.', 'Denies palpitations or presyncope.', 'Mild exertional fatigue, otherwise well.', 'Feels well.'])}"]
        if extra:
            lines.append(extra)
        lines.append(rng.choice(['Continue current regimen. Return in 3 months.', 'No changes today. Follow up in 3-4 months.', 'Plan as above; routine follow-up.']))
        return '\n'.join(lines)


REMOVE_AF = {'10004235', '10020306'}
# Other whole Condition records removed (subject -> ICD pattern): an acute inpatient coagulopathy code that would read as a
# standing contraindication.
REMOVE_DX = {'10020306': r'^D689'}
# v0.3.2 calibration: 10020306's AF codes stay removed, but her clinic notes carry AF in the history line.
NOTE_AF = {'10020306': 'persistent atrial fibrillation', '10004235': 'paroxysmal atrial fibrillation'}   # v0.3.4: 10004235 too
D = dt.date


def spec_table():
    """Per-patient outpatient specifics (MIMIC subject id). Everything else follows the generic layer."""
    return {
        # Anticoagulation
        '10004457': {'drugs': [('Apixaban', None, None)], 'visits': [D(2026, 8, 20)]},
        '10005348': {'drugs': [('Warfarin', None, None)],
                     'visit_text_first': 'Remote history of GI bleed (2019), fully resolved; tolerating warfarin without bleeding.'},
        '10014354': {'drugs': [('Rivaroxaban', None, None), ('Apixaban', D(2026, 7, 15), None)], 'last_visit': D(2026, 7, 15),
                     'visit_text': {D(2026, 7, 15): 'Switching anticoagulant from rivaroxaban to apixaban for insurance coverage. Start apixaban 5 mg twice daily.'},
                     'visit_reading': {D(2026, 7, 15): {'switch': ['Rivaroxaban', 'Apixaban']}}},
        '10022880': {'drugs': [('Warfarin', D(2025, 12, 15), D(2026, 5, 10)), ('Apixaban', D(2026, 5, 10), None), ('Citalopram', D(2026, 3, 2), None)],
                     'visits': [D(2026, 3, 7)],
                     'visit_text': {D(2026, 5, 10): 'Transitioning from warfarin to apixaban; warfarin discontinued today.',
                                    D(2026, 3, 7): 'ECG today: sinus rhythm.'},
                     'visit_reading': {D(2026, 5, 10): {'switch': ['Warfarin', 'Apixaban']}, D(2026, 3, 7): {'rhythm': 'sinus'}}},
        '10015272': {'drugs': [('Warfarin', None, None)], 'visits': [D(2026, 6, 10)],
                     'visit_text': {D(2026, 6, 10): 'ECG obtained today: normal sinus rhythm, rate 72.'},
                     'visit_reading': {D(2026, 6, 10): {'rhythm': 'sinus'}}},
        # QT safety (chronic watch-list drugs started before any ECG-after-start memo, except 10004422)
        '10023239': {'drugs': [('Citalopram', D(2023, 10, 2), None)]},
        '10004422': {'drugs': [('Warfarin', None, None), ('Amiodarone', D(2025, 11, 10), None)]},
        '10012853': {'drugs': [('Warfarin', None, None), ('Amiodarone', D(2022, 3, 1), None)], 'last_visit': D(2026, 9, 2)},
        # Follow-up after starting watch-list drugs
        '10039831': {'drugs': [('Escitalopram Oxalate', D(2026, 8, 1), None)]},
        '10029291': {'drugs': [('Haloperidol', D(2026, 9, 15), None)]},
        '10018423': {'drugs': [('Escitalopram Oxalate', D(2026, 4, 10), None)]},
        '10021312': {'drugs': [('Escitalopram Oxalate', D(2026, 8, 10), None)]},
        # INR after warfarin dose changes
        '10016150': {'drugs': [('Warfarin', None, None)], 'last_visit': D(2026, 9, 1), 'visits': [D(2026, 9, 1)], 'no_inr': [D(2026, 9, 1)],
                     'visit_text': {D(2026, 9, 1): 'INR today 1.6, subtherapeutic. Increase warfarin to 7.5 mg daily; recheck INR.'},
                     'visit_reading': {D(2026, 9, 1): {'dose_change': 'Warfarin'}}},
        '10002495': {'drugs': [('Warfarin', None, None)]},
        # Look-alikes
        '10001217': {'visits': [D(2025, 11, 23)], 'visit_text': {D(2025, 11, 23): 'ECG today: sinus rhythm.'},
                     'visit_reading': {D(2025, 11, 23): {'rhythm': 'sinus'}}},
        '10009628': {'drugs': [('Warfarin', None, None)]}, '10022017': {'drugs': [('Apixaban', None, None)]},
        '10020786': {'drugs': [('Apixaban', None, None)]},
        # v0.2 cases: QTc just over threshold contradicting a documented 'QT acceptable'; ECG window set by the memo in force at the start
        '10013049': {'drugs': [('Escitalopram Oxalate', D(2024, 5, 14), None)], 'visits': [D(2024, 5, 14)],
                     'visit_text': {D(2024, 5, 14): 'Reviewed ECG from 10/8/2023: sinus rhythm, QT acceptable. Start escitalopram 10 mg daily; PCP aware.'},
                     'visit_reading': {D(2024, 5, 14): {'qt_assessment': 'acceptable', 'ecg': '108018814'}}},
        '10019385': {'drugs': [('Escitalopram Oxalate', D(2026, 2, 12), None)]},
        '10019172': {'drugs': [('Apixaban', None, None)], 'visit_text_first': 'Pulse regular; in sinus rhythm today.',
                     'visit_reading_first': {'rhythm': 'sinus'}},
    }


def build():
    b = Builder()
    b.keys, b.visits = {}, {}
    b.context()
    specs = spec_table()
    # A3: AF documented only on the ECG -> remove this patient's AF diagnosis codes (whole Condition records).
    # 10020306: AF documented only in inpatient rhythm charting (no codes, no ECGs).
    for s in REMOVE_AF:
        b.removed += sorted({rid for code, _, _, rid in b.info[s]['dx'] if AF_CODE.match(code.replace('.', ''))})
    for s, pat in REMOVE_DX.items():
        b.removed += sorted({rid for code, _, _, rid in b.info[s]['dx'] if re.match(pat, code.replace('.', ''))} - set(b.removed))
    memos = {
        'standing': b.memo('standing', D(2024, 6, 1), 'Anticoagulation clinic standing order',
                           'Clinic pharmacists may adjust warfarin doses under the anticoagulation protocol and document the change. Nurses may relay '
                           'instructions but may not change doses.', {'authority': {'warfarin_dose': ['clinician', 'pharmacist']}}),
        'qt': b.memo('qt', D(2025, 1, 15), 'QT monitoring',
                     'QT watch list: citalopram, escitalopram, haloperidol, methadone, amiodarone, sotalol, dofetilide. For a patient taking a '
                     'watch-list medication, a most recent ECG with QTc (Bazett) of 500 ms or more requires prescriber review.',
                     {'watch_list': list(WATCH), 'qtc_threshold': 500, 'formula': 'bazett'}),
        'ecg30': b.memo('ecg30', D(2025, 9, 1), 'ECG after starting QT watch-list medications',
                        'Effective 9/1/2025 for medications started on or after that date: obtain an ECG within 30 days after a QT watch-list '
                        'medication is started at a Cardiology Clinic visit.',
                        {'post_start_ecg_days': 30, 'effective': '2025-09-01'}),
        'ecg14': b.memo('ecg14', D(2026, 3, 1), 'ECG after starting QT watch-list medications (revised)',
                        'Replaces the 9/1/2025 memo for medications started on or after 3/1/2026 (earlier starts keep the 30-day window): obtain '
                        'an ECG within 14 days after a QT watch-list medication is started at a Cardiology Clinic visit.', {'post_start_ecg_days': 14, 'effective': '2026-03-01', 'replaces': 'ecg30'}),
        'inr': b.memo('inr', D(2026, 3, 1), 'INR after warfarin dose changes',
                      'Effective 3/1/2026: after a warfarin dose change made by a Cardiology Clinic clinician or clinic pharmacist, obtain an INR within 7 days. '
                      'Dose changes are documented in the note that makes them; refills at an unchanged dose are not changes.',
                      {'inr_days': 7, 'effective': '2026-03-01'}),
        'parking': b.memo('parking', D(2026, 2, 2), 'Clinic operations', 'Patient parking moves to the east garage during lobby renovation. '
                          'Check-in kiosks are available at both entrances.', {}),
    }
    living = [s for s, v in b.info.items() if not v['death']]
    for s in sorted(living):
        b.outpatient(s, specs.get(s, {}))
    extras(b, memos)
    return b, memos


def extras(b, memos):
    """Case records that are not clinic visits: outside records, telephone and pharmacist notes, labs."""
    k = b.keys
    k['10004457:bleed'] = b.note('10004457', 'outside-bleed', at(D(2026, 8, 12), 15, 20), 'outside', 'clinician',
        'Outside records received and reviewed (Mercy Hospital). Admitted 8/2/2026-8/5/2026 with upper GI bleeding from a duodenal ulcer; '
        'hemoglobin nadir 6.9, transfused 2 units. Apixaban held at discharge pending cardiology review.',
        reading={'contraindication': 'recent_major_bleed', 'held': 'Apixaban'})
    k['10012853:dose'] = b.note('10012853', 'pharm-dose', at(D(2026, 9, 10), 11, 5), 'pharmacy', 'pharmacist',
        'Anticoagulation clinic (telephone). Home INR 3.4. Warfarin decreased from 5 mg to 4 mg daily per protocol. Patient verbalized understanding.',
        reading={'dose_change': 'Warfarin'})
    k['10016150:inr'] = b.lab('10016150', '51237', 2.3, at(D(2026, 9, 5), 8, 40))
    k['10021312:phone'] = b.note('10021312', 'phone-ecg', at(D(2026, 8, 25), 10, 15), 'telephone', 'nurse',
        'Telephone call. Patient reports she had an ECG at Northside Urgent Care on 8/18. Report requested by fax; not yet received.',
        reading={'unreceived_ecg': '2026-08-18'})
    b.note('10002495', 'phone-extra', at(D(2026, 8, 19), 16, 0), 'telephone', 'nurse',
           'Patient called: took an extra warfarin tablet on Saturday by mistake. No bleeding. Advised to continue usual dose; no change made.',
           reading={'dose_change': None})


# ---------------------------------------------------------------------- answers (authored) and checks
def med_orders(b, s):
    """All medication orders for a patient (real re-anchored + added): (id, drug, authored, status, validity_end)."""
    pid, off = b.pid[s], b.offsets[s]
    out = []
    for r in b.data['MimicMedicationRequest']:
        if r['subject']['reference'] != 'Patient/' + pid or 'medicationReference' not in r: continue
        end = (r.get('dispenseRequest') or {}).get('validityPeriod', {}).get('end')
        out.append((r['id'], b.medname(r['medicationReference']['reference'].split('/')[-1]), T.shift_value(r['authoredOn'], off), r['status'],
                    T.shift_value(end, off) if end else None))
    for r in b.added:
        if r['resourceType'] == 'MedicationRequest' and r['subject']['reference'] == 'Patient/' + pid:
            out.append((r['id'], b.medname(r['medicationReference']['reference'].split('/')[-1]), r['authoredOn'], r['status'],
                        r['dispenseRequest']['validityPeriod']['end']))
    return out


def current_orders(b, s, drug):
    rows = sorted(o for o in med_orders(b, s) if o[1] == drug and o[2] <= iso(EVAL))
    rows = [o for o in rows]  # authoredOn order
    rows.sort(key=lambda o: o[2])
    if not rows or rows[-1][3] == 'stopped':
        return []
    return [o[0] for o in rows if o[3] != 'stopped' and o[4] and o[4] >= iso(EVAL) and
            not any(x[3] == 'stopped' and x[2] > o[2] for x in rows)]


def latest_lab(b, s, code):
    pid, off = b.pid[s], b.offsets[s]
    rows = [(T.shift_value(o['effectiveDateTime'], off), o['id']) for o in b.data['MimicObservationLabevents']
            if o['subject']['reference'] == 'Patient/' + pid and o['code']['coding'][0]['code'] == code]
    rows += [(o['effectiveDateTime'], o['id']) for o in b.added if o['resourceType'] == 'Observation' and o['subject']['reference'] == 'Patient/' + pid
             and o['code']['coding'][0]['code'] == code]
    rows = sorted(r for r in rows if r[0] <= iso(EVAL))
    assert len(rows) < 2 or rows[-1][0] != rows[-2][0], (s, code, 'tie')
    return rows[-1][1]


def risk(b, s):
    info = b.info[s]; factors = set()
    for code, _, icd9, rid in info['dx']:
        if rid in b.removed: continue
        c = code if not icd9 else code
        for name, pat in RISK.items():
            if re.match(pat, c): factors.add(name)
    if info['age'] >= 75: factors.add('AGE_75_PLUS')
    elif info['age'] >= 65: factors.add('AGE_65_74')
    if info['sex'] == 'female': factors.add('FEMALE')
    score = sum(2 if f in ('STROKE_TIA', 'AGE_75_PLUS') else 1 for f in factors)
    return score, factors


def answers(b, memos):
    k = b.keys; pid = b.pid
    current_ecg = {}
    for e in b.catalog:
        if e['ecg_time'] <= EVAL.strftime('%Y-%m-%d %H:%M:%S') and (e['patient'] not in current_ecg or e['ecg_time'] > current_ecg[e['patient']]['ecg_time']):
            current_ecg[e['patient']] = e
    # ECG interpretations: most recent ECG of every patient with ECGs (specs from qa/task4_interp_truth.py)
    interp = json.loads((HERE / 'task4/ecg_interp.json').read_text())
    findings = []
    living_pid = {b.pid[s] for s, v in b.info.items() if not v['death']}
    optional = sorted(e['study_id'] for p, e in current_ecg.items() if p not in living_pid)   # deceased: neither required nor penalized
    for p, e in sorted(current_ecg.items()):
        if p not in living_pid:
            continue
        L = interp['latest'][p]
        assert L['ecg'] == e['study_id'], (p, L['ecg'], e['study_id'])
        findings.append({'patient': p, 'subject': e['subject_id'], 'ecg': L['ecg'], 'fields': L['fields'], 'prior_ecg': L['prior_ecg'],
                         'changes': L['changes']})
    rhythm = {}
    for o in b.data.get('MimicObservationChartevents', []):
        if o['code']['coding'][0]['code'] == '220048' and re.match(r'^(AF|A Flut)', o.get('valueString') or ''):
            rhythm.setdefault(T.owner(o, b.subject), set()).add(o['id'])
    # Any record that documents AF: coded diagnoses, AF ECGs, charted rhythm, clinic notes naming AF.
    af_conditions = lambda s: sorted({rid for code, _, _, rid in b.info[s]['dx'] if AF_CODE.match(code.replace('.', '')) and rid not in b.removed}
                                     | {e['study_id'] for e in b.catalog if e['subject_id'] == s and b.truth[e['study_id']]['label'] == 'AF'}
                                     | rhythm.get(s, set())
                                     | {n[1] for n in b.notes_by_patient.get(s, []) if re.search(r'atrial (fibrillation|flutter)', n[2], re.I)})
    # At least one record establishing AF is required; coded dysrhythmias from the same history (ICD-9 427.x, ICD-10 I47-I49) are
    # accepted as corroboration alongside it (v0.3.6: four runs cited 427.89 next to 10004235's AF evidence).
    dysrhythmia = lambda s: sorted({rid for code, _, _, rid in b.info[s]['dx'] if re.match(r'^(427|I4[7-9])', code.replace('.', ''))
                                    and rid not in b.removed} - set(af_conditions(s)))
    af_spec = lambda s: {'cover': [af_conditions(s)], 'also': dysrhythmia(s)}
    ex = lambda v: {'exact': v}
    items = []
    def item(s, category, reason, ecg_fields=(), **fields):
        items.append({'patient': pid[s], 'subject': s, 'category': category, 'reason': reason, 'fields': fields, 'ecg_fields': list(ecg_fields)})
    # Untreated AF (authored factor lists; cross-checked against the codes below)
    item('10039997', 'ANTICOAGULATION', 'UNTREATED_AF', af_evidence=af_spec('10039997'), risk_score=ex(5),
         risk_factors={'set': ['AGE_65_74', 'FEMALE', 'HYPERTENSION', 'STROKE_TIA']}, anticoagulant={'null': True})
    item('10023771', 'ANTICOAGULATION', 'UNTREATED_AF', af_evidence=af_spec('10023771'), risk_score={'one_of': [2, 3]},
         risk_factors={'set_one_of': [['AGE_65_74', 'HYPERTENSION'], ['AGE_65_74', 'HYPERTENSION', 'VASCULAR']]}, anticoagulant={'null': True})
    item('10004235', 'ANTICOAGULATION', 'UNTREATED_AF', ecg_fields=[], af_evidence=af_spec('10004235'), risk_score=ex(2),
         risk_factors={'set': ['CHF', 'HYPERTENSION']}, anticoagulant={'null': True})
    item('10020306', 'ANTICOAGULATION', 'UNTREATED_AF', af_evidence=af_spec('10020306'), risk_score=ex(9),
         risk_factors={'set': ['AGE_75_PLUS', 'CHF', 'DIABETES', 'FEMALE', 'HYPERTENSION', 'STROKE_TIA', 'VASCULAR']}, anticoagulant={'null': True})
    item('10004457', 'ANTICOAGULATION', 'ANTICOAGULANT_WITH_CONTRAINDICATION',
         anticoagulant={'one_of': current_orders(b, '10004457', 'Apixaban')}, contraindication=ex(k['10004457:bleed']))
    item('10014354', 'CONTRADICTION', 'DUAL_ANTICOAGULATION',
         records={'cover': [current_orders(b, '10014354', 'Rivaroxaban'), current_orders(b, '10014354', 'Apixaban')],
                  'also': [n[1] for n in b.notes_by_patient['10014354'] if 'Rivaroxaban' in n[2] and 'Apixaban' in n[2]]})
    rhythm_note = next(n[1] for n in b.notes_by_patient['10015272'] if 'normal sinus rhythm' in n[2])
    af_same_day = [e['study_id'] for e in b.catalog if e['subject_id'] == '10015272' and e['ecg_time'].startswith('2026-06-10')]
    item('10015272', 'CONTRADICTION', 'RHYTHM_DOCUMENTATION_CONFLICT', ecg_fields=['records'], records={'cover': [[rhythm_note], af_same_day]})
    for s, ecg, drug in (('10023239', '104821039', 'Citalopram'), ('10004422', '106885519', 'Amiodarone'), ('10012853', '101515306', 'Amiodarone'),
                         ('10013049', '108018814', 'Escitalopram Oxalate')):
        t = b.truth[ecg]
        item(s, 'QT_SAFETY', 'PROLONGED_QTC_ON_WATCH_LIST_DRUG', ecg_fields=['ecg', 'qtc_ms', 'heart_rate'], ecg=ex(ecg), qtc_ms={'range': t['qtc_range']}, heart_rate={'range': t['hr_range']},
             qt_drug={'one_of': current_orders(b, s, drug)}, potassium=ex(latest_lab(b, s, '50971')), magnesium=ex(latest_lab(b, s, '50960')))
    def start_note(s, drug):  # the progress note of the visit that started the drug also documents the start
        start = next(st for d, st, _ in spec_table()[s]['drugs'] if d == drug)
        notes = [n[1] for n in b.notes_by_patient[s] if n[0].date() == start and drug.split()[0] in n[2]]
        assert len(notes) == 1, (s, drug, notes)
        return notes
    fu = lambda s, drug, due, status, memo, completion=None: item(
        s, 'FOLLOW_UP', 'ECG_AFTER_WATCH_LIST_START', ecg_fields=['completion_record'] if completion else [], status=ex(status),
        trigger={'one_of': [k[f'{s}:{drug}:start']] + start_note(s, drug)}, requirement=ex(memos[memo]),
        due_date=ex(due), completion_record=ex(completion))
    fu('10039831', 'Escitalopram Oxalate', '2026-08-15', 'overdue', 'ecg14')
    fu('10029291', 'Haloperidol', '2026-09-29', 'not_due', 'ecg14')
    fu('10018423', 'Escitalopram Oxalate', '2026-04-24', 'overdue', 'ecg14')
    fu('10022880', 'Citalopram', '2026-03-16', 'completed', 'ecg14', '104882441')
    fu('10021312', 'Escitalopram Oxalate', '2026-08-24', 'cannot_determine', 'ecg14')
    fu('10004422', 'Amiodarone', '2025-12-10', 'completed', 'ecg30', '106885519')
    fu('10019385', 'Escitalopram Oxalate', '2026-03-14', 'completed', 'ecg30', '101538691')
    dose_note_16150 = next(n[1] for n in b.notes_by_patient['10016150'] if 'Increase warfarin' in n[2])
    item('10016150', 'FOLLOW_UP', 'INR_AFTER_WARFARIN_DOSE_CHANGE', status=ex('completed'), trigger=ex(dose_note_16150), requirement=ex(memos['inr']),
         due_date=ex('2026-09-08'), completion_record=ex(k['10016150:inr']))
    item('10012853', 'FOLLOW_UP', 'INR_AFTER_WARFARIN_DOSE_CHANGE', status=ex('overdue'), trigger=ex(k['10012853:dose']), requirement=ex(memos['inr']),
         due_date=ex('2026-09-17'), completion_record=ex(None))
    return {'items': items, 'interpretations': findings, 'optional_interpretations': optional, 'current_ecg': {p: e['study_id'] for p, e in current_ecg.items()}}


def checks(b, ans):
    """Guard against unintended cases created by the real data or the generic layer."""
    living = {s for s, v in b.info.items() if not v['death']}
    af_ecg = {e['subject_id'] for e in b.catalog if b.truth[e['study_id']]['label'] == 'AF'}
    flagged = {(i['subject'], i['reason']) for i in ans['items']}
    for s in sorted(living):
        af = any(AF_CODE.match(c.replace('.', '')) and rid not in b.removed for c, _, _, rid in b.info[s]['dx']) or s in af_ecg
        anticoag = [d for d in ANTICOAGULANTS if d in b.meds and current_orders(b, s, d)]
        score, factors = risk(b, s)
        if af and not anticoag:
            thresh = 3 if b.info[s]['sex'] == 'female' else 2
            assert score >= thresh and (s, 'UNTREATED_AF') in flagged, (s, score, factors)
            item = next(i for i in ans['items'] if i['subject'] == s and i['reason'] == 'UNTREATED_AF')
            rf, rs = item['fields']['risk_factors'], item['fields']['risk_score']
            assert sorted(factors) in ([rf['set']] if 'set' in rf else rf['set_one_of']) and score in ([rs['exact']] if 'exact' in rs else rs['one_of']), (s, factors, score)
            # Coronary disease with revascularization counts as vascular disease under some definitions: the decision must not depend on it.
            broad = any(re.match(VASCULAR_BROAD, c.replace('.', '')) and rid not in b.removed for c, _, _, rid in b.info[s]['dx'])
            assert score + (broad and 'VASCULAR' not in factors) >= thresh
            if broad and 'VASCULAR' not in factors:
                assert 'set_one_of' in rf and score + 1 in rs['one_of'], (s, 'vascular definition changes the answer fields')
        if len(anticoag) > 1:
            assert (s, 'DUAL_ANTICOAGULATION') in flagged, (s, anticoag)
        watch = [d for d in WATCH if d in b.meds and current_orders(b, s, d)]
        cur = ans['current_ecg'].get(b.pid[s])
        if watch and cur and b.truth[cur]['label'] == 'QTC_PROLONGED':
            assert (s, 'PROLONGED_QTC_ON_WATCH_LIST_DRUG') in flagged, s
        if (s, 'PROLONGED_QTC_ON_WATCH_LIST_DRUG') in flagged:
            assert len(watch) == 1, (s, watch)
    for i in ans['items']:
        assert i['subject'] in living, i
    return True


def write(b, memos, ans):
    import shutil
    over = TASK / 'environment/service/overlay'
    over.mkdir(parents=True, exist_ok=True)
    offsets = {b.pid[s]: off for s, off in b.offsets.items()}
    catalog = [{k: e[k] for k in ('study_id', 'patient', 'ecg_time', 'path')} for e in b.catalog]
    (over / 'overlay.json').write_text(json.dumps({'offsets': offsets, 'removed': sorted(b.removed), 'ecg_catalog': catalog}, indent=1) + '\n')
    with gzip.GzipFile(over / 'added.ndjson.gz', 'wb', mtime=0) as g:
        for r in sorted(b.added, key=lambda r: r['id']):
            g.write((json.dumps(r, separators=(',', ':')) + '\n').encode())
    import numpy as np
    ddir = over / 'ecg_deltas'
    if ddir.exists(): shutil.rmtree(ddir)
    ddir.mkdir()
    deltas = np.load(HERE / 'task4/ecg_deltas.npz')
    for sid in deltas.files:
        (ddir / (sid + '.bin')).write_bytes(deltas[sid].astype('<i4').tobytes())
    (TASK / 'tests').mkdir(exist_ok=True); (TASK / 'solution').mkdir(exist_ok=True)
    (TASK / 'tests/expected.json').write_text(json.dumps(ans, indent=1) + '\n')
    specs = json.loads((HERE / 'task4/ecg_interp.json').read_text())['ecg']
    mid = lambda sp: round(sum(sp['range']) / 2) if 'range' in sp else None
    base = lambda t: 'AF' if t['label'] == 'AF' else 'PACED' if t['label'] == 'PACED' else 'SINUS'
    rhythm_of = lambda t, opts: base(t) if base(t) in opts else opts[0]
    expert = {sid: {'label': t['label'], 'hr': round(sum(t['hr_range']) / 2, 1) if t['hr_range'] else None,
                    'rhythm': specs[sid]['rhythm'].get('exact') or rhythm_of(t, specs[sid]['rhythm']['one_of']),
                    'pr_ms': mid(specs[sid]['pr_ms']), 'qrs_ms': mid(specs[sid]['qrs_ms']),
                    'qtc_ms': round(sum(t['qtc_range']) / 2) if t.get('qtc_range') else mid(specs[sid]['qtc_ms']),
                    'axis': specs[sid]['axis'].get('exact') or (specs[sid]['axis'].get('one_of') or [None])[0],
                    'conduction': specs[sid]['conduction']['required']} for sid, t in b.truth.items()}
    (TASK / 'solution/readings.json').write_text(json.dumps({'notes': b.readings, 'ecg': expert}, indent=1) + '\n')


def main():
    b, memos = build()
    ans = answers(b, memos)
    checks(b, ans)
    write(b, memos, ans)
    from collections import Counter
    print('added', len(b.added), 'resources; removed', len(b.removed), '| items', len(ans['items']), dict(Counter(i['reason'] for i in ans['items'])),
          '| ECG interpretations', len(ans['interpretations']), dict(Counter(json.dumps(f['fields']['rhythm']) for f in ans['interpretations'])))


if __name__ == '__main__':
    main()
