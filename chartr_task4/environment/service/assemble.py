"""Build the clinic's read-only source database from pinned PhysioNet data plus the task overlay.

Inputs (all pinned):
  * MIMIC-IV Clinical Database Demo on FHIR v2.1.0 (ODbL v1.0): fhir/*.ndjson.gz
  * MIMIC-IV-ECG Demo v0.1 (ODbL v1.0): the WFDB records the clinic's ECG system holds
  * overlay/: per-patient re-anchoring offsets, added and removed resources, the ECG catalog, and ECG
    edits stored as little-endian int32 sample differences (ecg_deltas/<study>.bin)
Output: sources.sqlite (resources + ECG catalog + digest) and an ECG directory, identical on every build.

Each patient's record, ECGs included, moves by a whole number of weeks close to a whole number of years;
wall-clock times keep their local value and take the America/New_York offset valid on the new date.
"""
import base64, gzip, hashlib, json, re, sqlite3, sys, zlib
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/New_York')
DATETIME = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(T(\d{2}):(\d{2})(:(\d{2})(\.\d+)?)?([+-]\d{2}:\d{2}|Z)?)?$')
DATE_FIELDS = ('effectiveDateTime', 'authoredOn', 'whenHandedOver', 'issued', 'date', 'recordedDate', 'onsetDateTime')


def shift_value(value, days):
    m = DATETIME.match(value)
    if not m:
        return value
    day = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) + dt.timedelta(days=days)
    if not m.group(4):
        return day.isoformat()
    hh, mm, ss, frac, tail = int(m.group(5)), int(m.group(6)), m.group(8), m.group(9) or '', m.group(10)
    body = f'{day.isoformat()}T{hh:02d}:{mm:02d}' + (f':{ss}{frac}' if ss is not None else '')
    if tail is None or tail == 'Z':
        return body + (tail or '')
    off = dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ).utcoffset()
    sign, mins = ('-' if off < dt.timedelta(0) else '+'), abs(int(off.total_seconds())) // 60
    return body + f'{sign}{mins // 60:02d}:{mins % 60:02d}'


def shift(obj, days):
    if isinstance(obj, dict):
        return {k: shift(v, days) for k, v in obj.items()}
    if isinstance(obj, list):
        return [shift(v, days) for v in obj]
    return shift_value(obj, days) if isinstance(obj, str) else obj


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def patient_of(r):
    if r['resourceType'] == 'Patient':
        return r['id']
    ref = (r.get('subject') or r.get('patient') or {}).get('reference', '')
    return ref.split('/')[-1] or None


def when_of(r):
    for k in DATE_FIELDS:
        if isinstance(r.get(k), str):
            return r[k]
    for k, sub in (('period', 'start'), ('effectivePeriod', 'start'), ('collection', 'collectedDateTime')):
        if isinstance(r.get(k), dict) and r[k].get(sub):
            return r[k][sub]
    return None


def code_of(r):
    for key in ('code', 'medicationCodeableConcept', 'type'):
        v = r.get(key)
        if isinstance(v, list):
            v = v[0] if v else None
        if isinstance(v, dict) and v.get('coding'):
            return v['coding'][0].get('code')
    return None


def real_resources(fhir_dir, overlay):
    """Yield the demo's resources, re-anchored, minus the overlay's removals."""
    offsets = overlay['offsets']                  # FHIR patient id -> day offset
    removed = set(overlay['removed'])
    for f in sorted(Path(fhir_dir).glob('*.ndjson.gz')):
        with gzip.open(f, 'rt') as handle:
            for line in handle:
                r = json.loads(line)
                if r['id'] in removed:
                    continue
                p = patient_of(r)
                yield shift(r, offsets[p]) if p in offsets else r


def build(fhir_dir, ecg_dir, overlay_dir, out_db, out_ecg):
    overlay_dir = Path(overlay_dir)
    overlay = json.loads((overlay_dir / 'overlay.json').read_text())
    added = [json.loads(l) for l in gzip.open(overlay_dir / 'added.ndjson.gz', 'rt')]
    out_db = Path(out_db)
    out_db.parent.mkdir(parents=True, exist_ok=True)
    if out_db.exists():
        out_db.unlink()
    db = sqlite3.connect(out_db)
    db.executescript('''
        CREATE TABLE resource (id TEXT PRIMARY KEY, type TEXT NOT NULL, patient TEXT, time TEXT, code TEXT, json BLOB NOT NULL);
        CREATE TABLE ecg (id TEXT PRIMARY KEY, patient TEXT NOT NULL, time TEXT NOT NULL, path TEXT NOT NULL);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    ''')
    batch = []
    for r in list(real_resources(fhir_dir, overlay)) + added:
        batch.append((r['id'], r['resourceType'], patient_of(r), when_of(r), code_of(r), zlib.compress(canonical(r).encode(), 6)))
        if len(batch) >= 20000:
            db.executemany('INSERT INTO resource VALUES (?,?,?,?,?,?)', batch); batch = []
    db.executemany('INSERT INTO resource VALUES (?,?,?,?,?,?)', batch)
    # Covering the full sort key (time, id) keeps every search page an index walk instead of a sort.
    db.execute('CREATE INDEX by_patient ON resource (patient, type, time, id)')
    db.execute('CREATE INDEX by_type ON resource (type, time, id)')
    db.execute('CREATE INDEX by_code ON resource (type, code, time, id)')
    write_ecgs(ecg_dir, overlay_dir, overlay, db, Path(out_ecg))
    h = hashlib.sha256()
    for row in db.execute('SELECT id, json FROM resource ORDER BY id'):
        h.update(row[0].encode()); h.update(b'\0'); h.update(zlib.decompress(row[1])); h.update(b'\n')
    for row in db.execute('SELECT id, patient, time, path FROM ecg ORDER BY id'):
        h.update('|'.join(row).encode()); h.update(b'\n')
    for p in sorted(Path(out_ecg).rglob('*')):
        if p.is_file():
            h.update(p.relative_to(out_ecg).as_posix().encode()); h.update(p.read_bytes())
    db.execute('INSERT INTO meta VALUES (?,?)', ('sources_digest', h.hexdigest()))
    db.commit(); db.close()
    return h.hexdigest()


def write_ecgs(ecg_dir, overlay_dir, overlay, db, out):
    """Write each catalogued ECG (WFDB format 16) with its re-anchored header date and any stored integer edit.

    Standard library only: format 16 is little-endian int16 interleaved by sample; each signal line carries the
    first sample and the column sum mod 65536. Comment lines are dropped for every record.
    """
    import array
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for e in overlay['ecg_catalog']:
        src = Path(ecg_dir) / e['path']
        header = [l for l in src.with_suffix('.hea').read_text().splitlines() if l and not l.startswith('#')]
        name, nsig, fs, nsamp = header[0].split()[:4]
        nsig, nsamp = int(nsig), int(nsamp)
        samples = array.array('h'); samples.frombytes(src.with_suffix('.dat').read_bytes())
        if sys.byteorder != 'little':
            samples.byteswap()
        delta = overlay_dir / 'ecg_deltas' / (e['study_id'] + '.bin')
        if delta.exists():
            diff = array.array('i'); diff.frombytes(delta.read_bytes())
            if sys.byteorder != 'little':
                diff.byteswap()
            samples = array.array('h', (a + b for a, b in zip(samples, diff)))
        when = dt.datetime.fromisoformat(e['ecg_time'])
        lines = [f"{name} {nsig} {fs} {nsamp} {when.strftime('%H:%M:%S')} {when.strftime('%d/%m/%Y')}"]
        for i, line in enumerate(header[1:1 + nsig]):
            f = line.split()
            col = samples[i::nsig]
            f[5], f[6] = str(col[0]), str(sum(col) % 65536)
            lines.append(' '.join(f))
        rec_dir = out / e['study_id']
        rec_dir.mkdir(parents=True, exist_ok=True)
        data = array.array('h', samples)
        if sys.byteorder != 'little':
            data.byteswap()
        (rec_dir / (name + '.dat')).write_bytes(data.tobytes())
        (rec_dir / (name + '.hea')).write_text('\n'.join(lines) + '\n')
        rows.append((e['study_id'], e['patient'], e['ecg_time'], e['study_id']))
    db.executemany('INSERT INTO ecg VALUES (?,?,?,?)', rows)


if __name__ == '__main__':
    print(build(*sys.argv[1:6]))
