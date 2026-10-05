"""Private ECG labeling for Task 4 (designer aid; never reaches the agent).

Three independent reads of every MIMIC-IV-ECG Demo recording:
  A. A simple in-house algorithm on lead II: band-passed energy peaks for R waves, RR irregularity,
     and QT from QRS onset to T end on the median beat (tangent method).
  B. neurokit2 (cleaning, R peaks, DWT delineation) on lead II.
  C. The ECG cart's own statements and intervals from the open MIMIC-IV-ECG v1.0 machine_measurements.csv,
     matched by subject and minute (the full module renumbers study IDs).
A recording is labelled only when all available reads agree with a wide margin; everything else is
"ambiguous" and is left out of the clinic's ECG system. Run with the separate labeling venv:
    data/.labvenv/bin/python qa/task4_ecg_labels.py
"""
import csv, json, re, sys, warnings
from pathlib import Path
import numpy as np
from scipy import signal
import wfdb

warnings.filterwarnings('ignore')
MAIN = Path(__file__).resolve().parents[1]
DEMO = MAIN / 'data/physionet/mimic-iv-ecg-demo/0.1'
FULL = MAIN / 'data/physionet/mimic-iv-ecg/1.0/machine_measurements.csv'
OUT = Path(__file__).resolve().parent / 'task4' / 'ecg_labels.json'


def lead(rec, name):
    return rec.p_signal[:, rec.sig_name.index(name)].astype(float)


def alg_a(x, fs):
    """In-house read: R peaks from band-passed energy, RR stats, median-beat QT (tangent)."""
    b, a = signal.butter(2, [5 / (fs / 2), 20 / (fs / 2)], 'band')
    energy = np.gradient(signal.filtfilt(b, a, x)) ** 2
    energy = np.convolve(energy, np.ones(int(0.12 * fs)) / int(0.12 * fs), 'same')
    peaks, _ = signal.find_peaks(energy, height=0.3 * np.percentile(energy, 99), distance=int(0.3 * fs))
    if len(peaks) < 4:
        return None
    # snap to the largest absolute deflection near each energy peak
    raw = signal.filtfilt(*signal.butter(2, [0.5 / (fs / 2), 40 / (fs / 2)], 'band'), x)
    r = np.array([p - int(0.08 * fs) + np.argmax(np.abs(raw[max(0, p - int(0.08 * fs)):p + int(0.08 * fs)])) for p in peaks])
    rr = np.diff(r) / fs
    hr = 60 / np.median(rr)
    irregular = float(np.median(np.abs(np.diff(rr))) / np.median(rr)) if len(rr) > 2 else 0.0
    # median beat, QRS onset and T end (tangent at steepest T downslope intersecting baseline)
    pre, post = int(0.25 * fs), int(0.60 * fs)
    beats = [raw[i - pre:i + post] for i in r if i - pre >= 0 and i + post < len(raw)]
    if len(beats) < 3:
        return {'hr': hr, 'irregular': irregular, 'qt': None}
    m = np.median(beats, axis=0); m = m - np.median(m[:int(0.1 * fs)])
    d = np.gradient(m)
    thr = 0.15 * np.max(np.abs(d[pre - int(0.06 * fs):pre + int(0.04 * fs)]))
    onset = pre - int(0.06 * fs) + np.argmax(np.abs(d[pre - int(0.06 * fs):pre]) > thr)
    seg = slice(pre + int(0.10 * fs), min(len(m), pre + int(min(0.55, 0.8 * np.median(rr)) * fs)))
    tseg = m[seg]
    if len(tseg) < 10:
        return {'hr': hr, 'irregular': irregular, 'qt': None}
    tpk = seg.start + int(np.argmax(np.abs(tseg)))
    sign = np.sign(m[tpk])
    tail = sign * m[tpk:seg.stop]
    if len(tail) < 3:
        return {'hr': hr, 'irregular': irregular, 'qt': None}
    k = tpk + int(np.argmin(np.gradient(tail)))
    slope = np.gradient(m)[k]
    tend = k - m[k] / slope if slope != 0 else None
    qt = (tend - onset) / fs * 1000 if tend and tend > tpk else None
    return {'hr': hr, 'irregular': irregular, 'qt': qt}


def alg_b(x, fs):
    import neurokit2 as nk
    try:
        clean = nk.ecg_clean(x, sampling_rate=fs)
        _, info = nk.ecg_peaks(clean, sampling_rate=fs)
        r = np.asarray(info['ECG_R_Peaks'])
        rr = np.diff(r) / fs
        if len(rr) < 3:
            return None
        hr = 60 / np.median(rr)
        irregular = float(np.median(np.abs(np.diff(rr))) / np.median(rr))
        _, waves = nk.ecg_delineate(clean, r, sampling_rate=fs, method='dwt')
        on, off = np.asarray(waves.get('ECG_R_Onsets'), float), np.asarray(waves.get('ECG_T_Offsets'), float)
        qts = [(t - o) / fs * 1000 for o, t in zip(on, off) if np.isfinite(o) and np.isfinite(t) and 200 < (t - o) / fs * 1000 < 700]
        return {'hr': hr, 'irregular': irregular, 'qt': float(np.median(qts)) if len(qts) >= 3 else None}
    except Exception:
        return None


def qtc(qt, hr, formula):
    if qt is None or not hr:
        return None
    rr = 60 / hr
    return qt / rr ** 0.5 if formula == 'bazett' else qt / rr ** (1 / 3)


def machine_index(demo):
    subs = {r['subject_id'] for r in demo}
    idx = {}
    with open(FULL) as f:
        for r in csv.DictReader(f):
            if r['subject_id'] in subs:
                idx.setdefault((r['subject_id'], r['ecg_time'][:16]), []).append(r)
    return idx


def main():
    demo = list(csv.DictReader(open(DEMO / 'record_list.csv')))
    mach = machine_index(demo)
    out = {}
    for n, row in enumerate(demo):
        rec = wfdb.rdrecord(str(DEMO / row['path']))
        fs = rec.fs
        x = lead(rec, 'II')
        a, b = alg_a(x, fs), alg_b(x, fs)
        m = mach.get((row['subject_id'], row['ecg_time'][:16]), [])
        m = m[0] if len(m) == 1 else None
        text = ' | '.join(v for k, v in (m or {}).items() if k.startswith('report_') and v)
        mqt = None
        if m:
            try:
                mhr = 60000 / float(m['rr_interval']); mqt = float(m['t_end']) - float(m['qrs_onset'])
                if not (200 < mqt < 750): mqt = None
            except (ValueError, ZeroDivisionError):
                mhr, mqt = None, None
        else:
            mhr = None
        reads = {'A': a, 'B': b, 'machine': {'hr': mhr, 'qt': mqt, 'text': text} if m else None}
        # AF: machine statement plus both algorithms irregular; non-AF: machine sinus plus both regular
        flags = re.search(r'(?i)pac(ed|ing|emaker)|flutter|artifact|unsuitable|poor quality|baseline wander', text or '')
        irr = [r['irregular'] for r in (a, b) if r]
        af = bool(m) and re.search(r'(?i)atrial fibrillation', text) and len(irr) == 2 and min(irr) > 0.08
        sinus = bool(m) and re.search(r'(?i)sinus', text) and not re.search(r'(?i)fibrillation', text) and len(irr) == 2 and max(irr) < 0.04
        qtcs = [q for q in (qtc(r['qt'], r['hr'], f) for r in (a, b, reads['machine']) if r and r.get('qt') for f in ('bazett', 'fridericia')) if q]
        bz = [qtc(r['qt'], r['hr'], 'bazett') for r in (b, reads['machine']) if r and r.get('qt') and r.get('hr')]
        fr = [qtc(r['qt'], r['hr'], 'fridericia') for r in (b, reads['machine']) if r and r.get('qt') and r.get('hr')]
        long_qt = len(bz) == 2 and min(bz) >= 520 and min(fr) >= 500
        normal_qt = len(bz) == 2 and max(bz) <= 460 and max(fr) <= 460
        hrs = [r['hr'] for r in (a, b, reads['machine']) if r and r.get('hr')]
        hr_agree = len(hrs) >= 2 and max(hrs) - min(hrs) <= 5
        if flags or not m or not hr_agree:
            label = 'ambiguous'
        elif af:
            label = 'AF'
        elif sinus and long_qt:
            label = 'QTC_PROLONGED'
        elif sinus and normal_qt:
            label = 'NORMAL'
        else:
            label = 'ambiguous'
        out[row['study_id']] = {'subject_id': row['subject_id'], 'ecg_time': row['ecg_time'], 'path': row['path'], 'label': label,
                                'hr': round(float(np.median(hrs)), 1) if hrs else None,
                                'qtc_bazett': [round(v, 1) for v in bz], 'qtc_fridericia': [round(v, 1) for v in fr],
                                'reads': {k: ({kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()} if v else None)
                                          for k, v in reads.items()}}
        if n % 100 == 0:
            print(n, file=sys.stderr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + '\n')
    from collections import Counter
    c = Counter(v['label'] for v in out.values())
    print('labels:', dict(c))
    for lab in ('AF', 'QTC_PROLONGED', 'NORMAL'):
        print(lab, 'patients:', len({v['subject_id'] for v in out.values() if v['label'] == lab}))


if __name__ == '__main__':
    main()
