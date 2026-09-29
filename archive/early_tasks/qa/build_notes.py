"""Render the interacting-requirements cases (qa/graph_cases.py) as free-text clinical documentation.

Same authored facts and golden answers as qa/build_graph.py. What changes is the documentation:
corrections, retractions, holds and follow-up plans are written as varied clinical prose that names
records by their charted details instead of numbered machine clauses, with abbreviations, mixed date
formats, filler, confirmations that change nothing, and unauthorized look-alikes. Each statement still
has exactly one reading under the public policy. A private reading of every note (what an expert reader
extracts) is written for the reference solution only.
"""
import base64, calendar, datetime as dt, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_notes'
sys.path[:0] = [str(TASK / 'environment/service'), str(ROOT / 'qa')]
from fhir import extension, validate, digest, VERSION, NOW
from graph_cases import CASES
D = dt.date.fromisoformat
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
NAMES = {'clinician': ['Dr. Imani Shaw', 'Dr. Noah Patel', 'Dr. Elias Green'],
         'laboratory': ['Clinical Laboratory (M. Ortiz, MLS)', 'Lab Services, R. Chen'],
         'nurse': ['Mina Cho, RN', 'Jordan Lee, RN']}


def rid(key): return 'R' + hashlib.sha256(('notes-v1:' + key).encode()).hexdigest()[:12]
def plus(d, n): return (D(d) + dt.timedelta(days=n)).isoformat()
def pick(options, *seed):
    return options[int(hashlib.sha256(repr(seed).encode()).hexdigest(), 16) % len(options)]


def golden_due(anchor, months, intervals):
    a = D(anchor); ix = a.year * 12 + a.month - 1 + months; y, m = divmod(ix, 12)
    target = dt.date(y, m + 1, min(a.day, calendar.monthrange(y, m + 1)[1])); remaining = (target - a).days
    day = a; paused = 0
    while remaining:
        if any(D(s) <= day < D(e) for s, e in intervals): paused += 1
        else: remaining -= 1
        day += dt.timedelta(days=1)
    return day.isoformat(), paused


def fmt(value, *seed):
    """A date the way clinic staff write it. Dates outside 2026 always carry the year."""
    d = D(value); sfx = 'th' if 10 <= d.day % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')
    styles = [f'{d.month}/{d.day}/{d.year % 100:02d}', f'{MONTHS[d.month - 1][:3]} {d.day}, {d.year}', d.isoformat()]
    if d.year == 2026:
        styles += [f'{d.month}/{d.day}', f'{MONTHS[d.month - 1][:3]} {d.day}', f'{MONTHS[d.month - 1]} {d.day}{sfx}',
                   f'{d.day} {MONTHS[d.month - 1][:3]}']
    return pick(styles, value, *seed)


def listing(items):
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


class Case:
    def __init__(self, c, ci):
        self.c, self.ci = c, ci
        self.ref = lambda k: rid(c['key'] + '.' + k)
        self.plan_entered = {'p' + k: c['starts']['abc'.index(k)] for k in 'abc'}
        if c.get('extra_plan'):
            self.plan_entered.update(pa2=plus(c['starts'][0], 2), pa3=plus(c['starts'][0], 4))
        # Every record type is named by charted details, which must be unique inside the chart.
        assert len(set(c['starts'])) == 3
        assert len({h[1] for h in c['holds']}) == len(c['holds'])
        assert len({l[1] for l in c['labs']}) == len(c['labs'])
        assert len({(d, k[1]) for k, d in self.plan_entered.items()}) == len(self.plan_entered)

    def series(self, k, *seed):
        d = fmt(self.c['starts']['abc'.index(k)], 'series', k, *seed)
        return pick([f'the {d} series', f'the Bicillin series started {d}', f'the BPG course that began {d}',
                     f'the series begun {d}'], k, *seed)

    def injection(self, key, *seed):
        k, i = key[0], int(key[1:]); idx = 'abc'.index(k)
        charted = fmt(plus(self.c['starts'][idx], self.c['days'][idx][i - 1]), 'inj', key, *seed)
        s = self.series(k, 'inj', key, *seed)
        return pick([f'the injection charted {charted} under {s}', f'the {charted} dose on {s}',
                     f'the Bicillin dose documented for {charted} ({s})'], key, *seed)

    def hold(self, h, *seed):
        start = next(x[1] for x in self.c['holds'] if x[0] == h)
        d = fmt(start, 'hold', h, *seed)
        return pick([f'the review hold starting {d}', f'the clock hold that began {d}', f'the {d} review hold'], h, *seed)

    def plan(self, p, *seed):
        entered = fmt(self.plan_entered[p], 'plan', p, *seed); s = self.series(p[1], 'plan', p, *seed)
        return pick([f'the RPR follow-up plan entered {entered} for {s}', f'the {entered} follow-up plan ({s})'], p, *seed)

    def specimen(self, s, *seed):
        d = fmt(next(x[1] for x in self.c['labs'] if x[0] == s), 'spec', s, *seed)
        return pick([f'the specimen collected {d}', f'the {d} draw', f'the RPR specimen from {d}'], s, *seed)

    def report(self, key, *seed):
        d = fmt({'base': '2025-12-01', 'marker': '2025-12-10', 'marker2': '2025-12-12'}[key], 'rep', key, *seed)
        return pick([f'the {d} RPR', f'the RPR resulted from the {d} draw', f'the RPR report on the {d} specimen'], key, *seed)

    def describe(self, target, field, *seed):
        """Noun phrase for a correction, used when a later note retracts it."""
        what = {'date': 'date correction', 'course': 'series reassignment', 'status': 'status change',
                'courses': 'change to the series it covers', 'end': 'end-date change', 'titer': 'titer correction',
                'routine': 'schedule change'}[field]
        return f'the {what} for {self.thing(target, *seed)}'

    def thing(self, target, *seed):
        if target in ('base', 'marker', 'marker2'): return self.report(target, *seed)
        if target in self.plan_entered: return self.plan(target, *seed)
        if target[0] == 'h': return self.hold(target, *seed)
        if target[0] == 's': return self.specimen(target, *seed)
        return self.injection(target, *seed)

    def statement(self, role, target, field, value, *seed):
        """One explicit correction in the author's voice."""
        t = self.thing(target, *seed)
        cap = t[0].upper() + t[1:]
        if field == 'date' and target[0] == 's':
            d = fmt(value, 'v', *seed)
            return pick([f'{cap} was mislabeled; actual collection date {d}.', f'Collection date for {t} should read {d}.'], *seed)
        if field == 'date':
            d = fmt(value, 'v', *seed)
            return pick([f'{cap} was actually given on {d}; charting error.', f'Charting error: {t} should be dated {d}.',
                         f'{cap}: date should read {d}.'], *seed)
        if field == 'course':
            s = self.series(value, 'v', *seed)
            return pick([f'{cap} was drawn against the order for {s} and belongs to that series.',
                         f'Please reassign {t} to {s}.'], *seed)
        if field == 'status' and value == 'not-done':
            why = pick(['pt left before it was drawn up', 'held after pt reported feeling unwell', 'no injection was given; documentation error'], *seed)
            return pick([f'{cap} was not administered ({why}).', f'Correction: {t} was NOT given, {why}.'], *seed)
        if field == 'status' and value == 'completed':
            return pick([f'{cap} was in fact administered.', f'Correction: {t} was given after all.'], *seed)
        if field == 'status' and value == 'entered-in-error':
            return pick([f'{cap} was resulted on the wrong patient and is entered in error.',
                         f'{cap} is entered in error (specimen belonged to another pt).'], *seed)
        if field == 'status' and value == 'unavailable':
            return pick([f'{cap} was lost in transit and is unavailable.', f'{cap}: specimen unavailable (QNS/lost).'], *seed)
        if field == 'status' and value == 'revoked':
            return pick([f'Discontinue {t}.', f'{cap} is cancelled.'], *seed)
        if field == 'status' and value == 'active':
            return pick([f'Reactivate {t}.', f'{cap} should be active again.'], *seed)
        if field == 'courses':
            series = listing([self.series(k, 'v', i, *seed) for i, k in enumerate(value)])
            if target[0] == 'h':
                return pick([f'{cap} should apply to {series} only.', f'Scope of {t}: {series}.'], *seed)
            if target[0] == 's':
                return pick([f'{cap} was drawn as follow-up for {series} only.', f'{cap} supports {series} only.'], *seed)
            return pick([f'{cap} should be linked to {series} instead.', f'Relink {t} to {series}.'], *seed)
        if field == 'end':
            if pick([0, 1], *seed):
                return pick([f'{cap} was lifted on {fmt(value, "v", *seed)}.', f'{cap} ended; clocks resumed {fmt(value, "v", *seed)}.'], *seed)
            return pick([f'{cap} ran through {fmt(plus(value, -1), "v", *seed)}.', f'{cap}: last held day {fmt(plus(value, -1), "v", *seed)}.'], *seed)
        if field == 'titer':
            return pick([f'Corrected report: {t} titer is 1:{value} (previously reported 1:8).', f'{cap} should read 1:{value}.'], *seed)
        if field == 'routine':
            a, b = value.split(',')
            return pick([f'Per protocol, changing routine checkpoints on {t} to {a} and {b} months.',
                         f'Routine f/u on {t} moved to {a} mo / {b} mo.'], *seed)
        raise ValueError((target, field, value))


def build():
    sources = []; targets = {}; expected = {}; readings = {}
    for ci, c in enumerate(CASES):
        case = Case(c, ci); ref = case.ref
        pid = 'P' + rid(c['key'])[1:8]; eps = {k: 'E' + ref('ep' + k)[1:] for k in 'abc'}
        targets[pid] = list(eps.values()); sources.append({'resourceType': 'Patient', 'id': pid, 'name': [{'text': c['name']}]})
        for k, start in zip('abc', c['starts']):
            sources.append({'resourceType': 'EpisodeOfCare', 'id': eps[k], 'status': 'active', 'patient': {'reference': 'Patient/' + pid}, 'period': {'start': start}})

        def add(kind, key, day, **attrs):
            r = {'resourceType': kind, 'id': ref(key), 'subject': {'reference': 'Patient/' + pid},
                 'extension': [extension('event-time', 'DateTime', day + 'T08:00:00Z')], **attrs}
            sources.append(r); return r

        def note(key, day, role, text, hour=10):
            name = pick(NAMES[role], c['key'], key)
            text = text + '\n\n' + {'clinician': f'Electronically signed: {name}', 'laboratory': f'Released by {name}',
                                    'nurse': f'Signed: {name}'}[role]
            r = add('DocumentReference', key, day, status='current', docStatus='final', date=f'{day}T{hour:02d}:00:00Z',
                    description=text, author=[{'display': name}],
                    content=[{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(text.encode()).decode()}}])
            r['authenticator'] = r['author'][0]; r['extension'].append(extension('author-role', 'Code', role))
            return r['id']

        drug = lambda *s: pick(['Bicillin L-A 2.4 MU IM', 'benzathine penicillin G 2.4 million units IM', 'BPG 2.4MU IM',
                                'Bicillin LA 2.4 MU IM x1'], *s)
        for k, start, offsets in zip('abc', c['starts'], c['days']):
            r = add('MedicationRequest', k, start, status='active', intent='order', authoredOn=start + 'T08:00:00Z',
                    medicationCodeableConcept={'text': pick(['Bicillin L-A (benzathine penicillin G)', 'Benzathine penicillin G', 'BPG (Bicillin L-A)'], c['key'], k)},
                    dosageInstruction=[{'text': pick(['2.4 MU IM weekly x3', '2.4 million units IM qweek x 3 doses', 'Weekly IM injection, 3 doses'], c['key'], k)}])
            r['extension'].append(extension('episode', 'Reference', {'reference': 'EpisodeOfCare/' + eps[k]}))
            for i, off in enumerate(offsets, 1):
                day = plus(start, off)
                site = pick(['R ventrogluteal', 'L ventrogluteal', 'R gluteal', 'L gluteal'], c['key'], k, i)
                add('MedicationAdministration', k + str(i), day, status='completed', effectiveDateTime=day + 'T09:00:00Z',
                    medicationCodeableConcept={'text': drug(c['key'], k, i)}, request={'reference': 'MedicationRequest/' + ref(k)},
                    dosage={'text': pick([f'{drug(c["key"], k, i)}, {site}. Tolerated well.', f'Given {site}; observed 15 min, no reaction.',
                                          f'{site}. Lot on file.'], c['key'], k, i)})

        # Holds: amended holds stay structured; about half of the rest exist only as a clinician's note.
        amended = {t for _, _, clauses in c['edits'] for t, *_ in clauses}
        for hi, (h, start, end, courses) in enumerate(c['holds']):
            if h not in amended and (ci + hi) % 2 == 0:
                series = listing([case.series(k, 'holdnote', h, i) for i, k in enumerate(courses)])
                body = pick([f'Placing a review hold on the dosing and follow-up clocks for {series} from {fmt(start, h, 1)}; resume {fmt(end, h, 2)}.',
                             f'Review hold ordered for {series}: clocks paused {fmt(start, h, 3)} through {fmt(plus(end, -1), h, 4)}.'], c['key'], h)
                context = pick(['Pt admitted to outside hospital; records pending.', 'Awaiting ID consult before next steps.',
                                'Pt out of state for family emergency.'], c['key'], h)
                nid = note(h + 'note', start, 'clinician', f'Clinical note: follow-up review\n{context} {body}', hour=14)
                readings[nid] = {'role': 'clinician', 'date': start + 'T14:00:00Z', 'clauses': [],
                                 'hold': {'start': start, 'end': end, 'courses': [ref(k) for k in courses]}}
                continue
            r = add('Basic', h, start, code={'text': 'Review-clock pause'}, created=start)
            r['extension'] += [extension('pause-period', 'Period', {'start': start, 'end': end}), extension('pause-status', 'Code', 'active')] + \
                              [extension('course', 'Reference', {'reference': 'MedicationRequest/' + ref(k)}) for k in courses]

        for key, day, value in [('base', '2025-12-01', 4), ('marker', '2025-12-10', 8), ('marker2', '2025-12-12', 8)]:
            specimen = add('Specimen', key + 'spec', day, status='available', collection={'collectedDateTime': day + 'T08:00:00Z'})
            add('Observation', key, day, status='final', code={'text': 'RPR'}, effectiveDateTime=day + 'T08:00:00Z', issued=day + 'T16:00:00Z',
                specimen={'reference': 'Specimen/' + specimen['id']}, valueInteger=value)
        plans = {}
        for k, sch, marker in zip('abc', c['schedules'], c.get('marker_for', ['marker', 'marker', 'marker2'])):
            (r0, r1), (a0, a1), separation = sch
            sep = pick([f'{separation // 7} weeks', f'{separation} days'], c['key'], k)
            base = fmt('2025-12-01', c['key'], k, 'b'); comp = fmt({'marker': '2025-12-10', 'marker2': '2025-12-12'}[marker], c['key'], k, 'c')
            text = pick([
                f'Follow-up serology: RPR at {r0} and {r1} months after completing the series. If the {comp} RPR titer is at least 4x the {base} baseline (and drawn after it), shorten to {a0} and {a1} months. Space follow-up draws at least {sep} apart.',
                f'Plan: repeat RPR {r0} mo / {r1} mo post-completion. Accelerate to {a0} mo / {a1} mo only if comparison RPR ({comp}) is >= fourfold the baseline RPR ({base}) and was drawn later. Min. {sep} between follow-up draws.',
                f'RPR checkpoints {r0} & {r1} months from series completion; accelerated schedule {a0} & {a1} months applies when the {comp} titer is at least 4x the {base} titer from an earlier draw. Follow-up draws must be at least {sep} apart.'], c['key'], k)
            entered = c['starts']['abc'.index(k)]
            r = add('ServiceRequest', 'p' + k, entered, status='active', intent='plan', code={'text': 'Serial RPR follow-up'},
                    authoredOn=entered + 'T11:00:00Z', supportingInfo=[{'reference': 'MedicationRequest/' + ref(k)}], note=[{'text': text}])
            reading = {'baseline': ref('base'), 'comparison': ref(marker), 'routine': [r0, r1], 'accelerated': [a0, a1], 'separation': separation}
            plans[r['id']] = reading
            if c.get('extra_plan') and k == 'a':
                for label, prev in [('pa2', 'pa'), ('pa3', 'pa2')]:
                    v = json.loads(json.dumps(r)); v['id'] = ref(label); v['authoredOn'] = case.plan_entered[label] + 'T11:00:00Z'
                    v['extension'][0] = extension('event-time', 'DateTime', case.plan_entered[label] + 'T08:00:00Z')
                    v['extension'].append(extension('replaces', 'Reference', {'reference': 'ServiceRequest/' + ref(prev)}))
                    sources.append(v); plans[v['id']] = reading

        for key, day, courses in c['labs']:
            r = add('Specimen', key, day, status='available', collection={'collectedDateTime': day + 'T08:00:00Z'})
            r['extension'] += [extension('course', 'Reference', {'reference': 'MedicationRequest/' + ref(k)}) for k in courses]
            issued = '2026-06-08T16:00:00Z' if c['key'] == 'meadow' and key == 's1' else day + 'T16:00:00Z'
            add('Observation', key + 'obs', day, status='final', code={'text': 'RPR'}, effectiveDateTime=day + 'T08:00:00Z', issued=issued,
                specimen={'reference': 'Specimen/' + ref(key)}, valueInteger=8)
            if key in c.get('duplicates', []):
                add('Observation', key + 'copy', day, status='final', code={'text': 'RPR'}, effectiveDateTime=day + 'T08:00:00Z', issued=issued,
                    specimen={'reference': 'Specimen/' + ref(key)}, valueInteger=8, note=[{'text': 'Duplicate report sent by reference lab interface.'}])

        # Corrections and retractions as free text. note_meta keeps what each note corrected so later
        # retractions can describe it in words.
        edits = {key: (role, clauses) for key, role, clauses in c['edits']}
        dates = {key: plus('2026-09-02', j * 2) for j, (key, _, _) in enumerate(c['edits'])}
        untouched = [f'{k}{i}' for k in 'abc' for i in range(1, len(c['days']['abc'.index(k)]) + 1) if f'{k}{i}' not in amended]
        for j, (key, role, clauses) in enumerate(c['edits']):
            lines, parsed = [], []
            for i, (target, field, value) in enumerate(clauses, 1):
                seed = (c['key'], key, i)
                if target == 'withdraw':
                    inner_key, inner_num = field, int(value)
                    inner_role, inner = edits[inner_key]
                    t, f, v = inner[inner_num - 1]
                    prior = f'{pick(NAMES[inner_role], c["key"], inner_key)}\'s {fmt(dates[inner_key], *seed)} note'
                    if t == 'withdraw':
                        tt, tf, _ = edits[f][1][int(v) - 1]
                        what = f'the retraction in {prior} (of {case.describe(tt, tf, *seed)})'
                    else:
                        what = f'{case.describe(t, f, *seed)} in {prior}'
                    lines.append(pick([f'Please disregard {what}; it was entered in error. The rest of that note stands.',
                                       f'Retracting {what}.'], *seed))
                    parsed.append((i, 'withdraw', ref(inner_key), inner_num, None))
                else:
                    lines.append(case.statement(role, target, field, value, *seed))
                    stored = value
                    if field == 'course': stored = ref(value)
                    if field == 'courses': stored = ','.join(ref(k) for k in value)
                    tid = ref({'marker': 'marker', 'marker2': 'marker2', 'base': 'base'}.get(target, target))
                    parsed.append((i, 'set', tid, field, str(stored)))
            head = {'clinician': pick(['Addendum', 'Clinical note: chart correction', 'Progress note addendum'], c['key'], key),
                    'laboratory': pick(['Laboratory correction notice', 'Lab QA notice'], c['key'], key),
                    'nurse': pick(['Nursing note', 'Nurse follow-up note'], c['key'], key)}[role]
            filler = pick({'clinician': ['Chart reviewed with pharmacy.', 'Pt doing well, no rash or new sx.', 'Discussed with pt by phone.'],
                           'laboratory': ['Accession reviewed by supervisor.', 'Questions: call the lab.'],
                           'nurse': ['Pt called with questions about next appt.', 'Reminder letter mailed.']}[role], c['key'], key)
            body = lines if len(lines) == 1 else [f'- {x}' for x in lines]
            extra = []
            if role == 'clinician' and untouched and pick([0, 1], c['key'], key, 'confirm'):
                extra = [f'{case.injection(pick(untouched, c["key"], key), c["key"], key, "c")[0].upper()}{case.injection(pick(untouched, c["key"], key), c["key"], key, "c")[1:]} is correct as charted.']
            text = '\n'.join([head, filler] + body + extra)
            nid = note(key, dates[key], role, text)
            readings[nid] = {'role': role, 'date': dates[key] + 'T10:00:00Z', 'clauses': parsed}

        # An unauthorized hold look-alike and ordinary notes that change nothing.
        gold_b = c['gold'][1]
        if ci % 2 == 0 and gold_b[3]:
            s, e = plus(gold_b[3], 20), plus(gold_b[3], 31)
            nid = note('rnhold', plus(gold_b[3], 19), 'nurse',
                       f'Nursing note\nPt traveling {fmt(s, "rn")} to {fmt(plus(e, -1), "rn2")}; holding follow-up clock for {case.series("b", "rn")} while away.', hour=15)
            readings[nid] = {'role': 'nurse', 'date': plus(gold_b[3], 19) + 'T15:00:00Z', 'clauses': [],
                             'hold': {'start': s, 'end': e, 'courses': [ref('b')]}}
        for j in range(ci % 3 + 1):
            text = ['Telephone contact details confirmed.', 'Prescription pickup confirmed by pt.', 'Records received from referring clinic; reviewed, no changes.'][j]
            role = ['nurse', 'nurse', 'clinician'][j]
            nid = note('routine' + str(j), plus('2026-08-21', j * 3), role, text, hour=15)
            readings[nid] = {'role': role, 'date': plus('2026-08-21', j * 3) + 'T15:00:00Z', 'clauses': []}

        # Golden rows exactly as qa/build_graph.py computes them.
        rows = {}; labfacts = {}
        for key, day, courses in c['labs']:
            effective = {'date': day, 'courses': courses, 'status': 'available', **c.get('effective_labs', {}).get(key, {})}
            for suffix in ['obs'] + (['copy'] if key in c.get('duplicates', []) else []):
                labfacts[ref(key + suffix)] = {'specimen': ref(key), 'date': effective['date'], 'courses': [ref(k) for k in effective['courses']],
                                               'eligible': effective['status'] == 'available' and day < '2026-09-24'}
        for k, g, sch in zip('abc', c['gold'], c['schedules']):
            plan, branch, doses, anchor, months, holds = g
            for idx, checkpoint in enumerate(('first', 'second')):
                unavailable = plan in ('unclear', 'no_requirement')
                due, paused = golden_due(anchor, months[idx], holds) if anchor else (None, None)
                rows[eps[k] + ':' + checkpoint] = {'episode': eps[k], 'checkpoint': checkpoint, 'plan': ref(plan) if not unavailable else None,
                    'course': ref(k) if not unavailable else None, 'branch': branch, 'doses': [ref(d) for d in doses],
                    'completion_date': anchor, 'due_date': due, 'paused_days': paused, 'fixed_status': plan if unavailable else None, 'separation': sch[2]}
        expected[pid] = {'rows': rows, 'reports': labfacts, 'optimum': c['optimum']}
        readings.update({f'plan:{k}': v for k, v in plans.items()})
    sources.sort(key=lambda r: r['id'])
    for r in sources: validate(r)
    assert len(sources) == len({r['id'] for r in sources})
    return {'version': VERSION, 'evaluation_time': NOW, 'targets': targets, 'sources': sources}, expected, readings


def main():
    fixture, expected, readings = build()
    (TASK / 'environment/service/fixture.json').write_text(json.dumps(fixture, indent=2) + '\n')
    (TASK / 'tests/expected.json').write_text(json.dumps(expected, indent=2) + '\n')
    (TASK / 'solution/readings.json').write_text(json.dumps(readings, indent=2) + '\n')
    (TASK / 'tests/baseline.json').write_text(json.dumps({'version': VERSION, 'evaluation_time': NOW, 'initial_digest': digest(fixture),
                                                          'sources_digest': digest(fixture['sources'])}, indent=2) + '\n')
    print('Built', len(expected), 'patients;', len(fixture['sources']), 'resources;', sum(len(x['rows']) for x in expected.values()), 'determinations')


if __name__ == '__main__':
    main()
