"""Task 3 private rule engine (PRIVATE).

Recomputes every candidate's disposition from each patient's clinical facts under the CDC 2021 STI
Treatment Guidelines plus the published local conventions, by evaluating every possible world of the
patient's single unknown: confirmed / not_an_issue when all worlds agree, otherwise cannot_determine
with the unknown's code. The same machinery evaluates the deliberately wrong algorithms.
"""
import calendar
import datetime as dt

from task3_cases import PATIENTS, EVAL, ISSUES, ADQ, FUP, MIS, PRG, PEND, OUT, CONF

D = dt.date.fromisoformat
EARLY = ('primary', 'secondary', 'early_latent')
ALGORITHMS = ('never_abstain', 'abstain_any_gap', 'flag_all', 'per_patient', 'ignore_received',
              'ignore_unreceived', 'pending_negative', 'pending_not_obtained', 'latest_wins', 'default_late',
              'pep_is_treatment', 'nonpregnant_interval_in_pregnancy', 'structured_only')
GAP_CODE = {'stage_unrecorded': CONF, 'conflict': CONF, 'outside': OUT, 'outside_received': OUT,
            'pending_hcg': PEND, 'pending_rpr': PEND}
BY_KEY = {p['key']: p for p in PATIENTS}


def months(day, n):
    ix = day.year * 12 + day.month - 1 + n
    y, m = divmod(ix, 12)
    return dt.date(y, m + 1, min(day.day, calendar.monthrange(y, m + 1)[1]))


def derived(p, view='full'):
    """Structured facts read from the chart; case facts override them."""
    doses, fu, misfiled = [], [], False
    for r in p['records']:
        kind, day = r[0], r[1]
        if kind == 'bpg':
            doses.append((day, 'bpg' if r[2].startswith('2.4') else 'bpg_half'))
        elif kind == 'med' and r[6] == 'completed':
            doses.append((day, 'azithro' if 'zithro' in r[2] else 'other'))
        elif kind == 'dispense' and 'oxycycline' in r[2]:
            doses.append((day, 'pep' if '72 hours' in r[5] else {14: 'doxy14', 28: 'doxy28'}[r[4]]))
    first = min((d for d, _ in doses), default=None)
    for q in [p if x['key'] == p['key'] else x for x in PATIENTS]:
        for r in q['records']:
            if r[0] != 'rpr' or not first:
                continue
            owner = r[3].get('owner', q['key'])
            mine = (q['key'] == p['key']) if view == 'per_patient' else owner == p['key']
            if q['key'] == p['key'] and owner != p['key'] and view != 'per_patient':
                misfiled = True
            if mine and D(r[1]) > D(first):
                fu.append((r[1], r[3].get('status', 'final')))
    return dict(doses=doses, fu=fu, misfiled=misfiled, stage_recorded=True, pregnant=False, allergy=False,
                delivery=None, extra_fu=[], fu_drop=[])


def adequate(f, pregnant_gap=9):
    """Whether counted treatment is adequate for the stage and pregnancy status (CDC 2021)."""
    after = sorted(d for d in f['doses'] if D(d[0]) >= D(f['dx']))
    bpg = [D(d) for d, k in after if k == 'bpg']
    doxy = [k for _, k in after if k in ('doxy14', 'doxy28')]
    if f['stage'] in EARLY:
        if bpg:
            return True, bpg[0]
        ok = f['allergy'] and not f['pregnant'] and doxy
        return bool(ok), None
    for i in range(len(bpg) - 2):
        gaps = [(bpg[i + 1] - bpg[i]).days, (bpg[i + 2] - bpg[i + 1]).days]
        limit = pregnant_gap if f['pregnant'] else 9
        if not f['pregnant']:
            assert all(g <= 9 or g >= 15 for g in gaps), 'guideline-hedged 10-14 day gap outside pregnancy'
        if all(6 <= g <= limit for g in gaps):
            return True, bpg[i]
    ok = f['allergy'] and not f['pregnant'] and 'doxy28' in doxy
    return bool(ok), None


def evaluate(f, pending_counts=True, pregnant_gap=9):
    """Disposition of each issue in one fully specified world: True means the issue exists."""
    ok, start = adequate(f, pregnant_gap)
    out = {ADQ: (D(EVAL) - D(f['dx'])).days >= 30 and not ok, MIS: f['misfiled']}
    if not f['pregnant']:
        out[PRG] = False
    else:
        # Ongoing pregnancy: adequate treatment so far. After delivery: begun at least 30 days before it.
        timely = f['delivery'] is None or (start is not None and (D(f['delivery']) - start).days >= 30)
        out[PRG] = not (ok and timely)
    treated = [D(d) for d, k in f['doses'] if k != 'pep' and D(d) >= D(f['dx'])]
    overdue = False
    if treated:
        anchor = min(treated)
        specimens = [(D(d), s) for d, s in f['fu'] + f['extra_fu'] if d not in f['fu_drop']]
        for m in ((6, 12) if f['stage'] in ('primary', 'secondary') else (6, 12, 24)):
            due = months(anchor, m)
            lo, hi = due - dt.timedelta(days=30), due + dt.timedelta(days=30)
            if hi >= D(EVAL):
                continue
            usable = ('final', 'pending') if pending_counts else ('final',)
            if not any(lo <= d <= hi and s in usable for d, s in specimens):
                overdue = True
    out[FUP] = overdue
    return out


def facts(p, view='full', overrides=()):
    f = {**derived(p, view), 'dx': p['dx'], **p['facts']}
    for o in overrides:
        f.update(o)
    return f


def disposition(p, algorithm=None):
    """{issue: (disposition, code)} for one patient under the truth or a wrong algorithm."""
    if algorithm == 'flag_all':
        return {i: ('confirmed', None) for i in ISSUES}
    view = 'per_patient' if algorithm == 'per_patient' else 'full'
    extra = [p['wrong'][algorithm]] if algorithm in p['wrong'] else []
    kw = dict(pending_counts=algorithm != 'pending_not_obtained',
              pregnant_gap=14 if algorithm == 'nonpregnant_interval_in_pregnancy' else 9)
    unknown = p.get('unknown')
    if algorithm == 'never_abstain':
        extra += [p['wrong'].get('fill_stage', {})]
    worlds = [{}]
    if unknown:
        worlds = list(unknown['options'].values())
        chosen = {'never_abstain': 'best', 'latest_wins': 'latest', 'pending_negative': 'negative',
                  'ignore_unreceived': 'absent'}.get(algorithm)
        if chosen and unknown.get(chosen) and (chosen == 'best' or unknown['kind'] in
                                               {'latest': 'conflict', 'negative': 'pending', 'absent': 'outside'}[chosen]):
            worlds = [unknown['options'][unknown[chosen]]]
        if algorithm == 'per_patient' and unknown['kind'] == 'conflict' and 'collection' in unknown['options']:
            worlds = [unknown['options']['collection']]
    results = [evaluate(facts(p, view, [w] + extra), **kw) for w in worlds]
    out = {}
    for issue in ISSUES:
        values = {r[issue] for r in results}
        out[issue] = ('confirmed', None) if values == {True} else ('not_an_issue', None) if values == {False} \
            else ('cannot_determine', unknown['code'])
    if algorithm == 'abstain_any_gap':
        for tag, issues in p['gaps'].items():
            for issue in issues:
                out[issue] = ('cannot_determine', GAP_CODE[tag])
    if algorithm == 'ignore_received':
        for issue in p['gaps'].get('outside_received', ()):
            out[issue] = ('cannot_determine', OUT)
    return out


def cohort(algorithm=None):
    return {p['key']: disposition(p, algorithm) for p in PATIENTS}
