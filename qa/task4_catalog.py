"""Task 4 ECG catalog: which recordings the clinic's ECG system holds, the edits, and the private truth.

Only unambiguous recordings are served (clean AF, clean normal sinus, or an edited prolonged QT); paced,
flutter, poor-quality and borderline-QT strips are simply not in the clinic's system. Edits:
  * QT lengthening on chosen current ECGs (and one older ECG as a look-alike), tuned so every independent
    measurement (in-house tangent, neurokit2 DWT and CWT; leads II and V5) reads Bazett QTc >= 505 ms
    while the cart-equivalent reading stays close to the threshold;
  * artifact on chosen normal ECGs (muscle noise, motion, baseline wander, LA/RA reversal) and on one AF strip.
Edited samples are stored as integer differences from the PhysioNet originals (`ecg_deltas.npz`), so the
image build fetches the pinned originals and reproduces every file byte for byte.

Run with the labeling venv:  data/.labvenv/bin/python qa/task4_catalog.py
"""
import json, re, sys, warnings
from pathlib import Path
import numpy as np
warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import task4_data as T
import task4_ecg_labels as L
import task4_ecg_edit as E

OUT = HERE / 'task4'
BAD = re.compile(r'(?i)pac(ed|ing|emaker)|flutter|artifact|unsuitable|poor quality|baseline wander')

# study_id -> edit. Current ECGs of QT cases; one older ECG (look-alike); artifact controls; noisy AF.
QT_EDITS = {'104821039': 'current', '106885519': 'current', '101515306': 'current', '105362569': 'older', '108018814': 'current'}
# 109419304 (motion, seed 12) was withdrawn after pilot 1: on that low-voltage tracing the artifact made the rhythm unreadable.
ARTIFACTS = {'106825293': ('emg', 11), '101538691': ('wander', 13),
             '107859369': ('la_ra', 14), '108211642': ('wander', 15)}


def usable_label(v):
    if v['label'] in ('NORMAL', 'QTC_PROLONGED', 'AF'):
        return v['label']
    m = v['reads']['machine']
    if m and not BAD.search(m.get('text') or '') and re.search(r'(?i)atrial fibrillation', m.get('text') or ''):
        irr = [x['irregular'] for x in (v['reads']['A'], v['reads']['B']) if x]
        if len(irr) == 2 and min(irr) > 0.08:
            return 'AF'
    return None


def measure_all(mv, fs=500):
    """Bazett QTc and HR from every independent method on leads II and V5."""
    import neurokit2 as nk
    qtcs, hrs = {}, {}
    for li, ln in ((1, 'II'), (10, 'V5')):
        x = mv[:, li]
        reads = {'A': L.alg_a(x, fs), 'nk-dwt': L.alg_b(x, fs)}
        try:
            c = nk.ecg_clean(x, sampling_rate=fs); _, info = nk.ecg_peaks(c, sampling_rate=fs); r = np.asarray(info['ECG_R_Peaks'])
            _, w = nk.ecg_delineate(c, r, sampling_rate=fs, method='cwt')
            q = [(t - o) / fs * 1000 for o, t in zip(np.asarray(w['ECG_R_Onsets'], float), np.asarray(w['ECG_T_Offsets'], float))
                 if np.isfinite(o) and np.isfinite(t) and 200 < (t - o) / fs * 1000 < 750]
            reads['nk-cwt'] = {'hr': 60 / np.median(np.diff(r) / fs), 'qt': float(np.median(q)) if len(q) >= 3 else None}
        except Exception:
            pass
        for name, rd in reads.items():
            if rd and rd.get('hr'):
                hrs[f'{ln}/{name}'] = round(float(rd['hr']), 1)
            if rd and rd.get('qt'):
                qtcs[f'{ln}/{name}'] = round(float(L.qtc(rd['qt'], rd['hr'], 'bazett')), 1)
    return qtcs, hrs


def agreeing(reads, spread=60):
    """Reads within `spread` ms of the median; failed delineations (far-off values) are not reasonable reads."""
    med = float(np.median(list(reads.values())))
    return {k: v for k, v in reads.items() if abs(v - med) <= spread}


def lengthen_verified(rec):
    for target in range(530, 600, 5):
        new, info = E.lengthen_qt(rec, target)
        qtcs, hrs = measure_all(new / np.asarray(rec.adc_gain))
        good = agreeing(qtcs) if qtcs else {}
        if len(good) >= 4 and min(good.values()) >= 505:
            return new, target, good, hrs, info
    raise ValueError('could not reach a fair QT margin')


def build():
    labels = json.loads((OUT / 'ecg_labels.json').read_text())
    data, subject = T.load_demo(); ecgs = T.ecg_records(); off = T.anchors(data, subject, ecgs)
    fhir_id = {v: k for k, v in subject.items()}
    shifted = {e['study_id']: e for e in T.shifted_ecgs(ecgs, off)}
    catalog, truth, deltas = [], {}, {}
    for e in ecgs:
        sid = e['study_id']; lab = usable_label(labels[sid])
        if not lab:
            continue
        rec = E.load(T.ECG_DIR / e['path'])
        d = rec.d_signal.astype(np.int64)
        entry = {'study_id': sid, 'subject_id': e['subject_id'], 'patient': fhir_id[e['subject_id']],
                 'ecg_time': shifted[sid]['ecg_time'], 'path': e['path']}
        t = {'label': lab, 'edit': None}
        if sid in QT_EDITS:
            new, target, qtcs, hrs, info = lengthen_verified(rec)
            t.update(label='QTC_PROLONGED', edit=f'qt_lengthened:{QT_EDITS[sid]}', target_bazett=target, qtc_reads=qtcs,
                     qtc_range=[min(qtcs.values()) - 20, max(qtcs.values()) + 20], hr_reads=hrs, delta_ms=round(info['delta_ms']))
            d = new
        elif sid in ARTIFACTS:
            kind, seed = ARTIFACTS[sid]
            d = E.add_artifact(rec, kind, seed)
            t['edit'] = f'artifact:{kind}'
        if 'hr_reads' not in t:
            q, h = measure_all(d / np.asarray(rec.adc_gain)) if sid in ARTIFACTS else ({}, {})
            base = [x for x in (labels[sid]['reads'].get('A') or {}, labels[sid]['reads'].get('B') or {}, labels[sid]['reads'].get('machine') or {})
                    if x.get('hr')]
            t['hr_reads'] = {k: v for k, v in zip(('A', 'nk', 'machine'), [round(x['hr'], 1) for x in base])}
            if q: t['after_artifact'] = {'qtc': q, 'hr': h}
        hrs = list(t['hr_reads'].values())
        tol = 12 if t['label'] == 'AF' else 5
        t['hr_range'] = [round(min(hrs) - tol, 1), round(max(hrs) + tol, 1)] if hrs else None
        if not np.array_equal(d, rec.d_signal):
            deltas[sid] = (d - rec.d_signal.astype(np.int64)).astype(np.int32)
        catalog.append(entry); truth[sid] = t
    OUT.mkdir(exist_ok=True)
    (OUT / 'ecg_catalog.json').write_text(json.dumps(catalog, indent=1) + '\n')
    (OUT / 'ecg_truth.json').write_text(json.dumps(truth, indent=1) + '\n')
    np.savez_compressed(OUT / 'ecg_deltas.npz', **deltas)
    from collections import Counter
    print('catalog', len(catalog), 'ECGs for', len({c['subject_id'] for c in catalog}), 'patients;', dict(Counter(v['label'] for v in truth.values())))
    for sid in list(QT_EDITS) + list(ARTIFACTS):
        v = truth.get(sid)
        if v: print(sid, v['edit'], v.get('target_bazett'), v.get('qtc_reads') or v.get('after_artifact'), v.get('hr_range'))


if __name__ == '__main__':
    build()
