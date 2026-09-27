"""Standard-of-care Task 1 (chartr_soc): hand-written charts, CDC-grounded determinations.

Private. Contains expected answers. Clinical rules come from the CDC 2021 STI Treatment Guidelines
(stage-dependent benzathine penicillin regimens, dose-interval restarts including pregnancy, doxy-PEP is
not treatment); clinic-specific rules (follow-up months, windows, spacing, conditional schedules, holds,
replacements) are written into each patient's own orders and notes. Golden rows are authored by hand
below; the reference solver recomputes them from public records plus solution/readings.json (what an
expert reader extracts from each free-text note and order).
"""
import base64, hashlib, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'chartr_soc'
sys.path[:0] = [str(TASK / 'environment/service')]
from fhir import extension, validate, digest, VERSION, NOW

CLINICIANS = ['Dr. Imani Shaw', 'Dr. Noah Patel', 'Dr. Elias Green']
AUTHORS = {'clinician': CLINICIANS, 'nurse': ['Mina Cho, RN', 'Jordan Lee, RN'], 'laboratory': ['Clinical Laboratory (M. Ortiz, MLS)']}


def rid(key): return 'R' + hashlib.sha256(('soc-v1:' + key).encode()).hexdigest()[:12]


class Chart:
    def __init__(self, key, name):
        self.key, self.name = key, name
        self.pid = 'P' + rid(key)[1:8]
        self.sources, self.readings, self.episodes, self.golden = [], {}, [], {}
        self.sources.append({'resourceType': 'Patient', 'id': self.pid, 'name': [{'text': name}]})

    def ref(self, k): return rid(self.key + '.' + k)

    def add(self, kind, k, day, **attrs):
        r = {'resourceType': kind, 'id': self.ref(k), 'subject': {'reference': 'Patient/' + self.pid},
             'extension': [extension('event-time', 'DateTime', day + 'T09:00:00Z')], **attrs}
        self.sources.append(r)
        return r['id']

    def episode(self, k, start):
        eid = 'E' + self.ref('ep' + k)[1:]
        self.sources.append({'resourceType': 'EpisodeOfCare', 'id': eid, 'status': 'active',
                             'patient': {'reference': 'Patient/' + self.pid}, 'period': {'start': start}})
        self.episodes.append(eid)
        return eid

    def order(self, k, ep, day, drug, text, reading):
        oid = self.add('MedicationRequest', k, day, status='active', intent='order', authoredOn=day + 'T09:00:00Z',
                       medicationCodeableConcept={'text': drug}, dosageInstruction=[{'text': text}])
        self.sources[-1]['extension'].append(extension('episode', 'Reference', {'reference': 'EpisodeOfCare/' + ep}))
        self.readings['order:' + oid] = reading
        return oid

    def dose(self, k, order, when, text, drug='Bicillin L-A 2.4 MU IM'):
        common = dict(status='completed', medicationCodeableConcept={'text': drug}, request={'reference': 'MedicationRequest/' + order},
                      dosage={'text': text})
        if isinstance(when, tuple):
            return self.add('MedicationAdministration', k, when[0], effectivePeriod={'start': when[0], 'end': when[1]}, **common)
        return self.add('MedicationAdministration', k, when, effectiveDateTime=when + 'T09:00:00Z', **common)

    def plan(self, k, order, day, text, reading):
        pid = self.add('ServiceRequest', k, day, status='active', intent='plan', code={'text': 'Serologic follow-up (RPR)'},
                       authoredOn=day + 'T11:00:00Z', supportingInfo=[{'reference': 'MedicationRequest/' + order}], note=[{'text': text}])
        self.readings['plan:' + pid] = reading
        return pid

    def rpr(self, k, day, titer, extra=()):
        spec = self.add('Specimen', k + '.spec', day, status='available', collection={'collectedDateTime': day + 'T08:30:00Z'})
        ids = [self.add('Observation', k, day, status='final', code={'text': 'RPR titer'}, effectiveDateTime=day + 'T08:30:00Z',
                        issued=day + 'T17:00:00Z', specimen={'reference': 'Specimen/' + spec}, valueInteger=titer)]
        for suffix, value, issued, note in extra:
            ids.append(self.add('Observation', k + suffix, day, status='final', code={'text': 'RPR titer'}, effectiveDateTime=day + 'T08:30:00Z',
                                issued=issued, specimen={'reference': 'Specimen/' + spec}, valueInteger=value, note=[{'text': note}]))
        return ids

    def note(self, k, day, role, text, reading=None, author=0):
        name = AUTHORS[role][author % len(AUTHORS[role])]
        sign = {'clinician': f'Electronically signed: {name}', 'nurse': f'Signed: {name}', 'laboratory': f'Released by {name}'}[role]
        body = text + '\n\n' + sign
        nid = self.add('DocumentReference', k, day, status='current', docStatus='final', date=day + 'T14:00:00Z', description=body,
                       author=[{'display': name}], authenticator={'display': name},
                       content=[{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(body.encode()).decode()}}])
        self.sources[-1]['extension'].append(extension('author-role', 'Code', role))
        self.readings[nid] = {'role': role, 'date': day + 'T14:00:00Z', **(reading or {})}
        return nid

    def row(self, ep, checkpoint, status, plan=None, course=None, branch=None, doses=(), completion=None, due=None, paused=None, results=()):
        self.golden[ep + ':' + checkpoint] = {'episode': ep, 'checkpoint': checkpoint, 'status': status, 'plan': plan, 'course': course,
                                             'branch': branch, 'doses': list(doses), 'completion_date': completion, 'due_date': due,
                                             'paused_days': paused, 'results': list(results)}


def standard_rows(c, ep, first, second, **fields):
    c.row(ep, 'first', first[0], due=first[1], results=first[2] if len(first) > 2 else (), **fields)
    c.row(ep, 'second', second[0], due=second[1], results=second[2] if len(second) > 2 else (), **fields)


def charts():
    out = []

    # A: latent of unknown duration (3 doses); replaced plan; ineffective dose-date correction;
    # unauthorized nurse schedule change; unreceived outside RPR that fits no open checkpoint.
    c = Chart('alvarez', 'Rosa Alvarez'); ep = c.episode('1', '2026-02-23')
    c.note('dx', '2026-02-23', 'clinician',
           'New patient visit\nReferred after routine screening: RPR 1:16, TP-PA reactive. No rash, no genital or oral lesions; neuro and eye exam unremarkable. '
           'No prior syphilis testing on record and pt does not recall ever being tested. Urine hCG negative today. Will start weekly Bicillin.',
           {'diagnosis': {'episode': ep, 'finding': 'none', 'last_negative': None, 'pregnant': False}})
    c.rpr('base', '2026-02-23', 16)
    o = c.order('bpg', ep, '2026-03-02', 'Bicillin L-A (benzathine penicillin G)', '2.4 MU IM weekly x3', {'drug': 'bpg', 'restart_over': None})
    d = [c.dose('d1', o, '2026-03-02', 'R ventrogluteal. Tolerated well.'), c.dose('d2', o, '2026-03-09', 'L ventrogluteal.'),
         c.dose('d3', o, '2026-03-16', 'R gluteal; observed 15 min, no reaction.')]
    old = c.plan('plan1', o, '2026-03-02', 'Repeat RPR at 3 and 6 months after completing the series. A draw counts if collected from 3 weeks before to 5 weeks '
                 'after its due date; the 6-month draw only counts once the 3-month draw is done, at least 6 weeks later.',
                 {'months': [3, 6], 'before': 21, 'after': 35, 'separation': 42, 'condition': None, 'replaces': None})
    new = c.plan('plan2', o, '2026-03-20', 'Replaces the 3/2 follow-up plan. Serologic f/u for latent syphilis: RPR at 6 and 12 months after completion of the '
                 'series. The 12-month draw counts only after the 6-month draw is done, at least 6 weeks apart.',
                 {'months': [6, 12], 'before': None, 'after': None, 'separation': 42, 'condition': None, 'replaces': old})
    c.note('corr', '2026-04-02', 'clinician', 'Addendum\nCharting error: the Bicillin injection charted 3/9 was actually given 3/10.',
           {'clauses': [[1, 'set', d[1], 'date', '2026-03-10']]}, author=1)
    c.note('rn', '2026-05-11', 'nurse', 'Nursing note\nPer clinic protocol, moved her follow-up RPR to 3 months after treatment. Recall letter mailed.',
           {'clauses': [[1, 'set', new, 'months', '3,12']]})
    c.note('outside', '2026-06-10', 'clinician', 'Telephone note\nPt says she had an RPR drawn at County Health on 6/1 for a work physical. '
           'Records release signed; result requested, not yet received.', {'unreceived': '2026-06-01'}, author=2)
    r = c.rpr('fu1', '2026-09-10', 4)
    f = dict(plan=new, course=o, doses=d, completion='2026-03-16', paused=0)
    standard_rows(c, ep, ('completed', '2026-09-16', r), ('not_due', '2027-03-16'), **f)
    out.append(c)

    # B: early latent (negative RPR within 12 months) so one dose completes; lab date correction
    # moves the only draw out of the window.
    c = Chart('whitfield', 'Dana Whitfield'); ep = c.episode('1', '2026-04-06')
    c.note('dx', '2026-04-06', 'clinician',
           'Clinic visit\nAsymptomatic. Screening RPR 1:32, TP-PA reactive. Outside records from Eastgate Community Clinic show a nonreactive RPR on 1/8/26. '
           'No lesions, rash, or neuro/ocular symptoms. Not pregnant.',
           {'diagnosis': {'episode': ep, 'finding': 'none', 'last_negative': '2026-01-08', 'pregnant': False}})
    o = c.order('bpg', ep, '2026-04-06', 'Benzathine penicillin G', '2.4 million units IM x1', {'drug': 'bpg', 'restart_over': None})
    d = [c.dose('d1', o, '2026-04-06', 'Given L gluteal. Tolerated.')]
    p = c.plan('plan', o, '2026-04-06', 'F/u RPR at 6 mo and 12 mo after treatment. A draw counts if collected within 30 days either side of the due date. '
               'The 12-mo draw only counts once the 6-mo draw is done, >= 6 wks apart.',
               {'months': [6, 12], 'before': 30, 'after': 30, 'separation': 42, 'condition': None, 'replaces': None})
    spec = c.rpr('fu1', '2026-09-15', 8)
    c.note('labfix', '2026-09-18', 'laboratory', 'Laboratory correction notice\nSpecimen labeling error: the RPR specimen charted as collected 9/15/26 was '
           'actually collected 8/29/26 (label printed on the wrong day). Result unchanged.',
           {'clauses': [[1, 'set', c.ref('fu1.spec'), 'collected', '2026-08-29']]})
    standard_rows(c, ep, ('not_due', '2026-10-06'), ('blocked', '2027-04-06'), plan=p, course=o, doses=d, completion='2026-04-06', paused=0)
    out.append(c)

    # C: pregnant, late latent; a 10-day gap restarts the series under CDC pregnancy guidance.
    c = Chart('natarajan', 'Priya Natarajan'); ep = c.episode('1', '2026-01-26')
    c.note('dx', '2026-01-26', 'clinician',
           'Prenatal intake, 14 wks by LMP\nRPR 1:8, TP-PA reactive. Asymptomatic, no lesions or rash. Last negative syphilis screen was during her 2023 pregnancy. '
           'Plan weekly Bicillin; coordinating with OB.',
           {'diagnosis': {'episode': ep, 'finding': 'none', 'last_negative': '2023-05-01', 'pregnant': True}})
    o = c.order('bpg', ep, '2026-02-02', 'Bicillin L-A (benzathine penicillin G)', '2.4 MU IM weekly x3 (pregnant)', {'drug': 'bpg', 'restart_over': None})
    d = [c.dose('d1', o, '2026-02-02', 'R ventrogluteal.'), c.dose('d2', o, '2026-02-09', 'L ventrogluteal.'),
         c.dose('d3', o, '2026-02-19', 'R ventrogluteal.'), c.dose('d4', o, '2026-02-26', 'L ventrogluteal.'), c.dose('d5', o, '2026-03-05', 'R ventrogluteal.')]
    c.note('rn', '2026-02-19', 'nurse', 'Nursing note\nPt missed last week\'s injection (traveling). Dose given today; next appointments booked with OB.')
    p = c.plan('plan', o, '2026-02-02', 'Pregnancy: repeat RPR at 3 and 6 months after completion of therapy. Each draw counts if collected within 4 weeks '
               'either side of its due date. The 6-month draw counts only after the 3-month draw, at least 6 weeks later.',
               {'months': [3, 6], 'before': 28, 'after': 28, 'separation': 42, 'condition': None, 'replaces': None})
    r1 = c.rpr('fu1', '2026-06-20', 4); r2 = c.rpr('fu2', '2026-08-20', 2)
    f = dict(plan=p, course=o, doses=d[2:], completion='2026-03-05', paused=0)
    standard_rows(c, ep, ('completed', '2026-06-05', r1), ('completed', '2026-09-05', r2), **f)
    out.append(c)

    # D: secondary syphilis, then reinfection (new episode); the first plan is discontinued.
    c = Chart('bell', 'Marcus Bell'); e1 = c.episode('1', '2026-01-12'); e2 = c.episode('2', '2026-06-15')
    c.note('dx1', '2026-01-12', 'clinician', 'Clinic visit\nDiffuse maculopapular rash including palms and soles x2 wks. RPR 1:64, TP-PA reactive. '
           'Dx secondary syphilis. Bicillin given today.', {'diagnosis': {'episode': e1, 'finding': 'rash', 'last_negative': None, 'pregnant': False}})
    o1 = c.order('bpg1', e1, '2026-01-12', 'Bicillin L-A', '2.4 MU IM once', {'drug': 'bpg', 'restart_over': None})
    c.dose('d1', o1, '2026-01-12', 'R gluteal.')
    p1 = c.plan('plan1', o1, '2026-01-12', 'RPR at 6 and 12 months after treatment; the 12-month draw counts only after the 6-month draw, >= 6 wks apart.',
                {'months': [6, 12], 'before': None, 'after': None, 'separation': 42, 'condition': None, 'replaces': None})
    c.rpr('m1', '2026-03-30', 4)
    c.rpr('dx2', '2026-06-15', 128)
    c.note('dx2', '2026-06-15', 'clinician', 'Clinic visit\nNew painless genital ulcer x5 days. RPR today 1:128 (was 1:4 on 3/30). Reinfection; primary syphilis. '
           'New episode opened. Discontinue the January follow-up plan; new plan entered today. Bicillin given today.',
           {'diagnosis': {'episode': e2, 'finding': 'chancre', 'last_negative': None, 'pregnant': False},
            'clauses': [[1, 'set', p1, 'status', 'revoked']]}, author=1)
    o2 = c.order('bpg2', e2, '2026-06-15', 'Bicillin L-A', '2.4 MU IM once', {'drug': 'bpg', 'restart_over': None})
    d2 = [c.dose('d2', o2, '2026-06-15', 'L gluteal.')]
    p2 = c.plan('plan2', o2, '2026-06-15', 'Follow-up serology: RPR at 6 and 12 months after treatment. The 12-month draw counts only after the 6-month draw, '
                'at least 6 weeks apart.',
                {'months': [6, 12], 'before': None, 'after': None, 'separation': 42, 'condition': None, 'replaces': None})
    c.rpr('m2', '2026-07-20', 32)
    c.row(e1, 'first', 'no_requirement'); c.row(e1, 'second', 'no_requirement')
    standard_rows(c, e2, ('not_due', '2026-12-15'), ('blocked', '2027-06-15'), plan=p2, course=o2, doses=d2, completion='2026-06-15', paused=0)
    out.append(c)

    # E: primary syphilis "treated" with a single 200 mg doxycycline dose (the doxy-PEP regimen), which
    # is not syphilis treatment; treatment is not complete.
    c = Chart('oduya', 'Terrence Oduya'); ep = c.episode('1', '2026-05-10')
    c.note('dx', '2026-05-10', 'clinician', 'Clinic visit\nPainless penile ulcer x1 wk. RPR 1:16, TP-PA reactive. Dx primary syphilis. Reports anaphylaxis to '
           'penicillin (2019). Treating with doxycycline; see order.', {'diagnosis': {'episode': ep, 'finding': 'chancre', 'last_negative': None, 'pregnant': False}})
    o = c.order('doxy', ep, '2026-05-10', 'Doxycycline', '200 mg PO x1', {'drug': 'doxy_pep', 'restart_over': None})
    c.dose('d1', o, '2026-05-10', 'Doxycycline 200 mg PO, taken in clinic.', drug='Doxycycline 200 mg PO')
    p = c.plan('plan', o, '2026-05-10', 'RPR at 3 and 6 months after treatment; count draws within 3 weeks before to 5 weeks after the due date; the 6-month '
               'draw only after the 3-month draw, >= 6 weeks apart.',
               {'months': [3, 6], 'before': 21, 'after': 35, 'separation': 42, 'condition': None, 'replaces': None})
    c.rpr('fu1', '2026-07-27', 8)
    c.row(ep, 'first', 'not_due', plan=p, course=o, paused=0); c.row(ep, 'second', 'not_due', plan=p, course=o, paused=0)
    out.append(c)

    # F: unknown duration (3 doses); conditional schedule whose comparison titer is discrepant but
    # fourfold either way; a date correction retracted by another clinician; duplicate report copy.
    c = Chart('park', 'Helen Park'); ep = c.episode('1', '2026-05-28')
    c.note('dx', '2026-05-28', 'clinician', 'Referral visit\nRising titer: RPR 1:4 on 5/1/26 (pre-employment screen), repeated today. TP-PA reactive. '
           'Asymptomatic, exam normal. No earlier testing available. Not pregnant.',
           {'diagnosis': {'episode': ep, 'finding': 'none', 'last_negative': None, 'pregnant': False}})
    c.rpr('base', '2026-05-01', 4)
    c.rpr('cmp', '2026-05-28', 16, extra=[('.ref', 32, '2026-05-29T12:00:00Z', 'Reported via reference lab interface.')])
    c.note('qa', '2026-05-30', 'laboratory', 'Lab QA notice\nThe 5/28/26 RPR was reported as 1:16 by the in-house analyzer and 1:32 by the reference lab '
           'interface. Discrepancy under review; neither result has been verified.')
    o = c.order('bpg', ep, '2026-06-01', 'BPG (Bicillin L-A)', '2.4 MU IM weekly x3', {'drug': 'bpg', 'restart_over': None})
    d = [c.dose('d1', o, '2026-06-01', 'R ventrogluteal.'), c.dose('d2', o, '2026-06-08', 'L ventrogluteal.'), c.dose('d3', o, '2026-06-15', 'R ventrogluteal.')]
    p = c.plan('plan', o, '2026-06-01', 'RPR at 6 and 12 mo after the series is complete. If the 5/28 RPR is at least fourfold the 5/1 baseline, use 3 and 6 mo '
               'instead. Draws count from 2 wks before to 4 wks after the due date. The later draw counts only after the first, >= 6 wks apart.',
               {'months': [6, 12], 'before': 14, 'after': 28, 'separation': 42,
                'condition': {'baseline': c.ref('base.spec'), 'comparison': c.ref('cmp.spec'), 'alt': [3, 6]}, 'replaces': None})
    n1 = c.note('corr', '2026-09-02', 'clinician', 'Addendum\nCharting error: the 6/15 injection was given 6/16.', {'clauses': [[1, 'set', d[2], 'date', '2026-06-16']]})
    c.note('retract', '2026-09-04', 'clinician', 'Addendum\nDisregard Dr. Shaw\'s 9/2 correction; the 6/15 injection date was right (confirmed against the MAR scan).',
           {'clauses': [[1, 'withdraw', n1, 1, None]]}, author=2)
    r = c.rpr('fu1', '2026-09-08', 4, extra=[('.copy', 4, '2026-09-08T17:00:00Z', 'Duplicate report from reference lab interface, same accession.')])
    f = dict(plan=p, course=o, branch='accelerated', doses=d, completion='2026-06-15', paused=0)
    standard_rows(c, ep, ('completed', '2026-09-15', r), ('not_due', '2026-12-15'), **f)
    out.append(c)

    # G: unknown duration; the second dose was given elsewhere on an unrecorded date whose range straddles
    # the order's 14-day restart rule, so completion cannot be established.
    c = Chart('siddiqui', 'Omar Siddiqui'); ep = c.episode('1', '2026-02-24')
    c.note('dx', '2026-02-24', 'clinician', 'Clinic visit\nAsymptomatic; RPR 1:8, TP-PA reactive on screening. No prior tests. Not pregnant. Plan weekly Bicillin.',
           {'diagnosis': {'episode': ep, 'finding': 'none', 'last_negative': None, 'pregnant': False}})
    o = c.order('bpg', ep, '2026-03-03', 'Bicillin L-A', '2.4 MU IM weekly x3', {'drug': 'bpg', 'restart_over': None})
    c.dose('d1', o, '2026-03-03', 'R gluteal.')
    c.dose('d2', o, ('2026-03-12', '2026-03-19'), 'Given at Northside Urgent Care while pt was traveling; exact date not recorded (sometime between 3/12 and 3/19).')
    c.dose('d3', o, '2026-03-24', 'L gluteal.')
    p = c.plan('plan', o, '2026-03-03', 'RPR at 6 and 12 months after completion; each draw counts within 30 days either side of its due date. The 12-month draw '
               'counts only after the 6-month draw, at least 6 weeks later.',
               {'months': [6, 12], 'before': 30, 'after': 30, 'separation': 42, 'condition': None, 'replaces': None})
    c.rpr('fu1', '2026-09-10', 2)
    c.row(ep, 'first', 'unclear'); c.row(ep, 'second', 'unclear')
    out.append(c)

    # H: primary syphilis, one dose; a clinician hold moves due dates by 14 days; an unreceived outside RPR
    # falls inside the open 6-month window.
    c = Chart('fischer', 'Lena Fischer'); ep = c.episode('1', '2026-02-10')
    c.note('dx', '2026-02-10', 'clinician', 'Clinic visit\nPainless ulcer on labia x10 days; RPR 1:32, TP-PA reactive. Dx primary syphilis. hCG negative. Bicillin today.',
           {'diagnosis': {'episode': ep, 'finding': 'chancre', 'last_negative': None, 'pregnant': False}})
    o = c.order('bpg', ep, '2026-02-10', 'Benzathine penicillin G', '2.4 MU IM once', {'drug': 'bpg', 'restart_over': None})
    d = [c.dose('d1', o, '2026-02-10', 'R gluteal; observed 15 min.')]
    p = c.plan('plan', o, '2026-02-10', 'RPR at 6 and 12 months after treatment. A draw counts from 3 weeks before to 5 weeks after its due date; the 12-month '
               'draw counts only after the 6-month draw and at least 8 weeks later.',
               {'months': [6, 12], 'before': 21, 'after': 35, 'separation': 56, 'condition': None, 'replaces': None})
    c.note('hold', '2026-04-01', 'clinician', 'Clinical note\nPt admitted to St. Luke\'s for pyelonephritis. Placing her follow-up clock on hold from 4/1; resume 4/15. '
           'Follow-up due dates move later by the number of held days.', {'hold': {'episode': ep, 'start': '2026-04-01', 'end': '2026-04-15'}}, author=1)
    c.rpr('early', '2026-07-01', 8)
    c.note('outside', '2026-09-02', 'clinician', 'Telephone note\nCalled Northside Urgent Care: RPR drawn there on 8/15. Result requested by fax; not yet received.',
           {'unreceived': '2026-08-15'}, author=2)
    f = dict(plan=p, course=o, doses=d, completion='2026-02-10', paused=14)
    standard_rows(c, ep, ('cannot_determine', '2026-08-24'), ('blocked', '2027-02-24'), **f)
    out.append(c)
    return out


MEMOS = [
    ('memo.standing', '2025-01-15', 'Standing orders: follow-up recalls',
     'Nursing staff may adjust follow-up RPR recall dates under the standing recall protocol without a new clinician order.',
     {'authority': {'nurse_may_change_plans': True}}),
    ('memo.window', '2025-09-01', 'Follow-up serology windows',
     'Unless the follow-up plan states otherwise, a follow-up RPR counts toward a checkpoint if it is collected from 3 weeks before to '
     '5 weeks after that checkpoint\'s due date.', {'default_window': [21, 35]}),
    ('memo.bpg', '2025-09-01', 'Benzathine penicillin series: missed doses',
     'For patients who are not pregnant: if any interval between doses of a weekly benzathine penicillin series exceeds 14 days, restart '
     'the series. Pregnant patients follow current CDC guidance.', {'restart_over_nonpregnant': 14}),
    ('memo.authority', '2026-01-05', 'Documentation authority',
     'Effective today; supersedes the 1/15/25 standing-orders memo. Only clinicians may order or change treatment, review holds, and follow-up '
     'plans. Only the laboratory may change specimens and results. Other staff may document but may not change these records.',
     {'authority': {'nurse_may_change_plans': False}, 'supersedes': 'memo.standing'}),
]


def memos():
    out, readings = [], {}
    for key, day, title, text, reading in MEMOS:
        body = f'{title}\n{text}\n\nClinic Operations Committee'
        r = {'resourceType': 'DocumentReference', 'id': rid(key), 'status': 'current', 'docStatus': 'final', 'date': day + 'T12:00:00Z',
             'description': body, 'author': [{'display': 'Clinic Operations Committee'}],
             'content': [{'attachment': {'contentType': 'text/plain', 'data': base64.b64encode(body.encode()).decode()}}],
             'extension': [extension('event-time', 'DateTime', day + 'T12:00:00Z'), extension('clinic-memo', 'Boolean', True)]}
        out.append(r)
        readings['memo:' + r['id']] = {'date': day, **{k: (rid(v) if k == 'supersedes' else v) for k, v in reading.items()}}
    return out, readings


def build():
    sources, targets, expected, readings = memos()[0], {}, {}, dict(memos()[1])
    for c in charts():
        sources += c.sources; targets[c.pid] = c.episodes; readings.update(c.readings)
        expected[c.pid] = {'rows': c.golden, 'unreceived': [r['unreceived'] for r in c.readings.values() if 'unreceived' in r]}
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
