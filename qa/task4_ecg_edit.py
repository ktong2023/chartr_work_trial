"""Private ECG editing for Task 4: realistic QT lengthening and artifact controls.

QT lengthening mimics drug-induced (IKr-block) prolongation: every beat's ST-T segment is smoothly
time-stretched and the T wave broadens and flattens slightly, while R-R intervals, P waves and QRS
complexes keep their recorded timing. Only the slow component (< 25 Hz) is warped; the recording's own
high-frequency noise is added back on its original timeline, so the edited stretch keeps the texture of
the rest of the strip. The added time comes out of the isoelectric T-P segment.

Every ECG the clinic serves is written through `write_record`, edited or not, so file formatting is
identical. Run with the labeling venv (numpy, scipy, wfdb, neurokit2).
"""
import numpy as np
from scipy import signal
from scipy.interpolate import PchipInterpolator
import wfdb

FS = 500


def load(path):
    return wfdb.rdrecord(str(path), physical=False)


def write_record(rec, d_signal, out_dir, base_date=None, base_time=None):
    wfdb.wrsamp(rec.record_name, fs=rec.fs, units=rec.units, sig_name=rec.sig_name, d_signal=d_signal.astype(np.int64),
                fmt=rec.fmt, adc_gain=rec.adc_gain, baseline=rec.baseline, base_time=base_time or rec.base_time,
                base_date=base_date or rec.base_date, comments=rec.comments, write_dir=str(out_dir))


def fiducials(mv, fs=FS):
    """Median R-relative QRS onset, QRS end (J), T end and P onset from neurokit2 on lead II."""
    import neurokit2 as nk
    x = nk.ecg_clean(mv[:, 1], sampling_rate=fs)
    _, info = nk.ecg_peaks(x, sampling_rate=fs)
    r = np.asarray(info['ECG_R_Peaks'])
    _, w = nk.ecg_delineate(x, r, sampling_rate=fs, method='dwt')
    def rel(key):
        v = np.asarray(w.get(key), float)
        d = v - r[:len(v)]
        d = d[np.isfinite(d)]
        return float(np.median(d)) if len(d) >= 3 else None
    return r, {'q_on': rel('ECG_R_Onsets'), 'j': rel('ECG_R_Offsets'), 't_end': rel('ECG_T_Offsets'), 'p_on': rel('ECG_P_Onsets')}


def lengthen_qt(rec, target_qtc_bazett, t_scale=0.92, fs=FS):
    """Return (new d_signal, info). Stretch ST-T so Bazett QTc (QRS onset to T end) reaches the target."""
    d = rec.d_signal.astype(float)
    gain = np.asarray(rec.adc_gain, float)
    mv = d / gain
    r, f = fiducials(mv, fs)
    if None in (f['q_on'], f['j'], f['t_end'], f['p_on']) or len(r) < 4:
        raise ValueError('fiducials unavailable')
    rr = float(np.median(np.diff(r)))
    qt = (f['t_end'] - f['q_on']) / fs
    delta = int(round((target_qtc_bazett / 1000 * np.sqrt(rr / fs) - qt) * fs))
    guard = int(-f['p_on'] + 0.04 * fs)                      # keep clear of the next P wave
    b, a = signal.butter(3, 25 / (fs / 2))
    slow = signal.filtfilt(b, a, mv, axis=0)
    fast = mv - slow
    out = slow.copy()
    n = len(mv)
    # beats including a virtual one before the strip so the first partial T wave is treated too
    beats = [int(r[0] - rr)] + list(r)
    for i, ri in enumerate(beats):
        nxt = beats[i + 1] if i + 1 < len(beats) else int(ri + rr)
        j0, t0 = ri + int(f['j']), ri + int(f['t_end'])
        a0 = nxt - guard
        if a0 - (t0 + delta) < int(0.06 * fs):
            raise ValueError('not enough T-P room for this heart rate')
        lo, hi = max(j0, 0), min(a0, n - 1)
        if hi - lo < 10:
            continue
        # output-time -> input-time map: identity at J and at the pre-P anchor; T end moves by +delta
        s0 = j0 + int(0.02 * fs)
        knots_out = np.array([j0, s0, t0 + delta, a0], float)
        knots_in = np.array([j0, s0, t0, a0], float)
        warp = PchipInterpolator(knots_out, knots_in)
        t_out = np.arange(lo, hi + 1)
        t_in = np.clip(warp(t_out), 0, n - 1)
        for c in range(mv.shape[1]):
            seg = np.interp(t_in, np.arange(n), slow[:, c])
            base = np.interp(t_out, [lo, hi], [slow[lo, c], slow[hi, c]])
            # flatten the stretched T slightly with a smooth window over J..T end(new)
            win = np.clip((t_out - s0) / (0.03 * fs), 0, 1) * np.clip((t0 + delta - t_out) / (0.05 * fs) + 1, 0, 1)
            out[lo:hi + 1, c] = base + (seg - base) * (1 - (1 - t_scale) * win)
    new = np.round((out + fast) * gain).astype(np.int64)
    return new, {'delta_ms': delta / fs * 1000, 'rr_ms': rr / fs * 1000, 'qt_before_ms': qt * 1000, 'fiducials': f}


def add_artifact(rec, kind, seed=0, fs=FS):
    """Realistic artifact on a copy: baseline wander, muscle (EMG) noise bursts, motion spikes, or LA/RA reversal."""
    rng = np.random.default_rng(seed)
    d = rec.d_signal.astype(float); gain = np.asarray(rec.adc_gain, float); mv = d / gain
    n, t = len(mv), np.arange(len(mv)) / fs
    if kind == 'wander':
        f0 = rng.uniform(0.15, 0.4)
        mv = mv + 0.6 * np.sin(2 * np.pi * f0 * t + rng.uniform(0, 6))[:, None] * rng.uniform(0.5, 1.0, mv.shape[1])
    elif kind == 'emg':
        b, a = signal.butter(4, [20 / (fs / 2), 150 / (fs / 2)], 'band')
        noise = signal.filtfilt(b, a, rng.normal(0, 1, mv.shape), axis=0)
        env = np.zeros(n)
        for _ in range(rng.integers(3, 6)):
            c = rng.integers(0, n); w = rng.integers(int(0.3 * fs), int(1.2 * fs))
            env[max(0, c - w):c + w] = 1
        env = np.convolve(env, np.hanning(int(0.2 * fs)) / np.hanning(int(0.2 * fs)).sum(), 'same')
        mv = mv + 0.12 * noise * env[:, None] / noise.std()
    elif kind == 'motion':
        for _ in range(rng.integers(4, 8)):
            c = rng.integers(int(0.2 * fs), n - int(0.2 * fs)); w = int(rng.uniform(0.04, 0.09) * fs)
            bump = np.hanning(2 * w) * rng.uniform(0.6, 1.4) * rng.choice([-1, 1])
            mv[c - w:c + w] += bump[:, None] * rng.uniform(0.4, 1.0, mv.shape[1])
    elif kind == 'la_ra':
        # limb lead reversal: I inverted, II<->III, aVR<->aVL (sig order I II III aVR aVF aVL V1..V6)
        mv = mv.copy(); I, II, III, aVR, aVF, aVL = (mv[:, k].copy() for k in range(6))
        mv[:, 0], mv[:, 1], mv[:, 2], mv[:, 3], mv[:, 5] = -I, III, II, aVL, aVR
    return np.round(mv * gain).astype(np.int64)
