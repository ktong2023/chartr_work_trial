"""Task 4 data layer: load the pinned MIMIC-IV demo datasets and re-anchor each patient's timeline.

MIMIC shifts every patient into a different future year (2110-2201 in the demo), so a single clinic
evaluation date needs a per-patient re-anchor. Each patient's whole record, ECGs included, moves by the
whole number of weeks closest to a whole number of years (weekday exact, season within 3 days, as MIMIC's
own shift preserves both) so that their latest real activity lands 3-27 months before the evaluation date. Wall-clock times keep their local value and get
the America/New_York offset valid on the new date, matching MIMIC's own local-time convention.

Private. The derived database is shared under ODbL v1.0 with attribution (see the task README).
"""
import csv, gzip, hashlib, json, re
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

MAIN = Path(__file__).resolve().parents[1]
FHIR_DIR = MAIN / 'data/physionet/mimic-iv-fhir-demo/2.1.0/fhir'
ECG_DIR = MAIN / 'data/physionet/mimic-iv-ecg-demo/0.1'
TZ = ZoneInfo('America/New_York')
EVAL = dt.datetime(2026, 9, 24, 12, 0, tzinfo=TZ)
YEAR = 365.2425
# SHA-256 of the pinned inputs (verified against PhysioNet's SHA256SUMS.txt on download).
PINNED = {'fhir-demo-2.1.0': 'SHA256SUMS.txt (30 files, all OK)', 'ecg-demo-0.1': 'SHA256SUMS.txt (1,321 files, all OK)',
          'ecg-1.0/machine_measurements.csv': '56f6b1413221bce95bd6f48b28ca1acf27ae0b073d6f2c1d12f3af7500eabbb6'}

DATETIME = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(T(\d{2}):(\d{2})(:(\d{2})(\.\d+)?)?([+-]\d{2}:\d{2}|Z)?)?$')


def load_demo():
    """All demo resources grouped by type file, plus a patient-id -> MIMIC subject_id map."""
    files = sorted(FHIR_DIR.glob('*.ndjson.gz'))
    data = {f.name.replace('.ndjson.gz', ''): [json.loads(l) for l in gzip.open(f, 'rt')] for f in files}
    subject = {p['id']: p['identifier'][0]['value'] for p in data['MimicPatient']}
    return data, subject


def owner(resource, subject):
    ref = (resource.get('subject') or resource.get('patient') or {}).get('reference', '')
    return subject.get(ref.split('/')[-1])


def iter_dates(obj):
    if isinstance(obj, dict):
        for v in obj.values(): yield from iter_dates(v)
    elif isinstance(obj, list):
        for v in obj: yield from iter_dates(v)
    elif isinstance(obj, str) and DATETIME.match(obj):
        yield obj


def shift_value(value, days):
    m = DATETIME.match(value)
    if not m:
        return value
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    day = dt.date(y, mo, d) + dt.timedelta(days=days)
    if not m.group(4):
        return day.isoformat()
    hh, mm = int(m.group(5)), int(m.group(6))
    ss = m.group(8) or None
    frac = m.group(9) or ''
    tail = m.group(10)
    body = f'{day.isoformat()}T{hh:02d}:{mm:02d}' + (f':{ss}{frac}' if ss is not None else '')
    if tail is None:
        return body
    if tail == 'Z':
        return body + 'Z'
    local = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ)
    off = local.utcoffset()
    sign = '-' if off < dt.timedelta(0) else '+'
    mins = abs(int(off.total_seconds())) // 60
    return body + f'{sign}{mins // 60:02d}:{mins % 60:02d}'


def shift_resource(obj, days):
    if isinstance(obj, dict):
        return {k: shift_resource(v, days) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shift_resource(v, days) for v in obj]
    if isinstance(obj, str):
        return shift_value(obj, days)
    return obj


def ecg_records():
    return list(csv.DictReader(open(ECG_DIR / 'record_list.csv')))


def anchors(data, subject, ecgs):
    """Per-patient day offset (whole weeks nearest whole years) placing latest real activity 3-27 months before EVAL."""
    last = {}
    for rows in data.values():
        for r in rows:
            s = owner(r, subject) if r.get('resourceType') != 'Patient' else r['identifier'][0]['value']
            if not s:
                continue
            for v in iter_dates(r):
                if r.get('resourceType') == 'Patient' and v == r.get('birthDate'):
                    continue
                last[s] = max(last.get(s, ''), v[:10])
    for e in ecgs:
        last[e['subject_id']] = max(last.get(e['subject_id'], ''), e['ecg_time'][:10])
    out = {}
    for s, v in last.items():
        seed = int(hashlib.sha256(('anchor:' + s).encode()).hexdigest(), 16)
        latest_allowed = EVAL.date() - dt.timedelta(days=97)
        years = int((latest_allowed - dt.date.fromisoformat(v)).days // YEAR) - seed % 2
        out[s] = int(round(years * YEAR / 7)) * 7        # whole weeks nearest to whole years
        landed = dt.date.fromisoformat(v) + dt.timedelta(days=out[s])
        assert EVAL.date() - dt.timedelta(days=90 + 3 * 366) < landed <= EVAL.date() - dt.timedelta(days=90), s
    return out


def shifted_ecgs(ecgs, offsets):
    out = []
    for e in ecgs:
        t = dt.datetime.fromisoformat(e['ecg_time']) + dt.timedelta(days=offsets[e['subject_id']])
        out.append({**e, 'ecg_time': t.isoformat(sep=' ')})
    return out
