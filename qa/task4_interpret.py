"""Private three-reader ECG interpretation for Task 4 v0.3 (designer aid; never reaches the agent).

For every MIMIC-IV-ECG Demo recording (with the catalog's edits applied) three independent readers measure the
fields the agent must report:
  M. the ECG cart (open MIMIC-IV-ECG v1.0 machine_measurements.csv): statements, RR, P onset, QRS onset/end,
     T end, QRS axis;
  N. neurokit2 DWT delineation on lead II (per-beat medians);
  G. an in-house 12-lead global method: median beats aligned on R, spatial velocity for QRS onset/end, RMS
     magnitude for P onset and T end (tangent), QRS axis from net QRS area in leads I and aVF, and a simple
     V1/I/V6 morphology read for bundle-branch block.
Machine intervals are not used for an edited QT (the edit postdates the cart). Output: task4/ecg_reads.json.
Run with the labeling venv:  data/.labvenv/bin/python qa/task4_interpret.py
"""
import csv, json, math, re, sys, warnings
from pathlib import Path
import numpy as np
from scipy import signal
import wfdb

warnings.filterwarnings('ignore')
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import task4_ecg_labels as L

FS = 500
OUT = HERE / 'task4' / 'ecg_reads.json'


def num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if v >= 29999 or v <= -29999 else v


def machine_read(m):
    if not m:
        return None
    text = ' | '.join(v for k, v in m.items() if k.startswith('report_') and v)
    rr, p_on, q_on, q_end, t_end, axis = (num(m[k]) for k in ('rr_interval', 'p_onset', 'qrs_onset', 'qrs_end', 't_end', 'qrs_axis'))
    out = {'text': text, 'hr': 60000 / rr if rr else None, 'axis': axis}
    out['pr'] = q_on - p_on if p_on is not None and q_on is not None and 60 < q_on - p_on < 400 else None
    out['qrs'] = q_end - q_on if q_end is not None and q_on is not None and 40 < q_end - q_on < 250 else None
    out['qt'] = t_end - q_on if t_end is not None and q_on is not None and 200 < t_end - q_on < 750 else None
    return out


def nk_read(x):
    import neurokit2 as nk
    try:
        clean = nk.ecg_clean(x, sampling_rate=FS)
        _, info = nk.ecg_peaks(clean, sampling_rate=FS)
        r = np.asarray(info['ECG_R_Peaks'])
        if len(r) < 4:
            return None
        _, w = nk.ecg_delineate(clean, r, sampling_rate=FS, method='dwt')
        g = lambda k: np.asarray(w.get(k, []), float)
        p_on, r_on, r_off, t_off = g('ECG_P_Onsets'), g('ECG_R_Onsets'), g('ECG_R_Offsets'), g('ECG_T_Offsets')
        def med(vals, lo, hi):
            v = [x for x in vals if np.isfinite(x) and lo < x < hi]
            return float(np.median(v)) if len(v) >= 3 else None
        n = min(len(p_on), len(r_on), len(r_off), len(t_off))
        return {'hr': 60 / np.median(np.diff(r) / FS),
                'pr': med([(r_on[i] - p_on[i]) / FS * 1000 for i in range(n)], 60, 400),
                'qrs': med([(r_off[i] - r_on[i]) / FS * 1000 for i in range(n)], 40, 250),
                'qt': med([(t_off[i] - r_on[i]) / FS * 1000 for i in range(n)], 200, 750)}
    except Exception:
        return None


def global_read(sig, names):
    """sig: samples x 12 (mV), columns in `names` order. Median-beat global delineation."""
    ix = {n: i for i, n in enumerate(names)}
    b, a = signal.butter(2, [0.5 / (FS / 2), 40 / (FS / 2)], 'band')
    X = signal.filtfilt(b, a, sig, axis=0)
    import neurokit2 as nk
    try:
        _, info = nk.ecg_peaks(nk.ecg_clean(sig[:, ix['II']], sampling_rate=FS), sampling_rate=FS)
        r = np.asarray(info['ECG_R_Peaks'])
    except Exception:
        return None
    if len(r) < 4:
        return None
    rr = float(np.median(np.diff(r))) / FS
    pre, post = int(0.40 * FS), int(min(0.70, 0.95 * rr) * FS)
    beats = np.array([X[i - pre:i + post] for i in r if i - pre >= 0 and i + post < len(X)])
    if len(beats) < 3:
        return None
    M = np.median(beats, axis=0)                                   # L x 12
    # QRS: spatial velocity around the R peak
    sv = np.sqrt((np.diff(M, axis=0) ** 2).sum(axis=1))
    win = slice(pre - int(0.08 * FS), pre + int(0.08 * FS))
    pk = win.start + int(np.argmax(sv[win]))
    base_sv = np.percentile(sv[:pre - int(0.15 * FS)], 50)
    thr = base_sv + 0.12 * (sv[pk] - base_sv)
    thr_off = base_sv + 0.06 * (sv[pk] - base_sv)      # terminal forces (e.g. slurred R' or S) are slow
    on = pk
    while on > pk - int(0.12 * FS) and sv[on] > thr:
        on -= 1
    off = pk
    while off < min(len(sv) - 1, pk + int(0.20 * FS)) and not (sv[off:off + 10] < thr_off).all():
        off += 1
    qrs = (off - on) / FS * 1000
    # baseline: median of the PR segment region just before QRS onset
    base = np.median(M[max(0, on - int(0.03 * FS)):on], axis=0)
    Mb = M - base
    rms = np.sqrt((Mb ** 2).mean(axis=1))
    # T end: tangent on RMS after T peak
    t0, t1 = off + int(0.06 * FS), min(len(rms) - 2, on + int(min(0.62, 0.9 * rr) * FS))
    qt = None
    if t1 - t0 > 20:
        tp = t0 + int(np.argmax(rms[t0:t1]))
        d = np.gradient(rms)
        k = tp + int(np.argmin(d[tp:t1])) if t1 > tp + 2 else None
        if k is not None and d[k] < 0:
            floor = np.percentile(rms[t0:], 5)
            tend = k + (rms[k] - floor) / -d[k]
            if tend > tp:
                qt = (tend - on) / FS * 1000
    # P onset on lead II (15 Hz low-pass), referenced to the PR segment just before QRS onset
    bl, al = signal.butter(2, 15 / (FS / 2))
    II = signal.filtfilt(bl, al, Mb[:, ix['II']])
    lo, hi = max(0, on - int(0.30 * FS)), on - int(0.05 * FS)
    pr = None
    if hi - lo > 20:
        seg = II[lo:hi] - II[hi]
        ppk = int(np.argmax(np.abs(seg)))
        amp = seg[ppk]
        tp = II[max(0, lo - int(0.06 * FS)):lo + 1] - II[hi]
        if abs(amp) > 0.04 and (len(tp) < 5 or abs(amp) > 3 * np.std(tp)):
            k = ppk
            while k > 0 and abs(seg[k]) > 0.12 * abs(amp) and np.sign(seg[k]) == np.sign(amp):
                k -= 1
            if k > 0:
                pr = (on - (lo + k)) / FS * 1000
    # axis from net QRS area in I and aVF; amplitude axis as a cross-check
    area = Mb[on:off + 1].sum(axis=0)
    axis = math.degrees(math.atan2(area[ix['aVF']], area[ix['I']]))
    amp = Mb[on:off + 1].max(axis=0) + Mb[on:off + 1].min(axis=0)
    axis_amp = math.degrees(math.atan2(amp[ix['aVF']], amp[ix['I']]))
    # bundle-branch morphology (only meaningful when QRS is wide)
    v1 = Mb[on:off + 1, ix['V1']]; i_ = Mb[on:off + 1, ix['I']]; v6 = Mb[on:off + 1, ix['V6']]
    third = max(1, len(v1) // 3)
    morph = None
    if qrs >= 110:
        terminal_v1 = v1[-third:].mean()
        if terminal_v1 > 0.05 and v1.max() > abs(v1.min()) * 0.5:
            morph = 'RBBB'
        elif v1.min() < -0.3 and abs(v1.min()) > 2 * max(v1.max(), 0.01) and i_.max() > abs(i_.min()) and v6.max() > abs(v6.min()):
            morph = 'LBBB'
        else:
            morph = 'IVCD'
    return {'hr': 60 / rr, 'pr': pr, 'qrs': qrs, 'qt': qt, 'axis': axis, 'axis_amp': axis_amp, 'bbb_morphology': morph}


def rhythm_from_text(text):
    t = (text or '').lower()
    if re.search(r'pac(ed|ing|emaker)', t):
        return 'PACED'
    if 'flutter' in t:
        return 'ATRIAL_FLUTTER'
    if 'fibrillation' in t:
        return 'AF'
    if 'sinus' in t:
        return 'SINUS'
    return None


def conduction_from_text(text):
    t = (text or '').lower()
    out = set()
    if re.search(r'right bundle branch block|\brbbb\b', t) and 'incomplete right' not in t:
        out.add('RBBB')
    if re.search(r'left bundle branch block|\blbbb\b', t):
        out.add('LBBB')
    if re.search(r'(?<!borderline )1st degree a-?v block|first degree a-?v block|prolonged pr interval', t):
        out.add('FIRST_DEGREE_AV_BLOCK')
    return sorted(out)


def main():
    demo = list(csv.DictReader(open(L.DEMO / 'record_list.csv')))
    mach = L.machine_index(demo)
    labels = json.loads((HERE / 'task4/ecg_labels.json').read_text())
    deltas = np.load(HERE / 'task4/ecg_deltas.npz')
    truth = json.loads((HERE / 'task4/ecg_truth.json').read_text())
    out = {}
    for n, row in enumerate(demo):
        sid = row['study_id']
        rec = wfdb.rdrecord(str(L.DEMO / row['path']))
        d = rec.d_signal.astype(np.int64) if rec.d_signal is not None else None
        if d is None:
            rec = wfdb.rdrecord(str(L.DEMO / row['path']), physical=False); d = rec.d_signal.astype(np.int64)
        if sid in deltas.files:
            d = d + deltas[sid].reshape(d.shape)
        sig = d / np.asarray(rec.adc_gain)
        m = mach.get((row['subject_id'], row['ecg_time'][:16]), [])
        mr = machine_read(m[0] if len(m) == 1 else None)
        edited_qt = (truth.get(sid, {}).get('edit') or '').startswith('qt_')
        if mr and edited_qt:
            mr['qt'] = None
        out[sid] = {'subject_id': row['subject_id'], 'M': mr, 'N': nk_read(sig[:, rec.sig_name.index('II')]), 'G': global_read(sig, rec.sig_name),
                    'irregular': [x['irregular'] for x in (labels[sid]['reads'].get('A'), labels[sid]['reads'].get('B')) if x],
                    'machine_rhythm': rhythm_from_text(mr['text']) if mr else None,
                    'machine_conduction': conduction_from_text(mr['text']) if mr else None}
        if n % 100 == 0:
            print(n, file=sys.stderr)
    OUT.write_text(json.dumps(out, indent=1, default=lambda v: round(float(v), 1)) + '\n')
    print('wrote', len(out))


if __name__ == '__main__':
    main()
