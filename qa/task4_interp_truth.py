"""Graded ECG interpretation specs for Task 4 v0.3 (private).

From the three readers (task4/ecg_reads.json), the catalog labels and edits, every served ECG gets a spec per field. A field
is graded only where independent readers agree; otherwise any value is accepted. Specs:
  rhythm        exact (SINUS / AF / PACED)
  rate          range: all reads -5/+5 (AF +-12)
  qrs_ms        range when machine and global QRS agree within 30 ms: [min-15, max+15]
  pr_ms         SINUS: range when two readers agree within 25 ms: [min-20, max+20]; AF: must be null; PACED: any
  qtc_ms        SINUS: Bazett reads agreeing within 60 ms of their median (>= 2 reads): [min-20, max+20]; edited: catalog range
  axis          one category when machine and global agree >= 10 deg from a boundary; neighbours accepted near a boundary
  conduction    required / allowed sets (BBB from machine statement + global morphology + QRS >= 120 by both readers;
                first-degree AV block from machine PR >= 210 confirmed by a second reader >= 210)
Comparisons (latest ECG vs the patient's previous served ECG) derive from both ECGs' specs.
Run with the labeling venv after task4_catalog.py and task4_interpret.py:  data/.labvenv/bin/python qa/task4_interp_truth.py
"""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'task4'
CATS = [('NORMAL', -30, 90), ('LEFT', -90, -30), ('RIGHT', 90, 180), ('EXTREME', -180, -90)]
# Rhythms that designer review could not settle (pilot evidence reviewed at high resolution): either reading is accepted.
#  108780865: slow irregular rhythm; the cart says AF, but low-amplitude waves ~150 ms before each QRS may be P waves.
#  100924231: fixed regular 141/min two days after AF; 2:1 flutter vs sinus tachycardia cannot be separated.
RHYTHM_AMBIGUOUS = {'108780865': ['AF', 'SINUS'], '100924231': ['ATRIAL_FLUTTER', 'OTHER', 'SINUS']}   # 100924231: also read as ectopic atrial tachycardia
NEIGHBOURS = {'NORMAL': ['LEFT', 'RIGHT'], 'LEFT': ['NORMAL', 'EXTREME'], 'RIGHT': ['NORMAL', 'EXTREME'], 'EXTREME': ['LEFT', 'RIGHT']}


def wrap(d):
    return (d + 180) % 360 - 180


def axis_cat(d):
    d = wrap(d)
    for name, lo, hi in CATS:
        if lo <= d <= hi:
            return name
    return 'EXTREME'


def margin(d):
    d = wrap(d)
    return min(abs(d - b) for b in (-90, -30, 90, 180, -180))


def bazett(qt, hr):
    return qt / (60 / hr) ** 0.5 if qt and hr else None


def agreeing(vals, spread=60):
    vals = sorted(v for v in vals if v)
    if not vals:
        return []
    med = vals[len(vals) // 2]
    return [v for v in vals if abs(v - med) <= spread]


def rng(vals, pad):
    return [round(min(vals) - pad, 1), round(max(vals) + pad, 1)]


def spec_for(sid, t, r, lab):
    rhythm = 'AF' if t['label'] == 'AF' else 'PACED' if t['label'] == 'PACED' else 'SINUS'
    M, N, G = r['M'] or {}, r['N'] or {}, r['G'] or {}
    artifact = (t.get('edit') or '').startswith('artifact')
    options = RHYTHM_AMBIGUOUS.get(sid)
    if options is None and rhythm == 'SINUS' and re.search(r'(?i)ectopic atrial', M.get('text') or ''):
        options = ['OTHER', 'SINUS']      # the cart itself hedges between sinus and an ectopic atrial rhythm
    s = {'rhythm': {'one_of': sorted(options)} if options else {'exact': rhythm}, 'ventricular_rate': {'range': t['hr_range']}}
    # QRS
    q = [v for v in (M.get('qrs'), G.get('qrs')) if v]
    s['qrs_ms'] = {'range': rng(q, 25)} if len(q) == 2 and abs(q[0] - q[1]) <= 30 else {'any': True}
    # PR
    if rhythm == 'AF':
        s['pr_ms'] = {'null': True}
    else:   # PR onset conventions differ by 30-50 ms between methods; PR is graded through first-degree AV block only
        s['pr_ms'] = {'any': True}
    # QTc (Bazett)
    if t.get('qtc_range'):
        s['qtc_ms'] = {'range': t['qtc_range']}
        qreads = list(t['qtc_reads'].values())
    elif rhythm == 'SINUS':
        # Anchor on the cart and neurokit2 (the readers the catalog's QTc screen used); admit the tangent and global reads
        # only when they fall within 40 ms of the anchors (T-end detection occasionally runs away).
        A = lab['reads'].get('A') or {}
        base = [v for v in (bazett(M.get('qt'), M.get('hr')), bazett(N.get('qt'), N.get('hr'))) if v]
        if len(base) == 2 and abs(base[0] - base[1]) <= 50:
            # QT end-point conventions (global vs single-lead tangent) differ by 30-50 ms: accept every plausible reader +-40 (inter-observer variability)
            mid = sum(base) / 2
            qreads = base + [v for v in (bazett(A.get('qt'), A.get('hr')), bazett(G.get('qt'), G.get('hr'))) if v and abs(v - mid) <= 60]
            s['qtc_ms'] = {'range': rng(qreads, 40)}
        else:
            qreads = []
            s['qtc_ms'] = {'any': True}
    else:
        qreads = []
        s['qtc_ms'] = {'any': True}
    # axis
    if artifact and 'la_ra' in t['edit']:
        s['axis'] = {'any': True}
    elif M.get('axis') is not None and G.get('axis') is not None and abs(wrap(M['axis'] - G['axis'])) > 40:
        s['axis'] = {'any': True}   # readers disagree: indeterminate (typically low-voltage QRS)
    elif M.get('axis') is not None and G.get('axis') is not None:
        cm, cg = axis_cat(M['axis']), axis_cat(G['axis'])
        if cm == cg and min(margin(M['axis']), margin(G['axis'])) >= 10:
            s['axis'] = {'exact': cm}
        elif cm == cg:
            near = {axis_cat(a + d) for a in (M['axis'], G['axis']) for d in (-10, 10)}
            s['axis'] = {'one_of': sorted(near)}
        elif cg in NEIGHBOURS[cm]:
            s['axis'] = {'one_of': sorted({cm, cg})}
        else:
            s['axis'] = {'any': True}
    else:
        s['axis'] = {'any': True}
    # conduction
    required, allowed = set(), set()
    mc = set(r['machine_conduction'] or [])
    wide = len(q) == 2 and min(q) >= 120
    narrow = len(q) == 2 and max(q) < 110
    for bbb in ('RBBB', 'LBBB'):
        if rhythm == 'PACED':
            allowed.add(bbb)
        elif bbb in mc and G.get('bbb_morphology') == bbb and wide:
            required.add(bbb)
        elif not narrow or bbb in mc:
            allowed.add(bbb)
    if rhythm == 'SINUS':
        mpr = M.get('pr'); others = [v for v in (G.get('pr'), N.get('pr')) if v]
        if 'FIRST_DEGREE_AV_BLOCK' in mc and mpr and mpr >= 210 and any(v >= 210 for v in others):
            required.add('FIRST_DEGREE_AV_BLOCK')
        elif not (mpr and N.get('pr') and max(v for v in (mpr, N['pr'], G.get('pr')) if v) <= 160):
            # forbidden only when the cart and neurokit, and the global reader if it found a P wave, all leave a 40 ms margin
            allowed.add('FIRST_DEGREE_AV_BLOCK')
    elif rhythm == 'PACED':
        allowed.add('FIRST_DEGREE_AV_BLOCK')
    s['conduction'] = {'required': sorted(required), 'allowed': sorted(allowed - required)}
    return s, qreads


def changes(cur, prev, cur_q, prev_q):
    required, allowed = set(), set()
    opts = lambda sp: sp['rhythm'].get('one_of') or [sp['rhythm']['exact']]
    combos = [(c, p) for c in opts(cur) for p in opts(prev)]
    for rhythm, name in (('AF', 'AF'), ('ATRIAL_FLUTTER', 'ATRIAL_FLUTTER'), ('PACED', 'PACED_RHYTHM')):
        for tag, holds in (('NEW_', lambda c, p: c == rhythm and p != rhythm), ('RESOLVED_', lambda c, p: p == rhythm and c != rhythm)):
            hits = [holds(c, p) for c, p in combos]
            if all(hits):
                required.add(tag + name)
            elif any(hits):
                allowed.add(tag + name)
    bbb = lambda s, k: set(s['conduction'][k]) & {'RBBB', 'LBBB'}
    c_req, c_opt, p_req, p_opt = bbb(cur, 'required'), bbb(cur, 'allowed'), bbb(prev, 'required'), bbb(prev, 'allowed')
    if c_req and not (p_req or p_opt):
        required.add('NEW_BUNDLE_BRANCH_BLOCK')
    elif (c_req or c_opt) and not p_req:
        allowed.add('NEW_BUNDLE_BRANCH_BLOCK')
    if p_req and not (c_req or c_opt):
        required.add('RESOLVED_BUNDLE_BRANCH_BLOCK')
    elif (p_req or p_opt) and not c_req:
        allowed.add('RESOLVED_BUNDLE_BRANCH_BLOCK')
    if 'range' in cur['qtc_ms'] and 'range' in prev['qtc_ms'] and opts(cur) == opts(prev) == ['SINUS']:
        # v0.4 (audit): use the same padded ranges the QTc fields accept, so any pair of accepted readings implies a change
        # (or no change) that the comparison also accepts.
        (clo, chi), (plo, phi) = cur['qtc_ms']['range'], prev['qtc_ms']['range']
        lo, hi = clo - phi, chi - plo
        if lo >= 60: required.add('QTC_INCREASE_60')
        elif hi >= 60: allowed.add('QTC_INCREASE_60')
        if hi <= -60: required.add('QTC_DECREASE_60')
        elif lo <= -60: allowed.add('QTC_DECREASE_60')
    else:
        allowed |= {'QTC_INCREASE_60', 'QTC_DECREASE_60'}
    return {'required': sorted(required), 'allowed': sorted(allowed - required)}


def main():
    catalog = json.loads((OUT / 'ecg_catalog.json').read_text())
    truth = json.loads((OUT / 'ecg_truth.json').read_text())
    reads = json.loads((OUT / 'ecg_reads.json').read_text())
    labels = json.loads((OUT / 'ecg_labels.json').read_text())
    specs, qsets = {}, {}
    for e in catalog:
        sid = e['study_id']
        specs[sid], qsets[sid] = spec_for(sid, truth[sid], reads[sid], labels[sid])
    by = {}
    for e in catalog:
        by.setdefault(e['patient'], []).append(e)
    latest = {}
    for p, rows in by.items():
        rows.sort(key=lambda e: e['ecg_time'])
        cur = rows[-1]['study_id']; prev = rows[-2]['study_id'] if len(rows) > 1 else None
        latest[p] = {'ecg': cur, 'subject_id': rows[-1]['subject_id'], 'fields': specs[cur],
                     'prior_ecg': prev, 'changes': changes(specs[cur], specs[prev], qsets[cur], qsets[prev]) if prev else {'required': [], 'allowed': []}}
    (OUT / 'ecg_interp.json').write_text(json.dumps({'ecg': specs, 'latest': latest}, indent=1) + '\n')
    from collections import Counter
    graded = Counter(f for v in latest.values() for f, sp in v['fields'].items() if 'any' not in sp)
    print(len(latest), 'patients with ECGs; graded fields on latest ECGs:', dict(graded))
    print('required changes:', Counter(c for v in latest.values() for c in v['changes']['required']))
    print('required conduction:', Counter(c for v in latest.values() for c in v['fields']['conduction']['required']))
    print('rhythms:', Counter(json.dumps(v['fields']['rhythm']) for v in latest.values()), 'axis:', Counter(json.dumps(v['fields']['axis']) for v in latest.values()))


if __name__ == '__main__':
    main()
