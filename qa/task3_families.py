"""Task 3 generated case families and background patients (PRIVATE).

Weighted heavily toward *chained* cases, where the status of one fact (an identity conflict, a correction, an
outside record, a pending test, a misfiled result) must be carried into a different issue or a different patient.
Every instance declares its intended dispositions (`truth`); qa/build_task3.py refuses to build unless
qa/task3_rules.py recomputes exactly those from the instance's facts. Surface details (names, dates, stages, staff,
phrasing, noise) vary per instance; outcome variants of each family point in both directions.
"""
import calendar
import datetime as dt
import hashlib
import random

from task3_cases import EVAL, ADQ, FUP, MIS, PRG, PEND, OUT, CONF, DR, RN, PHARM, PATIENTS as CORE

SEED = 20260927
D = dt.date.fromisoformat
EVALD = D(EVAL)
CLIN = DR + ['Dr. Hana Ito', 'Dr. Marcus Lee', 'Dr. Priya Raman', 'Dr. Owen Hart', 'Dr. Julia Brandt']
NURSES = RN + ['Lena Park, RN', 'Diego Santos, RN', 'Ruth Adeyemi, RN', 'Chris Novak, LPN', 'Amara Diallo, RN']
LABTECH = ['R. Chen, MLS', 'M. Ortiz, MLS', 'K. Dube, MLT', 'S. Walsh, MLS', 'J. Ferris, MLT']
EDS = ['Mercy General Emergency Department', "St. Luke's Emergency Department", 'Riverside Hospital ED',
       'Northgate Urgent Care', 'Valley Medical Center ED']
CLINICS = ['Eastside Community Health', 'County Health STD Clinic', 'Maple Family Medicine', 'Harbor Street Clinic',
           'Lakeview Health Center', 'Westbrook Family Practice']
HOSPITALS = ['Riverside Hospital', 'Mercy General', "St. Luke's Hospital", "Northgate Women's Hospital", 'Valley Medical Center']
FEMALE = ['Amelia', 'Beatriz', 'Chloe', 'Daniela', 'Elena', 'Fatima', 'Gabriela', 'Hope', 'Iris', 'Jade', 'Kayla', 'Leah',
          'Monique', 'Naomi', 'Opal', 'Paige', 'Quinn', 'Rosa', 'Sofia', 'Tanya', 'Uma', 'Valerie', 'Wendy', 'Ximena',
          'Yara', 'Zoe', 'Alicia', 'Brenda', 'Carmen', 'Dominique', 'Erin', 'Farah', 'Grace', 'Holly', 'Ingrid', 'Janelle',
          'Kiara', 'Lorena', 'Maya', 'Nia', 'Olga', 'Priscilla', 'Renata', 'Sasha', 'Tiana', 'Vanessa', 'Whitney', 'Yvette',
          'Adriana', 'Bianca', 'Celeste', 'Destiny', 'Esther', 'Flor', 'Gloria', 'Hazel', 'Imogen', 'Joy', 'Kendra', 'Lila']
MALE = ['Aaron', 'Brandon', 'Carlos', 'Dmitri', 'Emmanuel', 'Felix', 'Gavin', 'Hector', 'Isaac', 'Jamal', 'Kenji', 'Luis',
        'Mateo', 'Nathan', 'Omar', 'Patrick', 'Rafael', 'Simon', 'Trevor', 'Ulises', 'Vincent', 'Wesley', 'Xavier', 'Yusuf',
        'Zachary', 'Andre', 'Bruno', 'Cedric', 'Darnell', 'Eli', 'Francisco', 'Gordon', 'Hugo', 'Ivan', 'Jorge', 'Kofi',
        'Leon', 'Malik', 'Nolan', 'Oscar', 'Pablo', 'Reggie', 'Stefan', 'Tomas', 'Victor', 'Warren', 'Yosef', 'Zane',
        'Abdul', 'Blake', 'Colin', 'Dante', 'Everett', 'Frank', 'Graham', 'Hassan', 'Ian', 'Jonah', 'Kai', 'Lamar']
LAST = ['Abbott', 'Baptiste', 'Caldwell', 'Delgado', 'Ellison', 'Fontaine', 'Gutierrez', 'Hollis', 'Iyer', 'Jennings',
        'Kowalski', 'Lindgren', 'Mbeki', 'Navarro', "O'Neill", 'Pham', 'Quintero', 'Rasmussen', 'Soto', 'Tanaka',
        'Underwood', 'Vasquez', 'Whitaker', 'Yilmaz', 'Zimmer', 'Acosta', 'Bergstrom', 'Chowdhury', 'Dalton', 'Espinoza',
        'Farrow', 'Garrison', 'Haddad', 'Ibarra', 'Jovanovic', 'Kearney', 'Lozano', 'Mendoza', 'Nakagawa', 'Okonkwo',
        'Petrakis', 'Rinaldi', 'Sandoval', 'Thibodeaux', 'Umeh', 'Varga', 'Wainwright', 'Yamamoto', 'Zeller', 'Alvarado',
        'Bishop', 'Cruz', 'Dubois', 'Eriksen', 'Figueroa', 'Gallagher', 'Hwangbo', 'Ivanova', 'Jaramillo', 'Kline',
        'Lachance', 'Moreno', 'Nwosu', 'Orozco', 'Pellegrini', 'Reyna', 'Sokolov', 'Tran', 'Villanueva', 'Webber',
        'Adler', 'Barrios', 'Castellanos', 'Donovan', 'Echols', 'Fujita', 'Grimes', 'Holloway', 'Ingram', 'Jeter']
STAGE_TEXT = {'primary': ['Primary syphilis'], 'secondary': ['Secondary syphilis'],
              'early_latent': ['Early latent syphilis'], 'late_latent': ['Late latent syphilis', 'Latent syphilis, unknown duration']}
TITER = {'primary': [16, 32, 64], 'secondary': [32, 64, 128, 256], 'early_latent': [4, 8, 16, 32], 'late_latent': [1, 2, 4, 8]}


def iso(d):
    return d.isoformat()


def plus(day, n):
    return iso(D(day) + dt.timedelta(days=n))


def months(day, n):
    d = D(day)
    ix = d.year * 12 + d.month - 1 + n
    y, m = divmod(ix, 12)
    return iso(dt.date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1])))


def schedule(stage):
    return (6, 12) if stage in ('primary', 'secondary') else (6, 12, 24)


def window(anchor, m):
    due = months(anchor, m)
    return due, plus(due, -30), plus(due, 30)


def inside(g, lo, hi, margin=5):
    """A date at least `margin` days inside [lo, hi]: no answer may rest on whether a window edge is inclusive, or on
    how a month is added to a month-end date (Aug 31 + 6 months is Feb 28 or Mar 3)."""
    assert D(plus(lo, margin)) <= D(plus(hi, -margin)), (lo, hi)
    return g.date_between(plus(lo, margin), plus(hi, -margin))


def closed(anchor, m):
    return D(window(anchor, m)[2]) < EVALD


def mdy(day, style):
    d = D(day)
    return [f'{d.month}/{d.day}/{d.year % 100:02d}', f'{d.month}/{d.day}/{d.year}', d.strftime('%b %-d, %Y'),
            d.isoformat()][style % 4]


class Gen:
    def __init__(self, seed=SEED):
        self.rng = random.Random(seed)
        self.used = {p['name'] for p in CORE}
        self.externals = {}
        self.n = 0

    def pick(self, seq):
        return seq[self.rng.randrange(len(seq))]

    def name(self, sex):
        for _ in range(1000):
            n = self.pick(FEMALE if sex == 'female' else MALE) + ' ' + self.pick(LAST)
            if n not in self.used:
                self.used.add(n)
                return n
        raise RuntimeError('name pool exhausted')

    def date_between(self, lo, hi):
        a, b = D(lo), D(hi)
        return iso(a + dt.timedelta(days=self.rng.randint(0, max(0, (b - a).days))))

    def external(self, sex=None, reproductive=False):
        """A non-cohort clinic patient named only by one laboratory accessioning entry."""
        sex = sex or self.pick(['female', 'male'])
        name = self.name(sex)
        first, last = name.split(' ', 1)
        key = f'X{len(self.externals) + 1:03d}'
        mrn = str(int(hashlib.sha256(('ext:' + key).encode()).hexdigest()[:10], 16) % 90000000 + 10000000)
        dob = self.date_between('1983-01-01', '2006-12-31') if reproductive else self.date_between('1960-01-01', '2003-12-31')
        self.externals[key] = {'mrn': mrn, 'dob': dob, 'name': f'{last.upper()}, {first.upper()}'}
        return key


class Chart:
    def __init__(self, g, family, variant, sex=None, dx=None, age=(19, 62)):
        g.n += 1
        self.g, self.family, self.variant = g, family, variant
        self.key = f'g{g.n:03d}'
        self.sex = sex or g.pick(['female', 'male'])
        self.name = g.name(self.sex)
        self.dob = g.date_between(plus(EVAL, -365 * age[1]), plus(EVAL, -365 * age[0]))
        self.dx = dx
        self.records, self.facts, self.truth, self.kinds = [], {}, {}, {}
        self.requests, self.gaps, self.wrong, self.unknown = {}, {}, {}, None
        self.style = g.rng.randrange(4)

    @property
    def label(self):
        first, last = self.name.split(' ', 1)
        return f'{last.upper()}, {first.upper()}'

    def d(self, day):
        return mdy(day, self.style)

    def note(self, day, role, author, doc_type, text, hhmm=None):
        self.records.append(('note', day, hhmm or self.g.pick(['0845', '0930', '1015', '1110', '1340', '1425', '1530']),
                             role, author, doc_type, text))

    def rpr(self, day, titer, **opts):
        self.records.append(('rpr', day, titer if titer is None or titer == 'NR' else f'1:{titer}', opts))

    def patient(self):
        out = dict(key=self.key, name=self.name, sex=self.sex, dob=self.dob, dx=self.dx, records=self.records,
                   facts=self.facts, truth=self.truth, kinds=self.kinds, requests=self.requests, gaps=self.gaps,
                   wrong=self.wrong, family=self.family, variant=self.variant)
        if self.unknown:
            out['unknown'] = self.unknown
        return out


# ------------------------------------------------------------------------------------------------ building blocks

def diagnose(c, stage, clinician=None, pregnant_test=True, evidence=True):
    """Diagnostic labs, staging entry and intake note for an episode diagnosed on c.dx."""
    g, dx = c.g, c.dx
    doc = clinician or g.pick(CLIN)
    titer = g.pick(TITER[stage])
    c.titer = titer
    if stage == 'early_latent' and evidence:
        if g.rng.random() < 0.6:
            prior = plus(dx, -g.rng.randint(90, 300))
            c.rpr(prior, 'NR')
            why = g.pick([f'RPR nonreactive here {c.d(prior)}', f'neg RPR {c.d(prior)} at this clinic',
                          f'last RPR {c.d(prior)} was nonreactive'])
        else:
            why = g.pick(['partner treated for primary syphilis last month', 'named as a contact of a partner with secondary syphilis this spring'])
    c.records.append(('trep', dx, 'reactive'))
    c.rpr(dx, titer)
    if c.sex == 'female' and pregnant_test and 17 < (EVALD - D(c.dob)).days / 365 < 50:
        c.records.append(('hcg', dx, 'negative', {}))
    text = {
        'primary': g.pick(['Painless ulcer x {} days, indurated, clean base. RPR 1:{}, TP-PA reactive. Primary syphilis.',
                           'Chancre noted on exam, present ~{} days. RPR 1:{} reactive, treponemal reactive. Dx primary syphilis.']),
        'secondary': g.pick(['Rash x {} days incl. palms and soles, mucous patches. RPR 1:{}, TP-PA +. Secondary syphilis.',
                             'Diffuse papulosquamous rash for {} days, involving palms; condylomata lata. RPR 1:{}. Secondary syphilis.']),
        'early_latent': g.pick(['Asymptomatic; exam without lesions or rash. {}. RPR 1:{} now, TP-PA reactive. Early latent syphilis.',
                                'No symptoms, normal exam. {} -> infection within the past year. RPR 1:{}. Early latent.']),
        'late_latent': g.pick(['Asymptomatic, exam normal. No prior syphilis testing available and no known exposure in the past year. '
                               'RPR 1:{}, TP-PA reactive. Latent syphilis, duration unknown.',
                               'Screen-positive, no signs or symptoms. Unable to date infection (no prior tests on file). RPR 1:{}. '
                               'Treating as late latent.'])}[stage]
    if stage in ('primary', 'secondary'):
        text = text.format(g.rng.randint(5, 25), titer)
    elif stage == 'early_latent':
        text = text.format(why if evidence else 'Recent exposure documented', titer)
    else:
        text = text.format(titer)
    c.note(dx, 'clinician', doc, g.pick(['Progress note', 'New patient visit', 'STI clinic visit']), text)
    c.records.append(('condition', dx, g.pick(STAGE_TEXT[stage]), doc))
    c.facts['stage'] = stage
    return doc


def give(c, day, nurse=None, dose='2.4 million units IM'):
    nurse = nurse or c.g.pick(NURSES)
    site = c.g.pick(['R gluteal', 'L gluteal', 'R ventrogluteal', 'L ventrogluteal'])
    c.records.append(('bpg', day, dose, nurse, c.g.pick([f'{site}. Tolerated.', f'{site}, observed 15 min.', f'{site}.'])))
    return nurse


def treat(c, stage, start, gaps=None):
    if stage in ('primary', 'secondary', 'early_latent'):
        give(c, start)
        return [start]
    gaps = gaps or [c.g.pick([7, 7, 8]), c.g.pick([7, 7, 8, 9])]
    days = [start, plus(start, gaps[0]), plus(start, gaps[0] + gaps[1])]
    nurse = c.g.pick(NURSES)
    for i, day in enumerate(days, 1):
        give(c, day, nurse)
    return days


def followups(c, anchor, stage, skip=(), open_extra=0.3):
    """Own follow-up RPRs inside every closed window except `skip`; returns {month: (due, lo, hi)}."""
    g, out = c.g, {}
    titer = max(1, getattr(c, 'titer', 8) // 4)
    for m in schedule(stage):
        due, lo, hi = window(anchor, m)
        out[m] = (due, lo, hi)
        if D(hi) < EVALD + dt.timedelta(days=5):   # windows closing near the evaluation time are filled, never left ambiguous
            if m not in skip:
                day = plus(due, g.rng.randint(-18, 18))
                # Nonreactive only at the last scheduled test: no answer may rest on a test missed after seroreversion.
                c.rpr(day, titer if titer > 1 else (lambda v: v if m == schedule(stage)[-1] else 1)(g.pick([1, 'NR'])))
                titer = max(1, titer // 2)
        elif D(lo) < EVALD - dt.timedelta(days=10) and m not in skip and g.rng.random() < open_extra:
            c.rpr(g.date_between(lo, plus(EVAL, -4)), max(1, titer))
    return out


def noise(c, n=None):
    g = c.g
    for _ in range(g.rng.randint(0, 3) if n is None else n):
        day = g.date_between(plus(c.dx, -200), plus(EVAL, -5))
        kind = g.rng.randrange(5)
        if kind == 0:
            c.records.append(('lab', day, 'HIV-1/2 Ag/Ab', 'Nonreactive'))
        elif kind == 1:
            c.records.append(('lab', day, 'Chlamydia/Gonorrhea NAAT', 'Not detected'))
        elif kind == 2:
            c.note(day, 'nurse', g.pick(NURSES), 'Nursing note', g.pick(
                ['BP {}/{}. No complaints.'.format(g.rng.randint(110, 145), g.rng.randint(68, 92)),
                 'Portal message: requested work note; sent.', 'Flu vaccine given, L deltoid.',
                 'Pt called to confirm appointment time.']))
        elif kind == 3:
            c.note(day, 'clinician', g.pick(CLIN), 'Telephone encounter', g.pick(
                ['Discussed PrEP; pt will think about it.', 'Refill of lisinopril sent.', 'Reviewed lipid panel; diet counseling.']))
        else:
            c.records.append(('lab', day, 'Hepatitis C antibody', 'Nonreactive'))


def expect(c, **issues):
    """Declare intended non-silent dispositions: expect(c, FUP=('cannot_determine', CONF))."""
    names = {'ADQ': ADQ, 'FUP': FUP, 'MIS': MIS, 'PRG': PRG}
    for k, v in issues.items():
        c.truth[names[k]] = v


def kind(c, **issues):
    names = {'ADQ': ADQ, 'FUP': FUP, 'MIS': MIS, 'PRG': PRG}
    for k, v in issues.items():
        c.kinds[names[k]] = v


def request(c, issue, text):
    c.requests[issue] = text


REQ = {ADQ: ['Pharmacy QA: please review whether treatment for this episode is complete.',
             'Quality report: treatment course may not match the documented stage. Please review.'],
       FUP: ['Quality report: follow-up RPR may be overdue. Please review.',
             'Registry audit: follow-up serology not found for a due interval. Please review.'],
       MIS: ['Laboratory QA: possible identification discrepancy on a result in this chart. Please review.',
             'Laboratory QA: specimen identifiers flagged at accessioning. Please review.'],
       PRG: ['Perinatal QA: confirm whether maternal syphilis treatment was adequate for this pregnancy.',
             'Congenital syphilis prevention review: please confirm maternal treatment adequacy.']}


def anchor_for(g, months_needed, open_month=None):
    """A first-dose date whose `months_needed` checkpoint windows are all closed (and `open_month` open)."""
    latest = D(months(plus(EVAL, -40), -max(months_needed)))
    earliest = max(D('2023-10-01'), latest - dt.timedelta(days=260))
    if open_month:
        lo = D(months(plus(EVAL, 5), -open_month))            # window end >= EVAL
        hi = D(months(plus(EVAL, 22), -open_month))           # window start < EVAL - some days
        latest = min(latest, hi)
        earliest = max(earliest, lo)
    assert earliest <= latest, (months_needed, open_month)
    return g.date_between(iso(earliest), iso(latest))


# ------------------------------------------------------------------------------------------------ chained families

def f1_identity_conflict(g, variant):
    """Collection label says this patient; laboratory accessioning says someone else."""
    stage = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
    target = g.pick(schedule(stage))
    first = anchor_for(g, [target]) if variant != 'c' else anchor_for(g, [6], open_month=12)
    if variant == 'c':
        target = 12
    c = Chart(g, 'F1_identity_conflict', variant, dx=first)
    diagnose(c, stage)
    treat(c, stage, first)
    due, lo, hi = window(first, target)
    if variant == 'c':    # open window: collected inside it but before the evaluation time
        conflict = g.date_between(lo, plus(EVAL, -4))       # window start is at least 8 days before evaluation
    else:
        conflict = g.date_between(plus(due, -18), min(plus(due, 18), plus(EVAL, -4)))
    skip = (target,) if variant in ('a', 'e', 'f', 'c') else ()
    followups(c, first, stage, skip=skip, open_extra=0.0)
    collector = g.pick(NURSES)
    accessioner = g.pick(LABTECH)
    partner = None
    if variant == 'f':
        partner = Chart(g, 'F1_identity_conflict', 'f-partner')
        other = partner.key
    else:
        other = g.external()
    c.rpr(conflict, max(1, c.titer // 8) if c.titer > 4 else 'NR', accession_owner=other, collector=collector,
          accessioner=accessioner)
    if variant == 'b':
        # A second, correctly identified specimen in the same window.
        own = conflict
        while abs((D(own) - D(conflict)).days) < 6:
            own = g.date_between(lo, min(hi, plus(EVAL, -4)))
        c.rpr(own, max(1, c.titer // 8))
    c.gaps['conflict'] = (MIS, FUP)
    if variant in ('a', 'f', 'c', 'b'):
        c.unknown = dict(code=CONF, kind='conflict', best='self', latest='other', chart='self',
                         options={'self': {}, 'other': dict(fu_drop=[conflict], misfiled=True)})
        expect(c, MIS=('cannot_determine', CONF))
        if variant in ('a', 'f'):
            expect(c, FUP=('cannot_determine', CONF))
            kind(c, MIS='undeterminable', FUP='chain')
        else:
            kind(c, MIS='undeterminable', FUP='chain_irrelevant')
    elif variant == 'd':
        c.note(plus(conflict, g.rng.randint(1, 6)), 'laboratory', accessioner, 'Laboratory correction', g.pick([
            f'Accessioning correction: the RPR specimen received {c.d(conflict)} was logged under the wrong patient in the '
            f'receiving system. Correct patient per tube label: {c.label}, MRN on file, DOB {c.d(c.dob)}. Entry corrected.',
            f'Correction to my accessioning entry for the {c.d(conflict)} RPR: registered to the wrong MRN at receipt. '
            f'Specimen belongs to {c.label} (DOB {c.d(c.dob)}).']), '1500')
        c.wrong['structured_only'] = dict(fu_drop=[conflict], misfiled=True)
        kind(c, MIS='nonissue', FUP='chain_irrelevant')
    elif variant == 'e':
        who = g.externals[other]
        c.note(plus(conflict, g.rng.randint(1, 5)), 'nurse', collector, 'Nursing note - correction', g.pick([
            f'Correction to my collection record for the {c.d(conflict)} RPR draw: labels printed for this patient were used '
            f'on a tube drawn from another patient ({who["name"]}, DOB {c.d(who["dob"])}). This patient was not drawn that day.',
            f'Late entry/correction: the RPR tube I labeled on {c.d(conflict)} with this patient\'s label was actually drawn '
            f'from {who["name"]} (DOB {c.d(who["dob"])}). Documentation error on my part.']), '1600')
        c.facts.update(fu_drop=[conflict], misfiled=True)
        c.wrong['structured_only'] = dict(fu_drop=[], misfiled=False)
        expect(c, MIS=('confirmed', None), FUP=('confirmed', None))
        kind(c, MIS='chain', FUP='chain')
    noise(c)
    out = [c]
    if partner:
        # The accessioning entry names a cohort patient whose own window contains the collection date.
        pstage = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
        pm = g.pick(schedule(pstage))
        pfirst = months(plus(conflict, g.rng.randint(-12, 12)), -pm)
        partner.dx = pfirst
        diagnose(partner, pstage)
        treat(partner, pstage, pfirst)
        followups(partner, pfirst, pstage, skip=(pm,), open_extra=0.0)
        noise(partner)
        partner.unknown = dict(code=CONF, kind='conflict', best='not', latest='mine', chart='not',
                               options={'mine': dict(extra_fu=[(conflict, 'final')]), 'not': {}})
        partner.gaps['conflict'] = (FUP,)
        expect(partner, FUP=('cannot_determine', CONF))
        kind(partner, FUP='chain_cross')
        out.append(partner)
    return out


def f2_resolved_misfile(g, variant):
    """A result filed in A's chart whose specimen was labeled and accessioned for cohort patient B."""
    sa = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
    ma = g.pick(schedule(sa))
    afirst = anchor_for(g, [ma])
    a = Chart(g, 'F2_resolved_misfile', variant, dx=afirst)
    diagnose(a, sa)
    treat(a, sa, afirst)
    due, lo, hi = window(afirst, ma)
    day = g.date_between(plus(due, -18), min(plus(due, 18), plus(EVAL, -4)))
    followups(a, afirst, sa, skip=() if variant == 'b' else (ma,), open_extra=0.0)
    b = Chart(g, 'F2_resolved_misfile', variant + '-owner')
    sb = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
    mb = g.pick(schedule(sb))
    if variant in ('a', 'b'):
        bfirst = months(plus(day, g.rng.randint(-15, 15)), -mb)          # day inside B's window
        bskip = (mb,)
    elif variant == 'c':
        bfirst = months(plus(day, g.rng.randint(80, 140)), -mb)         # day in none of B's windows
        bskip = ()
    else:
        bfirst = months(plus(day, -g.rng.randint(36, 50)), -mb)         # day just after B's window closes
        bskip = (mb,)
    b.dx = bfirst
    diagnose(b, sb)
    treat(b, sb, bfirst)
    followups(b, bfirst, sb, skip=bskip, open_extra=0.0)
    a.rpr(day, max(1, b.titer // 8) if b.titer > 4 else 'NR', owner=b.key, collector=g.pick(NURSES))
    if g.rng.random() < 0.6:
        b.note(day, 'nurse', g.pick(NURSES), 'Nursing note', g.pick(['Here for follow-up labs; RPR drawn.',
                                                                   'Lab visit: RPR drawn, tolerated well.', 'Follow-up RPR drawn today.']))
    for x in (a, b):
        noise(x)
    expect(a, MIS=('confirmed', None))
    kind(a, MIS='real')
    if variant == 'b':
        kind(a, FUP='chain_irrelevant')
    else:
        expect(a, FUP=('confirmed', None))
        kind(a, FUP='chain')
    if variant == 'd':
        expect(b, FUP=('confirmed', None))
        kind(b, FUP='chain_cross')
    else:
        kind(b, FUP='chain_cross' if variant in ('a', 'b') else 'control')
    return [a, b]


def f4_pending_pregnancy(g, variant):
    """A pregnancy test with no final result, and treatment whose adequacy may or may not depend on it."""
    c = Chart(g, 'F4_pending_pregnancy', variant, sex='female', age=(18, 40))
    if variant == 'doxy':
        c.dx = g.date_between(plus(EVAL, -44), plus(EVAL, -32))
        c.records.append(('allergy', plus(c.dx, -g.rng.randint(400, 3000)), 'Penicillin',
                          g.pick(['Anaphylaxis after amoxicillin.', 'Hives and throat tightness with penicillin as a child; ED visit.'])))
        diagnose(c, 'early_latent', pregnant_test=False)
        c.records.append(('hcg', c.dx, None, {'comment': g.pick(['Specimen forwarded to reference laboratory.', 'Result to follow.'])}))
        c.records.append(('dispense', c.dx, 'Doxycycline hyclate 100 mg capsule', 28, 14,
                          'Take 1 capsule by mouth twice daily for 14 days', ''))
        c.note(c.dx, 'clinician', g.pick(CLIN), 'Progress note', g.pick([
            'Severe PCN allergy. Doxycycline x 14 d. LMP uncertain; serum hCG sent.',
            'PCN anaphylaxis history - doxycycline 100 BID x14 days. Pregnancy test sent, pt unsure of LMP.']))
        c.facts['allergy'] = True
        expect(c, ADQ=('cannot_determine', PEND), PRG=('cannot_determine', PEND))
        kind(c, ADQ='chain', PRG='undeterminable')
    elif variant == 'late1':
        c.dx = g.date_between(plus(EVAL, -120), plus(EVAL, -45))
        diagnose(c, 'late_latent')
        give(c, c.dx)
        for k in (7, 14):
            c.note(plus(c.dx, k + 1), 'nurse', g.pick(NURSES), 'Telephone encounter', g.pick(
                [f'No show for Bicillin #{k // 7 + 1}. VM left.', f'Missed injection #{k // 7 + 1}; unable to reach.']))
        later = g.date_between(plus(EVAL, -21), plus(EVAL, -4))
        c.note(later, 'clinician', g.pick(CLIN), 'Progress note', g.pick([
            'Back after missed injections. Reports late period; serum hCG sent. Will restart series.',
            'Returns to care. Possible pregnancy (LMP ~6 wks). Quantitative hCG sent; restart Bicillin when back.']))
        c.records.append(('hcg', later, None, {'comment': 'In process.'}))
        expect(c, ADQ=('confirmed', None), PRG=('cannot_determine', PEND))
        kind(c, ADQ='chain_irrelevant', PRG='undeterminable')
    elif variant == 'early1':
        c.dx = g.date_between(plus(EVAL, -44), plus(EVAL, -32))
        diagnose(c, g.pick(['primary', 'secondary', 'early_latent']), pregnant_test=False)
        give(c, c.dx)
        c.records.append(('hcg', c.dx, None, {'comment': g.pick(['Result to follow.', 'Sent out.'])}))
        kind(c, ADQ='chain_irrelevant', PRG='chain_irrelevant')
    else:  # late3: a correctly spaced series; adequate whether or not she is pregnant
        c.dx = g.date_between(plus(EVAL, -44), plus(EVAL, -32))
        diagnose(c, 'late_latent', pregnant_test=False)
        treat(c, 'late_latent', c.dx, gaps=[7, 7])
        c.records.append(('hcg', c.dx, None, {'comment': 'Result to follow.'}))
        kind(c, ADQ='chain_irrelevant', PRG='chain_irrelevant')
    c.unknown = dict(code=PEND, kind='pending', best='not', negative='not', chart='not',
                     options={'pregnant': dict(pregnant=True), 'not': dict(pregnant=False)})
    c.gaps['pending_hcg'] = (ADQ, PRG)
    noise(c)
    return [c]


def f5_hcg_identity(g, variant):
    """A positive pregnancy test whose identity is resolved to, or disputed with, another cohort patient."""
    out = []
    a = Chart(g, 'F5_hcg_identity', variant, sex='female', age=(18, 40))
    a.dx = g.date_between(plus(EVAL, -150), plus(EVAL, -50))
    a_doxy = variant in ('misfile', 'conflict', 'conflict-bpg')
    if a_doxy:
        a.records.append(('allergy', plus(a.dx, -g.rng.randint(400, 3000)), 'Penicillin', g.pick(['Anaphylaxis.', 'Angioedema after penicillin.'])))
        diagnose(a, 'early_latent', pregnant_test=False)
        a.records.append(('dispense', a.dx, 'Doxycycline hyclate 100 mg capsule', 28, 14, 'Take 1 capsule by mouth twice daily for 14 days', ''))
        a.facts['allergy'] = True
    else:
        diagnose(a, g.pick(['primary', 'early_latent']), pregnant_test=False)
        give(a, a.dx)
    test_day = plus(a.dx, g.rng.randint(0, 20))
    b = None
    if variant in ('misfile', 'conflict', 'conflict-bpg'):
        b = Chart(g, 'F5_hcg_identity', variant + '-other', sex='female', age=(18, 40))
        b.dx = plus(test_day, -g.rng.randint(0, 10))      # positive test during treatment: pregnant while treated
        b_doxy = variant in ('misfile', 'conflict') and g.rng.random() < 0.8
        if b_doxy:
            b.records.append(('allergy', plus(b.dx, -g.rng.randint(400, 3000)), 'Penicillin', g.pick(['Anaphylaxis.', 'Hives, wheeze.'])))
            diagnose(b, 'early_latent', pregnant_test=False)
            b.records.append(('dispense', b.dx, 'Doxycycline hyclate 100 mg capsule', 28, 14, 'Take 1 capsule by mouth twice daily for 14 days', ''))
            b.facts['allergy'] = True
        else:
            diagnose(b, g.pick(['primary', 'secondary', 'early_latent']), pregnant_test=False)
            give(b, b.dx)
        if variant == 'misfile' and g.rng.random() < 0.5:   # in a conflict it would make RESULT_PENDING arguable
            b.note(test_day, 'nurse', g.pick(NURSES), 'Nursing note', g.pick(['Labs drawn incl. serum hCG.', 'hCG drawn per provider.']))
    if variant == 'misfile':
        a.records.append(('hcg', test_day, 'positive', {'owner': b.key}))
        a.facts['pregnant'] = False
        b.facts['pregnant'] = True
        a.wrong['per_patient'] = dict(pregnant=True)
        b.wrong['per_patient'] = dict(pregnant=False)
        expect(a, MIS=('confirmed', None))
        kind(a, MIS='real', ADQ='chain_cross', PRG='chain_cross')
        if b.facts.get('allergy'):
            expect(b, ADQ=('confirmed', None), PRG=('confirmed', None))
            kind(b, ADQ='chain_cross', PRG='chain_cross')
        else:
            kind(b, ADQ='chain_irrelevant', PRG='chain_irrelevant')
    elif variant in ('conflict', 'conflict-bpg'):
        a.records.append(('hcg', test_day, 'positive', {'accession_owner': b.key}))
        a.unknown = dict(code=CONF, kind='conflict', best='self', latest='other', chart='self',
                         options={'self': dict(pregnant=True), 'other': dict(pregnant=False, misfiled=True)})
        a.gaps['conflict'] = (MIS, ADQ, PRG)
        expect(a, MIS=('cannot_determine', CONF), ADQ=('cannot_determine', CONF), PRG=('cannot_determine', CONF))
        kind(a, MIS='undeterminable', ADQ='chain', PRG='chain')
        b.unknown = dict(code=CONF, kind='conflict', best='not', latest='mine', chart='not',
                         options={'mine': dict(pregnant=True), 'not': dict(pregnant=False)})
        b.gaps['conflict'] = (ADQ, PRG)
        if b.facts.get('allergy'):
            expect(b, ADQ=('cannot_determine', CONF), PRG=('cannot_determine', CONF))
            kind(b, ADQ='chain_cross', PRG='chain_cross')
        else:
            kind(b, ADQ='chain_irrelevant', PRG='chain_irrelevant')
    else:  # 'irrelevant': disputed test, but BPG treatment is adequate whether or not she is pregnant
        a.records.append(('hcg', test_day, 'positive', {'accession_owner': g.external('female', reproductive=True)}))
        a.unknown = dict(code=CONF, kind='conflict', best='self', latest='other', chart='self',
                         options={'self': dict(pregnant=True), 'other': dict(pregnant=False, misfiled=True)})
        a.gaps['conflict'] = (MIS, ADQ, PRG)
        expect(a, MIS=('cannot_determine', CONF))
        kind(a, MIS='undeterminable', ADQ='chain_irrelevant', PRG='chain_irrelevant')
    for x in (a, b):
        if x:
            noise(x)
            out.append(x)
    return out


def f6_correction(g, variant):
    """A dose date corrected by its author (or disputed by someone else) moves the follow-up anchor or a gap."""
    if variant in ('anchor-late', 'anchor-early', 'dispute'):
        stage = g.pick(['primary', 'secondary', 'early_latent'])
        charted = plus(anchor_for(g, [12]), -30)   # the other date is up to 28 days later: both 12-month windows closed
        c = Chart(g, 'F6_correction', variant, dx=charted)
        diagnose(c, stage)
        nurse = give(c, charted)
        shift = g.rng.randint(20, 28)
        actual = plus(charted, shift) if variant != 'anchor-early' else plus(charted, -shift)
        if variant == 'anchor-early':
            c.dx = plus(actual, -g.rng.randint(0, 3))
            c.records = [r if r[1] != charted or r[0] not in ('trep', 'rpr', 'condition', 'note', 'hcg') else (r[0], c.dx) + r[2:]
                         for r in c.records]
        # 6-month specimen valid under either anchor; 12-month specimen inside exactly one anchor's window.
        lo6 = max(window(charted, 6)[1], window(actual, 6)[1])
        hi6 = min(window(charted, 6)[2], window(actual, 6)[2])
        c.rpr(inside(g, lo6, hi6), max(1, c.titer // 4))
        due_c, lo_c, hi_c = window(charted, 12)
        due_a, lo_a, hi_a = window(actual, 12)
        if variant == 'anchor-late':      # specimen fits only the charted (wrong) anchor
            spec = inside(g, lo_c, lo_a)
        elif variant == 'anchor-early':   # specimen fits only the corrected anchor
            spec = inside(g, lo_a, lo_c)
        else:                             # disputed: fits only the charted anchor
            spec = inside(g, lo_c, lo_a)
        c.rpr(spec, max(1, c.titer // 16))      # reactive: it may precede a missed window
        if variant == 'dispute':
            author = g.pick([x for x in CLIN])
            c.note(plus(actual, g.rng.randint(1, 20)), 'clinician', author, 'Progress note', g.pick([
                f'Reviewing chart: per my notes the Bicillin was actually given {c.d(actual)}, not on the date in the MAR.',
                f'Pt\'s injection was given at the {c.d(actual)} visit per my documentation; the MAR date appears wrong.']))
            c.unknown = dict(code=CONF, kind='conflict', best='charted', latest='other', chart='charted',
                             options={'charted': {}, 'other': dict(doses=[(actual, 'bpg')])})
            c.gaps['conflict'] = (FUP,)
            expect(c, FUP=('cannot_determine', CONF))
            kind(c, FUP='chain', ADQ='chain_irrelevant')
        else:
            c.note(plus(max(actual, charted), g.rng.randint(1, 10)), 'nurse', nurse, 'Nursing note - late entry', g.pick([
                f'Correction to my MAR entry: the Bicillin dose documented {c.d(charted)} was actually administered {c.d(actual)}. '
                'Charted on the wrong encounter.',
                f'Late entry: I documented the injection under {c.d(charted)} in error; pt received it {c.d(actual)}.']))
            c.facts['doses'] = [(actual, 'bpg')]
            c.wrong['structured_only'] = dict(doses=[(charted, 'bpg')])
            if variant == 'anchor-late':
                expect(c, FUP=('confirmed', None))
            kind(c, FUP='chain')
        noise(c)
        return [c]
    # gap variants: late latent series, third dose date corrected by the administering nurse
    first = anchor_for(g, [12])
    c = Chart(g, 'F6_correction', variant, dx=first)
    diagnose(c, 'late_latent')
    nurse = g.pick(NURSES)
    d2 = plus(first, 7)
    good, bad = plus(d2, g.pick([7, 8])), plus(d2, g.rng.randint(16, 21))
    charted, actual = (good, bad) if variant == 'gap-worse' else (bad, good)
    for day in (first, d2, charted):
        give(c, day, nurse)
    c.note(plus(max(charted, actual), g.rng.randint(1, 6)), 'nurse', nurse, 'Nursing note - late entry', g.pick([
        f'Correction: the third Bicillin injection charted {c.d(charted)} was actually given {c.d(actual)}.',
        f'MAR correction by me: dose 3 date should be {c.d(actual)} (entered on wrong day).']))
    c.facts['doses'] = [(first, 'bpg'), (d2, 'bpg'), (actual, 'bpg')]
    c.wrong['structured_only'] = dict(doses=[(first, 'bpg'), (d2, 'bpg'), (charted, 'bpg')])
    followups(c, first, 'late_latent', open_extra=0.0)
    if variant == 'gap-worse':
        expect(c, ADQ=('confirmed', None))
    kind(c, ADQ='chain')
    noise(c)
    return [c]


def f7_outside_first_dose(g, variant):
    """Treatment begun at another facility sets the follow-up anchor, received or not."""
    stage = g.pick(['primary', 'secondary']) if variant != 'late' else 'late_latent'
    ed_day = anchor_for(g, [12])
    visit = plus(ed_day, g.rng.randint(12, 24))
    c = Chart(g, 'F7_outside_first_dose', variant, dx=ed_day)
    facility = g.pick(EDS)
    c.dx = ed_day
    diagnose(c, stage) if variant == 'late' else None
    if variant != 'late':
        c.facts['stage'] = stage
        c.records.append(('trep', visit, 'reactive'))
        c.titer = g.pick(TITER[stage])
        c.rpr(visit, c.titer)
        c.records.append(('condition', visit, g.pick(STAGE_TEXT[stage]), g.pick(CLIN)))
    if variant in ('received-conflict-ok', 'received-conflict-late'):
        stated = plus(ed_day, g.rng.randint(10, 14))
        c.records.append(('outside', plus(stated, g.rng.randint(2, 8)), facility,
                          f'{facility.upper()} - DISCHARGE INSTRUCTIONS / MAR\nPatient: {c.label}  DOB {c.d(c.dob)}\nSeen {c.d(ed_day)}. '
                          f'Dx: {"primary" if stage == "primary" else "secondary"} syphilis. '
                          'Benzathine penicillin G 2.4 million units IM administered. Follow up with STI clinic.'))
        c.note(plus(stated, g.rng.randint(20, 60)), 'clinician', g.pick(CLIN), 'Progress note', g.pick([
            f'Follow-up visit. Recall pt was treated at {facility} on {c.d(stated)}. Doing well, rash resolved.',
            f'Seen for follow-up; s/p Bicillin at {facility} {c.d(stated)}. No new complaints.']))
        c.facts['doses'] = [(ed_day, 'bpg')]
        c.wrong['latest_wins'] = dict(doses=[(stated, 'bpg')])
        c.wrong['structured_only'] = dict(doses=[])
        c.rpr(inside(g, window(stated, 6)[1], window(ed_day, 6)[2]), max(1, c.titer // 4))
        if variant == 'received-conflict-ok':      # 12-month specimen fits only the hospital-recorded date
            spec = inside(g, window(ed_day, 12)[1], window(stated, 12)[1])
        else:                                      # fits only the misstated date: overdue per the governing record
            spec = inside(g, window(ed_day, 12)[2], min(window(stated, 12)[2], EVAL))
            expect(c, FUP=('confirmed', None))
        c.rpr(spec, max(1, c.titer // 16) if c.titer > 8 else 'NR')
        c.gaps['outside_received'] = (FUP,)
        kind(c, FUP='chain_authority')
    elif variant in ('received', 'late'):
        if variant == 'late':
            c.records.append(('outside', plus(ed_day, 3), facility,
                              f'{facility.upper()} - VISIT SUMMARY\nPatient: {c.label}  DOB {c.d(c.dob)}\n{c.d(ed_day)}: RPR reactive. '
                              'Bicillin L-A 2.4 million units IM given x1 (first of weekly series). Referred to STI clinic for doses 2 and 3.'))
            give(c, plus(ed_day, 7))
            give(c, plus(ed_day, 14))
            c.facts['doses'] = [(ed_day, 'bpg'), (plus(ed_day, 7), 'bpg'), (plus(ed_day, 14), 'bpg')]
            c.wrong['structured_only'] = dict(doses=[(plus(ed_day, 7), 'bpg'), (plus(ed_day, 14), 'bpg')])
            followups(c, ed_day, stage, open_extra=0.0)
            kind(c, ADQ='chain', FUP='chain')
        else:
            c.records.append(('outside', plus(visit, -2), facility,
                              f'{facility.upper()} - DISCHARGE INSTRUCTIONS / MAR\nPatient: {c.label}  DOB {c.d(c.dob)}\nSeen {c.d(ed_day)}. '
                              f'Dx: {"primary" if stage == "primary" else "secondary"} syphilis (RPR reactive). '
                              'Benzathine penicillin G 2.4 million units IM administered. Follow up with STI clinic.'))
            c.note(visit, 'clinician', g.pick(CLIN), 'Progress note', g.pick([
                f'Seen in {facility} {c.d(ed_day)} and treated with Bicillin there (ED record reviewed). No further treatment needed.',
                f'Referred from {facility}; received BPG 2.4 MU on {c.d(ed_day)} per their MAR. Treatment complete; f/u serology.']))
            c.facts['doses'] = [(ed_day, 'bpg')]
            c.wrong['structured_only'] = dict(doses=[])
            # 6-month specimen valid for either anchor; 12-month specimen valid only from the ED date.
            c.rpr(inside(g, window(visit, 6)[1], window(ed_day, 6)[2]), max(1, c.titer // 4))
            spec = inside(g, window(ed_day, 12)[1], window(visit, 12)[1])
            c.rpr(spec, max(1, c.titer // 16) if c.titer > 8 else 'NR')
            kind(c, ADQ='chain', FUP='chain')
        c.gaps['outside_received'] = (ADQ, FUP)
    else:  # 'unreceived' / 'unreceived-both': patient reports an ED dose; clinic treats anyway
        c.note(visit, 'clinician', g.pick(CLIN), 'Progress note', g.pick([
            f'Pt reports being seen at {facility} ~{c.d(ed_day)} and "got a shot in the butt", no paperwork. Records '
            'requested. Unable to confirm, so Bicillin given today.',
            f'States treated at {facility} on {c.d(ed_day)}; ROI faxed for ED records. Giving BPG 2.4 MU today given '
            'uncertainty.']))
        give(c, visit)
        c.rpr(inside(g, window(visit, 6)[1], window(ed_day, 6)[2]), max(1, c.titer // 4))
        if variant == 'unreceived':
            spec = inside(g, window(ed_day, 12)[1], window(visit, 12)[1])
            expect(c, FUP=('cannot_determine', OUT))
            kind(c, FUP='chain', ADQ='relevance')
        else:
            spec = inside(g, window(visit, 12)[1], window(ed_day, 12)[2])
            kind(c, FUP='relevance', ADQ='relevance')
        c.rpr(spec, max(1, c.titer // 16) if c.titer > 8 else 'NR')
        c.unknown = dict(code=OUT, kind='outside', best='given', absent='not', chart='given',
                         options={'given': dict(doses=[(ed_day, 'bpg'), (visit, 'bpg')]), 'not': dict(doses=[(visit, 'bpg')])})
        c.gaps['outside'] = (ADQ, FUP)
    noise(c)
    return [c]


def f9_delivery(g, variant):
    """Delivery at another hospital: a received hospital record governs a conflicting later local note."""
    c = Chart(g, 'F9_delivery', variant, sex='female', age=(18, 40))
    c.dx = g.date_between('2024-06-01', '2025-12-15')
    diagnose(c, 'early_latent', pregnant_test=False)
    ga = g.rng.randint(24, 34)
    c.note(c.dx, 'clinician', g.pick(CLIN), 'Prenatal visit', f'{ga}w{g.rng.randint(0, 6)}d. RPR newly reactive. Bicillin today.')
    give(c, c.dx)
    hospital = g.pick(HOSPITALS)
    c.facts['pregnant'] = True
    if variant in ('hospital-ok', 'hospital-late'):
        real, wrong = (plus(c.dx, g.rng.randint(31, 34)), plus(c.dx, g.rng.randint(25, 29))) if variant == 'hospital-ok' \
            else (plus(c.dx, g.rng.randint(25, 29)), plus(c.dx, g.rng.randint(31, 34)))
        c.records.append(('outside', plus(real, g.rng.randint(5, 20)), hospital,
                          f'{hospital.upper()} - L&D DISCHARGE SUMMARY\nPatient: {c.label}  DOB {c.d(c.dob)}\nDelivery {c.d(real)}, '
                          f'{g.pick(["SVD", "primary cesarean", "vacuum-assisted vaginal delivery"])}, live infant. Maternal RPR reactive.'))
        c.note(plus(real, g.rng.randint(35, 50)), 'clinician', g.pick(CLIN), 'Postpartum visit',
               f'Postpartum check. Delivered {c.d(wrong)} at {hospital}. Recovering well.')
        c.facts['delivery'] = real
        c.wrong['latest_wins'] = dict(delivery=wrong)
        c.gaps['outside_received'] = (PRG,)
        if variant == 'hospital-late':
            expect(c, PRG=('confirmed', None))
            kind(c, PRG='chain')
        else:
            kind(c, PRG='chain')
        c.rpr(months(c.dx, 6) if D(months(c.dx, 6)) < EVALD else plus(EVAL, -5), max(1, c.titer // 4))
    else:  # 'unreceived': two local notes disagree, the hospital's record never arrived
        last = plus(c.dx, g.rng.randint(12, 22))
        c.note(last, 'clinician', g.pick(CLIN), 'Prenatal visit', f'{ga + (D(last) - D(c.dx)).days // 7}w. Doing well. Plans delivery at {hospital}.')
        early, late = plus(c.dx, g.rng.randint(24, 28)), plus(c.dx, g.rng.randint(32, 36))
        c.note(plus(late, 20), 'nurse', g.pick(NURSES), 'Telephone encounter',
               f'Pt called: delivered at {hospital} on {c.d(early)}. Delivery records requested from {hospital}.')
        c.note(plus(late, 45), 'clinician', g.pick(CLIN), 'Postpartum visit', f'Postpartum. Delivered {c.d(late)} per pt. Doing well.')
        c.unknown = dict(code=OUT, kind='outside', best='late', latest='late', absent='late',
                         options={'early': dict(delivery=early), 'late': dict(delivery=late)})
        c.gaps['outside'] = (PRG,)
        expect(c, PRG=('cannot_determine', OUT))
        kind(c, PRG='chain')
        c.rpr(months(c.dx, 6) if D(months(c.dx, 6)) < EVALD else plus(EVAL, -5), max(1, c.titer // 4))
    followups_after(c)
    noise(c)
    return [c]


def followups_after(c):
    """Fill any remaining closed windows (from the first dose) with own specimens."""
    first = min(r[1] for r in c.records if r[0] == 'bpg')
    have = [r[1] for r in c.records if r[0] == 'rpr' and r[1] > first]
    for m in schedule(c.facts['stage']):
        due, lo, hi = window(first, m)
        if D(hi) < EVALD + dt.timedelta(days=5) and not any(lo <= h <= hi for h in have):
            c.rpr(plus(due, c.g.rng.randint(-10, 10)), max(1, getattr(c, 'titer', 8) // 8))


# Stage-inference intake notes: examination and history only. No stage is named, and nothing else in these charts
# (no diagnosis-list entry, plan, order or follow-up note) names or schedules by stage.
F3_SECONDARY = [
    'c/o rash x {d} days, not itchy. Exam: diffuse maculopapular rash on trunk, palms and soles; mucous patches on the '
    'tongue; shotty cervical and inguinal nodes. RPR 1:{t}, TP-PA reactive. HIV neg.',
    'Rash for {d} days involving palms and soles, moist papules in the perianal area, patchy alopecia. RPR 1:{t}, '
    'treponemal reactive. HIV Ag/Ab nonreactive.',
    '{d} days of non-pruritic papulosquamous rash including palms and soles, sore throat, malaise. Mucous patches on '
    'buccal mucosa, generalized lymphadenopathy. RPR 1:{t}; TP-PA reactive. HIV neg.']
F3_NO_PRIOR = [
    'Referred after a reactive screen on routine labs. Denies sores, rash, hair loss or other symptoms in the past year. '
    'No prior syphilis testing on record or by history. No known contact to syphilis. Exam: no rash, no genital or oral '
    'lesions, no lymphadenopathy. RPR 1:{t}, TP-PA reactive. HIV neg.',
    'Reactive syphilis screen at blood donation. Asymptomatic; recalls no ulcer or rash. Never tested before. Unaware of '
    'any partner diagnosis. Exam unremarkable, skin and mucosa clear. RPR 1:{t}, treponemal reactive. HIV Ag/Ab nonreactive.',
    'Pre-employment labs: reactive treponemal test. No symptoms now or over the past year per pt. No earlier syphilis '
    'serology that pt knows of; no partner known to have syphilis. Exam: no rash, lesions or adenopathy. RPR 1:{t}, '
    'TP-PA reactive. HIV neg.']
F3_PRIOR = [
    'Routine screen. Asymptomatic; denies sores or rash since last visit. Exam: no rash, no genital or oral lesions, no '
    'lymphadenopathy. RPR nonreactive here {p}; now RPR 1:{t}, TP-PA reactive. No known contact to syphilis. HIV neg.',
    'Screening visit, no symptoms. Last syphilis screen at this clinic {p} was nonreactive. Today RPR 1:{t}, treponemal '
    'reactive. Exam without rash or lesions. Unaware of any partner diagnosis. HIV Ag/Ab nonreactive.']


def f3_stage_inference(g, variant):
    """No stage anywhere in the chart: the examination and testing history set it (CDC 2021), and the stage sets
    adequacy and whether a 24-month test is due. `early1` / `lapsed1` are matched: they differ only in whether the
    prior nonreactive test falls within the 12 months before diagnosis (documented seroconversion -> early latent)."""
    first = anchor_for(g, [24])
    c = Chart(g, 'F3_stage_inference', variant, dx=first)
    stage = {'secondary': 'secondary', 'early1': 'early_latent'}.get(variant, 'late_latent')
    c.titer = g.pick(TITER[stage] if variant not in ('early1', 'lapsed1') else [4, 8, 16])
    doc = g.pick(CLIN)
    if variant in ('early1', 'lapsed1'):
        prior = plus(first, -g.rng.randint(90, 270) if variant == 'early1' else -g.rng.randint(460, 670))
        c.note(prior, 'nurse', g.pick(NURSES), 'Nursing note', g.pick(['Routine STI screen; labs drawn.', 'Screening labs drawn per protocol.']))
        c.rpr(prior, 'NR')
        text = g.pick(F3_PRIOR).format(p=c.d(prior), t=c.titer)
    elif variant == 'secondary':
        text = g.pick(F3_SECONDARY).format(d=g.rng.randint(8, 25), t=c.titer)
    else:
        text = g.pick(F3_NO_PRIOR).format(t=c.titer)
    c.records.append(('lab', first, 'HIV-1/2 Ag/Ab', 'Nonreactive'))
    c.records.append(('trep', first, 'reactive'))
    c.rpr(first, c.titer)
    if c.sex == 'female' and 17 < (EVALD - D(c.dob)).days / 365 < 50:
        c.records.append(('hcg', first, 'negative', {}))
    c.note(first, 'clinician', doc, g.pick(['Progress note', 'New patient visit', 'STI clinic visit']),
           text + '\n' + g.pick(['Plan: Bicillin L-A 2.4 MU IM today. Partner referral given.',
                                 'Bicillin L-A 2.4 million units IM today; partner notification discussed.']))
    c.facts.update(stage=stage, stage_recorded=False)
    if variant == 'latent3':
        treat(c, 'late_latent', first, gaps=[7, 7])
        followups(c, first, stage, skip=(24,), open_extra=0.0)
        expect(c, FUP=('confirmed', None))
        kind(c, ADQ='relevance', FUP='inference')
    else:
        give(c, first)
        followups(c, first, stage, open_extra=0.0)
        if variant in ('latent1', 'lapsed1'):
            expect(c, ADQ=('confirmed', None))
        kind(c, ADQ='inference', **({'FUP': 'inference'} if variant == 'secondary' else {}))
    wrong = 'late_latent' if variant in ('secondary', 'early1') else 'early_latent'
    c.wrong['fill_stage'] = dict(stage=wrong)
    if wrong == 'late_latent':
        c.wrong['default_late'] = dict(stage='late_latent')
    c.gaps['stage_unrecorded'] = (ADQ, FUP)
    noise(c)
    return [c]


# ------------------------------------------------------------------------------------------------ single-step and background

def single(g, variant):
    c = Chart(g, 'S_single', variant)
    if variant == 'overdue':
        stage = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
        m = g.pick(schedule(stage))
        c.dx = anchor_for(g, [m])
        diagnose(c, stage)
        treat(c, stage, c.dx)
        followups(c, c.dx, stage, skip=(m,), open_extra=0.0)
        expect(c, FUP=('confirmed', None))
        kind(c, FUP='real')
    elif variant == 'gap16':
        c.dx = anchor_for(g, [6])
        diagnose(c, 'late_latent')
        treat(c, 'late_latent', c.dx, gaps=[7, g.rng.randint(16, 22)])
        followups(c, c.dx, 'late_latent', open_extra=0.0)
        expect(c, ADQ=('confirmed', None))
        kind(c, ADQ='real')
    elif variant == 'untreated':
        c.dx = g.date_between(plus(EVAL, -200), plus(EVAL, -40))
        diagnose(c, g.pick(['primary', 'secondary', 'early_latent']))
        c.records.append(('med', c.dx, 'Bicillin L-A 2.4 million units', '2.4 million units IM', g.pick(NURSES),
                          g.pick(['Pt declined injection today.', 'Pt left before injection given.']), 'not-done'))
        expect(c, ADQ=('confirmed', None))
        kind(c, ADQ='real')
    elif variant == 'pending_fu':
        stage = g.pick(['primary', 'secondary', 'early_latent'])
        c.dx = months(plus(EVAL, -30 - g.rng.randint(3, 20)), -12)     # 12-month window closed 3-20 days ago
        diagnose(c, stage)
        treat(c, stage, c.dx)
        wins = followups(c, c.dx, stage, skip=(12,), open_extra=0.0)
        c.rpr(inside(g, max(wins[12][1], plus(EVAL, -35)), wins[12][2]), None, status='pending',
              comment=g.pick(['Received at reference laboratory. Result to follow.', 'In process.']))
        request(c, FUP, g.pick(REQ[FUP]))
        kind(c, FUP='relevance')
    elif variant == 'rejected':
        stage = g.pick(['primary', 'secondary', 'early_latent'])
        c.dx = anchor_for(g, [12])
        diagnose(c, stage)
        treat(c, stage, c.dx)
        wins = followups(c, c.dx, stage, skip=(12,), open_extra=0.0)
        c.rpr(g.date_between(wins[12][1], min(wins[12][2], plus(EVAL, -4))), None, status='rejected',
              comment=g.pick(['Specimen hemolyzed. Test not performed.', 'QNS - test not performed. Please recollect.']))
        expect(c, FUP=('confirmed', None))
        kind(c, FUP='real')
    elif variant == 'unknown_duration1':
        c.dx = g.date_between(plus(EVAL, -300), plus(EVAL, -40))
        diagnose(c, 'late_latent')
        give(c, c.dx)
        followups(c, c.dx, 'late_latent', open_extra=0.0)
        expect(c, ADQ=('confirmed', None))
        kind(c, ADQ='real')
    elif variant == 'outside_unreceived':
        c.dx = g.date_between(plus(EVAL, -160), plus(EVAL, -50))
        diagnose(c, 'late_latent')
        give(c, c.dx)
        clinic = g.pick(CLINICS)
        c.note(plus(c.dx, 9), 'nurse', g.pick(NURSES), 'Telephone encounter',
               f'Pt says remaining Bicillin shots are being given at {clinic} (closer to work). Records request faxed.')
        c.unknown = dict(code=OUT, kind='outside', best='given', absent='not',
                         options={'given': dict(doses=[(c.dx, 'bpg'), (plus(c.dx, 7), 'bpg'), (plus(c.dx, 14), 'bpg')]),
                                  'not': dict(doses=[(c.dx, 'bpg')])})
        c.gaps['outside'] = (ADQ,)
        expect(c, ADQ=('cannot_determine', OUT))
        kind(c, ADQ='undeterminable')
    elif variant == 'outside_received':
        c.dx = anchor_for(g, [6])
        diagnose(c, 'late_latent')
        give(c, c.dx)
        clinic = g.pick(CLINICS)
        c.records.append(('outside', plus(c.dx, 20), clinic,
                          f'{clinic.upper()} - MEDICATION ADMINISTRATION RECORD\nPatient: {c.label}  DOB {c.d(c.dob)}\n'
                          f'{c.d(plus(c.dx, 7))} Bicillin L-A 2.4 MU IM\n{c.d(plus(c.dx, 14))} Bicillin L-A 2.4 MU IM'))
        c.facts['doses'] = [(c.dx, 'bpg'), (plus(c.dx, 7), 'bpg'), (plus(c.dx, 14), 'bpg')]
        c.wrong['structured_only'] = dict(doses=[(c.dx, 'bpg')])
        c.gaps['outside_received'] = (ADQ,)
        followups(c, c.dx, 'late_latent', open_extra=0.0)
        request(c, ADQ, g.pick(REQ[ADQ]))
        kind(c, ADQ='nonissue')
    elif variant in ('outside_conflict_complete', 'outside_conflict_incomplete'):
        c.dx = anchor_for(g, [6])
        diagnose(c, 'late_latent')
        give(c, c.dx)
        clinic = g.pick(CLINICS)
        complete = variant == 'outside_conflict_complete'
        rows = f'{c.d(plus(c.dx, 7))} Bicillin L-A 2.4 MU IM' + (f'\n{c.d(plus(c.dx, 14))} Bicillin L-A 2.4 MU IM' if complete else
               f'\n{c.d(plus(c.dx, 14))} No-show for scheduled dose. Not rescheduled.\nSeries incomplete at this facility.')
        c.records.append(('outside', plus(c.dx, 22), clinic,
                          f'{clinic.upper()} - MEDICATION ADMINISTRATION RECORD\nPatient: {c.label}  DOB {c.d(c.dob)}\n{rows}'))
        c.note(plus(c.dx, g.rng.randint(40, 90)), 'nurse', g.pick(NURSES), 'Telephone encounter', g.pick([
            f'Pt says {clinic} only gave one more shot, not two.' if complete else f'Pt states they finished all three shots; the last two were at {clinic}.',
            f'Per pt, only one injection was given at {clinic}.' if complete else f'Per pt, the second and third injections were both given at {clinic}.']))
        doses = [(c.dx, 'bpg'), (plus(c.dx, 7), 'bpg')] + ([(plus(c.dx, 14), 'bpg')] if complete else [])
        c.facts['doses'] = doses
        c.wrong['latest_wins'] = dict(doses=doses[:2] if complete else doses + [(plus(c.dx, 14), 'bpg')])
        c.wrong['structured_only'] = dict(doses=[(c.dx, 'bpg')])
        c.gaps['outside_received'] = (ADQ,)
        followups(c, c.dx, 'late_latent', open_extra=0.0)
        if not complete:
            expect(c, ADQ=('confirmed', None))
        kind(c, ADQ='chain_authority')
    elif variant == 'name_change':
        c.dx = anchor_for(g, [6])
        stage = g.pick(['primary', 'secondary', 'early_latent'])
        diagnose(c, stage)
        treat(c, stage, c.dx)
        old = g.pick(LAST).upper() + ', ' + c.name.split(' ')[0].upper()
        c.note(plus(c.dx, 30), 'registration', 'Front desk (L. Ames)', 'Registration update',
               f'Legal name change on file. Previous last name: {old.split(",")[0].title()}. MRN unchanged.')
        wins = followups(c, c.dx, stage, skip=(6,), open_extra=0.0)
        c.rpr(plus(wins[6][0], g.rng.randint(-10, 10)), max(1, c.titer // 4), label_name=old)
        request(c, MIS, g.pick(REQ[MIS]))
        kind(c, MIS='nonissue')
    elif variant == 'pep':
        c.dx = g.date_between(plus(EVAL, -200), plus(EVAL, -40))
        c.records.append(('dispense', plus(c.dx, -60), 'Doxycycline hyclate 100 mg tablet', 20, 30,
                          'Take 2 tablets (200 mg) once within 72 hours after condomless sex. Max 200 mg per 24 h.', 'doxy-PEP'))
        diagnose(c, 'early_latent')
        c.note(plus(c.dx, 1), 'clinician', g.pick(CLIN), 'Telephone encounter',
               'On doxy-PEP regularly; likely partially treated. Will recheck RPR rather than give Bicillin now.')
        expect(c, ADQ=('confirmed', None))
        c.wrong['pep_is_treatment'] = dict(doses=[(c.dx, 'bpg')])
        kind(c, ADQ='inference')
    else:
        raise ValueError(variant)
    noise(c)
    return [c]


def background(g, variant):
    c = Chart(g, 'B_background', variant)
    stage = g.pick(['primary', 'secondary', 'early_latent', 'late_latent'])
    c.dx = g.date_between('2024-01-10', plus(EVAL, -45))
    if variant == 'pregnant':
        c = Chart(g, 'B_background', variant, sex='female', age=(18, 40))
        c.dx = g.date_between('2024-02-01', '2026-02-01')
        stage = g.pick(['early_latent', 'late_latent'])
        diagnose(c, stage, pregnant_test=False)
        c.records.append(('hcg', c.dx, 'positive', {}))
        days = treat(c, stage, c.dx, gaps=[7, 7])
        hospital = g.pick(HOSPITALS)
        delivery = plus(days[0], g.rng.randint(45, 140))
        if D(delivery) < EVALD - dt.timedelta(days=20):
            c.records.append(('outside', plus(delivery, 10), hospital,
                              f'{hospital.upper()} - L&D DISCHARGE SUMMARY\nPatient: {c.label}  DOB {c.d(c.dob)}\nDelivery {c.d(delivery)}, live infant.'))
            c.facts['delivery'] = delivery
            c.gaps['outside_received'] = (PRG,)
        c.facts['pregnant'] = True
        followups(c, c.dx, stage, open_extra=0.2)
        kind(c, PRG='control')
    else:
        diagnose(c, stage)
        days = treat(c, stage, c.dx)
        followups(c, c.dx, stage)
        if variant == 'recollected':
            first = days[0]
            for m in schedule(stage):
                due, lo, hi = window(first, m)
                if D(hi) < EVALD:
                    bad = plus(lo, c.g.rng.randint(0, 10))
                    c.rpr(bad, None, status='rejected', comment=g.pick(['Hemolyzed; not performed.', 'Quantity not sufficient; recollect.']))
                    break
    noise(c, n=g.rng.randint(0, 4))
    return [c]


# 0.3.0: two or three instances per variant (a run applies one rule to every instance of a variant, so copies add
# workload, not difficulty) and a smaller background. F7 `unreceived` (a patient-reported ED dose that moves the
# follow-up anchor) was removed by user decision after pilot 0.2.0; `unreceived-both` keeps the same story where the
# answer does not depend on it.
PLAN = (
    [(f1_identity_conflict, v, 3) for v in ('a', 'b', 'c', 'd', 'e', 'f')] +
    [(f2_resolved_misfile, v, n) for v, n in (('a', 3), ('b', 2), ('c', 2), ('d', 3))] +
    [(f4_pending_pregnancy, v, 3) for v in ('doxy', 'late1', 'early1', 'late3')] +
    [(f5_hcg_identity, v, n) for v, n in (('misfile', 3), ('conflict', 2), ('conflict-bpg', 2), ('irrelevant', 2))] +
    [(f6_correction, v, 3) for v in ('anchor-late', 'anchor-early', 'dispute', 'gap-worse', 'gap-better')] +
    [(f7_outside_first_dose, v, n) for v, n in (('received', 3), ('late', 2), ('unreceived-both', 3),
                                                ('received-conflict-ok', 3), ('received-conflict-late', 3))] +
    [(f9_delivery, v, 3) for v in ('hospital-ok', 'hospital-late', 'unreceived')] +
    [(single, v, 2) for v in ('outside_conflict_complete', 'outside_conflict_incomplete')] +
    [(f3_stage_inference, v, n) for v, n in (('secondary', 3), ('latent3', 3), ('latent1', 2), ('early1', 3), ('lapsed1', 3))] +
    [(single, v, 2) for v in ('overdue', 'gap16', 'untreated', 'pending_fu', 'rejected', 'unknown_duration1',
                              'outside_unreceived', 'outside_received', 'name_change', 'pep')]
)
TARGET_TOTAL = 200 - len(CORE)


def generate(seed=SEED):
    g = Gen(seed)
    patients = []
    for family, variant, n in PLAN:
        for _ in range(n):
            patients += [c.patient() for c in family(g, variant)]
    i = 0
    while len(patients) < TARGET_TOTAL:
        variant = 'pregnant' if i % 9 == 4 else 'recollected' if i % 7 == 3 else 'plain'
        patients += [c.patient() for c in background(g, variant)]
        i += 1
    # Review requests on a spread of chained instances (both directions), fixed by position.
    by_family = {}
    for p in patients:
        by_family.setdefault((p['family'], p['variant']), []).append(p)
    wanted = [('F1_identity_conflict', 'a', MIS), ('F1_identity_conflict', 'b', FUP), ('F1_identity_conflict', 'd', MIS),
              ('F1_identity_conflict', 'f-partner', FUP), ('F2_resolved_misfile', 'a-owner', FUP), ('F2_resolved_misfile', 'd-owner', FUP),
              ('F2_resolved_misfile', 'b', MIS), ('F4_pending_pregnancy', 'doxy', ADQ), ('F4_pending_pregnancy', 'early1', PRG),
              ('F5_hcg_identity', 'misfile-other', PRG), ('F5_hcg_identity', 'conflict', ADQ), ('F5_hcg_identity', 'irrelevant', PRG),
              ('F6_correction', 'anchor-late', FUP), ('F6_correction', 'anchor-early', FUP), ('F6_correction', 'gap-better', ADQ),
              ('F7_outside_first_dose', 'received', FUP), ('F7_outside_first_dose', 'unreceived-both', FUP),
              ('F9_delivery', 'hospital-ok', PRG), ('F9_delivery', 'unreceived', PRG), ('F3_stage_inference', 'secondary', FUP)]
    rng = random.Random(seed + 1)
    for fam, var, issue in wanted:
        target = by_family[(fam, var)][0]
        target['requests'][issue] = rng.choice(REQ[issue])
    return patients, g.externals
