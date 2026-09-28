"""Task 4 clinic service state: read-only sources (built at image build) plus a per-trial state database.

Sources: /data/sources.sqlite (resources, ECG catalog, content digest) and /data/ecg/<id>/*.{hea,dat}.
State:   /state/state.sqlite (review items, ECG interpretations, audit, metadata). A fresh container is a fresh trial.
The service checks operational validity (types, vocabularies, record ownership) and never correctness.
"""
from contextlib import contextmanager
import base64, json, re, sqlite3, uuid, zlib
from urllib.parse import parse_qsl
from pathlib import Path

VERSION = 'chartr-task4-0.3.4'
NOW = '2026-09-24T12:00:00-04:00'
PAGE = 1000
CATEGORIES = {'ANTICOAGULATION': {'UNTREATED_AF', 'ANTICOAGULANT_WITH_CONTRAINDICATION'},
              'QT_SAFETY': {'PROLONGED_QTC_ON_WATCH_LIST_DRUG'},
              'FOLLOW_UP': {'ECG_AFTER_WATCH_LIST_START', 'INR_AFTER_WARFARIN_DOSE_CHANGE'},
              'CONTRADICTION': {'DUAL_ANTICOAGULATION', 'RHYTHM_DOCUMENTATION_CONFLICT'}}
FOLLOW_UP_STATUS = {'completed', 'overdue', 'not_due', 'cannot_determine'}
RISK_FACTORS = {'CHF', 'HYPERTENSION', 'AGE_65_74', 'AGE_75_PLUS', 'DIABETES', 'STROKE_TIA', 'VASCULAR', 'FEMALE'}
RHYTHMS = {'SINUS', 'AF', 'ATRIAL_FLUTTER', 'PACED', 'OTHER'}
AXES = {'NORMAL', 'LEFT', 'RIGHT', 'EXTREME'}
CONDUCTION = {'RBBB', 'LBBB', 'FIRST_DEGREE_AV_BLOCK'}
CHANGES = {'NEW_AF', 'RESOLVED_AF', 'NEW_ATRIAL_FLUTTER', 'RESOLVED_ATRIAL_FLUTTER', 'NEW_PACED_RHYTHM', 'RESOLVED_PACED_RHYTHM',
           'NEW_BUNDLE_BRANCH_BLOCK', 'RESOLVED_BUNDLE_BRANCH_BLOCK', 'QTC_INCREASE_60', 'QTC_DECREASE_60'}
ID_FIELDS = ('anticoagulant', 'contraindication', 'ecg', 'qt_drug', 'potassium', 'magnesium', 'trigger', 'requirement', 'completion_record')
LIST_FIELDS = ('af_evidence', 'records')
ITEM_FIELDS = ('patient', 'category', 'reason', 'status', 'af_evidence', 'risk_score', 'risk_factors', 'anticoagulant', 'contraindication',
               'records', 'ecg', 'qtc_ms', 'heart_rate', 'qt_drug', 'potassium', 'magnesium', 'trigger', 'requirement', 'due_date',
               'completion_record', 'explanation')
INTERP_FIELDS = ('ecg', 'rhythm', 'ventricular_rate', 'pr_ms', 'qrs_ms', 'qtc_ms', 'axis', 'conduction', 'prior_ecg', 'changes', 'explanation')
DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
COUNTS = {}
TEXT = re.compile(r'^[\x09\x0a\x0d\x20-\U0010ffff]*$')


class InvalidRequest(ValueError):
    pass


class Store:
    def __init__(self, state_path, sources_path='/data/sources.sqlite', ecg_dir='/data/ecg'):
        self.path, self.sources_path, self.ecg_dir = Path(state_path), Path(sources_path), Path(ecg_dir)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        db.execute('PRAGMA busy_timeout=20000')
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def sources(self):
        db = sqlite3.connect(f'file:{self.sources_path}?mode=ro&immutable=1', uri=True)
        try:
            yield db
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise RuntimeError('Refusing to reuse an existing trial database')
        with self.sources() as src:
            digest = src.execute("SELECT value FROM meta WHERE key='sources_digest'").fetchone()[0]
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE item (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE interpretation (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE audit (seq INTEGER PRIMARY KEY, event TEXT NOT NULL);
            ''')
            db.executemany('INSERT INTO meta VALUES (?,?)', [(k, json.dumps(v)) for k, v in {
                'version': VERSION, 'evaluation_time': NOW, 'sources_digest': digest, 'nonce': str(uuid.uuid4()),
                'trial_id': None, 'frozen': False, 'faults': 0, 'next_item': 1, 'next_interpretation': 1}.items()])

    @staticmethod
    def meta(db):
        return {k: json.loads(v) for k, v in db.execute('SELECT key, value FROM meta')}

    @staticmethod
    def set_meta(db, key, value):
        db.execute('UPDATE meta SET value=? WHERE key=?', (json.dumps(value), key))

    def state(self, db):
        return {'items': [json.loads(b) for (b,) in db.execute('SELECT body FROM item ORDER BY id')],
                'interpretations': [json.loads(b) for (b,) in db.execute('SELECT body FROM interpretation ORDER BY id')]}

    def attest(self, trial_id):
        with self.connect() as db:
            m = self.meta(db)
            if m['trial_id'] is not None or m['frozen']:
                raise RuntimeError('Attestation must happen once, before the trial')
            self.set_meta(db, 'trial_id', trial_id)
            return {'trial_id': trial_id, 'nonce': m['nonce'], 'version': m['version'], 'evaluation_time': m['evaluation_time'],
                    'sources_digest': m['sources_digest']}

    def collect(self):
        with self.connect() as db:
            self.set_meta(db, 'frozen', True)
            events = [json.loads(e) for (e,) in db.execute('SELECT event FROM audit ORDER BY seq')]
            return {'metadata': self.meta(db), **self.state(db), 'audit': events}

    # ------------------------------------------------------------------ request handling
    def request(self, method, path, data=None):
        with self.connect() as db:
            m = self.meta(db)
            if m['frozen']:
                return 409, {'error': 'Evaluation state is frozen'}
            before = self.state(db)
            seq = db.execute('SELECT COALESCE(MAX(seq), 0) + 1 FROM audit').fetchone()[0]
            try:
                response = self.operation(db, method, path, data)
                status = 200
            except InvalidRequest as exc:
                status, response = 400, {'error': str(exc)}
            except Exception:
                self.set_meta(db, 'faults', m['faults'] + 1)
                status, response = 500, {'error': 'Internal service error; evaluation infrastructure fault'}
            after = self.state(db) if method != 'GET' else before
            db.execute('INSERT INTO audit VALUES (?,?)', (seq, json.dumps({
                'seq': seq, 'method': method, 'path': path.split('?')[0], 'status': status,
                'arguments': data if method != 'GET' else None, 'before': before if method != 'GET' else None,
                'after': after if method != 'GET' else None})))
            return status, response

    def operation(self, db, method, path, data):
        route, _, query = path.partition('?')
        params = dict(parse_qsl(query))
        parts = [p for p in route.split('/') if p]
        if method == 'GET':
            if parts == ['patients']:
                return self.search('Patient', None, params)
            if parts == ['search']:
                if 'type' not in params:
                    raise InvalidRequest('search requires type')
                return self.search(params['type'], params.get('patient'), params)
            if parts == ['documents']:
                return self.search('DocumentReference', '', params)
            if parts == ['ecg']:
                with self.sources() as src:
                    rows = src.execute('SELECT id, patient, time FROM ecg WHERE (? IS NULL OR patient = ?) ORDER BY patient, time',
                                       (params.get('patient'), params.get('patient'))).fetchall()
                return {'complete': True, 'ecgs': [{'ecg': r[0], 'patient': r[1], 'time': r[2]} for r in rows]}
            if len(parts) == 2 and parts[0] == 'ecg':
                with self.sources() as src:
                    row = src.execute('SELECT id, patient, time FROM ecg WHERE id = ?', (parts[1],)).fetchone()
                if not row:
                    raise InvalidRequest('Unknown ECG')
                files = {p.name: base64.b64encode(p.read_bytes()).decode() for p in sorted((self.ecg_dir / row[0]).iterdir())}
                return {'ecg': row[0], 'patient': row[1], 'time': row[2], 'files': files}
            if parts in (['items'], ['interpretations']):
                table = 'item' if parts == ['items'] else 'interpretation'
                rows = [json.loads(b) for (b,) in db.execute(f'SELECT body FROM {table} ORDER BY id')]
                if params.get('patient'):
                    rows = [r for r in rows if r.get('patient') == params['patient']]
                return {'complete': True, parts[0]: rows}
            raise InvalidRequest('Unknown read route')
        if method == 'POST' and parts in (['items'], ['interpretations']):
            return self.write(db, parts[0], None, data)
        if method == 'PATCH' and len(parts) == 2 and parts[0] in ('items', 'interpretations'):
            return self.write(db, parts[0], parts[1], data)
        raise InvalidRequest('Unknown operation; clinical sources are read-only')

    def search(self, rtype, patient, params):
        try:
            page = int(params.get('page', '1'))
        except ValueError:
            raise InvalidRequest('page must be an integer')
        clauses, args = ['type = ?'], [rtype]
        if patient == '':
            clauses.append('patient IS NULL')
        elif patient is not None:
            clauses.append('patient = ?'); args.append(patient)
        for key, op in (('since', '>='), ('until', '<=')):
            if params.get(key):
                if not DATE.match(params[key]):
                    raise InvalidRequest(f'{key} must be YYYY-MM-DD')
                clauses.append(f'substr(time, 1, 10) {op} ?'); args.append(params[key])
        if params.get('code'):
            clauses.append('code = ?'); args.append(params['code'])
        where = ' AND '.join(clauses)
        with self.sources() as src:
            key = (where, tuple(args))
            if key not in COUNTS:   # sources are immutable; page walks need the total only once
                COUNTS[key] = src.execute(f'SELECT COUNT(*) FROM resource WHERE {where}', args).fetchone()[0]
            total = COUNTS[key]
            rows = src.execute(f'SELECT json FROM resource WHERE {where} ORDER BY time, id LIMIT ? OFFSET ?',
                               args + [PAGE, (page - 1) * PAGE]).fetchall()
        pages = max(1, -(-total // PAGE))
        return {'complete': page >= pages, 'type': rtype, 'total': total, 'page': page, 'pages': pages,
                'resources': [json.loads(zlib.decompress(r[0])) for r in rows]}

    # ------------------------------------------------------------------ submissions
    def owned(self, patient, value, field):
        if not isinstance(value, str) or not value:
            raise InvalidRequest(f'{field} must be a record ID string')
        rid = value.rpartition('/')[2]
        with self.sources() as src:
            row = src.execute('SELECT patient FROM resource WHERE id = ?', (rid,)).fetchone()
            if row is None:
                row = src.execute('SELECT patient FROM ecg WHERE id = ?', (rid,)).fetchone()
        if row is None or (row[0] is not None and row[0] != patient):
            raise InvalidRequest(f'{field} must reference a record in this patient\'s chart, an ECG of this patient, or a clinic document')
        return rid

    def write(self, db, kind, record_id, data):
        if not isinstance(data, dict) or not data:
            raise InvalidRequest('JSON object body required')
        table = 'item' if kind == 'items' else 'interpretation'
        allowed = ITEM_FIELDS if kind == 'items' else INTERP_FIELDS
        unknown = set(data) - set(allowed)
        if unknown:
            raise InvalidRequest('Unknown fields: ' + ', '.join(sorted(unknown)))
        if record_id is None:
            body = {k: None for k in allowed}
            if kind == 'items':
                body.update(af_evidence=[], risk_factors=[], records=[])
            else:
                body.update(conduction=[], changes=[])
        else:
            row = db.execute(f'SELECT body FROM {table} WHERE id = ?', (record_id,)).fetchone()
            if row is None:
                raise InvalidRequest('Unknown ' + table)
            body = json.loads(row[0])
            if kind == 'items' and ('patient' in data or 'category' in data or 'reason' in data):
                raise InvalidRequest('patient, category and reason are immutable')
            if kind == 'interpretations' and 'ecg' in data:
                raise InvalidRequest('ecg is immutable')
        body.update(data)
        (self.validate_item if kind == 'items' else self.validate_interpretation)(body)
        if record_id is None:
            m = self.meta(db); key = 'next_item' if kind == 'items' else 'next_interpretation'
            record_id = ('I' if kind == 'items' else 'F') + str(m[key]); self.set_meta(db, key, m[key] + 1)
            body = {'id': record_id, **body}
            db.execute(f'INSERT INTO {table} VALUES (?,?)', (record_id, json.dumps(body)))
        else:
            db.execute(f'UPDATE {table} SET body = ? WHERE id = ?', (json.dumps(body), record_id))
        return body

    def validate_item(self, b):
        with self.sources() as src:
            if not isinstance(b['patient'], str) or not src.execute("SELECT 1 FROM resource WHERE id = ? AND type = 'Patient'",
                                                                     (b['patient'],)).fetchone():
                raise InvalidRequest('patient must be a Patient ID')
        if b['category'] not in CATEGORIES or b['reason'] not in CATEGORIES.get(b['category'], ()):
            raise InvalidRequest('category/reason must be one of: ' + '; '.join(f"{c}: {', '.join(sorted(r))}" for c, r in CATEGORIES.items()))
        if b['status'] is not None and b['status'] not in FOLLOW_UP_STATUS:
            raise InvalidRequest('status must be one of ' + ', '.join(sorted(FOLLOW_UP_STATUS)) + ' or null')
        for f in ID_FIELDS:
            if b[f] is not None:
                b[f] = self.owned(b['patient'], b[f], f)
        for f in LIST_FIELDS:
            if not isinstance(b[f], list) or len(b[f]) > 20:
                raise InvalidRequest(f'{f} must be a list of at most 20 record IDs')
            b[f] = [self.owned(b['patient'], v, f) for v in b[f]]
        if not isinstance(b['risk_factors'], list) or not set(b['risk_factors']) <= RISK_FACTORS:
            raise InvalidRequest('risk_factors must be a list drawn from ' + ', '.join(sorted(RISK_FACTORS)))
        if b['risk_score'] is not None and (type(b['risk_score']) is not int or not 0 <= b['risk_score'] <= 9):
            raise InvalidRequest('risk_score must be an integer 0-9 or null')
        for f in ('qtc_ms', 'heart_rate'):
            if b[f] is not None and (type(b[f]) not in (int, float) or not 0 < b[f] < 1000):
                raise InvalidRequest(f'{f} must be a positive number or null')
        if b['due_date'] is not None and (not isinstance(b['due_date'], str) or not DATE.match(b['due_date'])):
            raise InvalidRequest('due_date must be YYYY-MM-DD or null')
        self.text(b)

    def validate_interpretation(self, b):
        with self.sources() as src:
            row = src.execute('SELECT patient, time FROM ecg WHERE id = ?', (b['ecg'],)).fetchone() if isinstance(b['ecg'], str) else None
            if row is None:
                raise InvalidRequest('ecg must be an ECG ID from clinic ecg list')
            if b['prior_ecg'] is not None:
                prior = src.execute('SELECT patient, time FROM ecg WHERE id = ?', (b['prior_ecg'],)).fetchone() if isinstance(b['prior_ecg'], str) else None
                if prior is None or prior[0] != row[0] or prior[1] >= row[1]:
                    raise InvalidRequest('prior_ecg must be an earlier ECG of the same patient, or null')
        if b['rhythm'] not in RHYTHMS:
            raise InvalidRequest('rhythm must be one of ' + ', '.join(sorted(RHYTHMS)))
        if b['axis'] is not None and b['axis'] not in AXES:
            raise InvalidRequest('axis must be one of ' + ', '.join(sorted(AXES)) + ' or null')
        for f, vocab in (('conduction', CONDUCTION), ('changes', CHANGES)):
            if not isinstance(b[f], list) or len(set(b[f])) != len(b[f]) or not set(b[f]) <= vocab:
                raise InvalidRequest(f'{f} must be a list of distinct values from ' + ', '.join(sorted(vocab)))
        for f in ('ventricular_rate', 'pr_ms', 'qrs_ms', 'qtc_ms'):
            if b[f] is not None and (type(b[f]) not in (int, float) or not 0 < b[f] < 1000):
                raise InvalidRequest(f'{f} must be a positive number or null')
        if b['ventricular_rate'] is None:
            raise InvalidRequest('ventricular_rate is required')
        self.text(b)

    @staticmethod
    def text(b):
        e = b.get('explanation')
        if e is not None and (not isinstance(e, str) or len(e) > 4000 or not TEXT.match(e)):
            raise InvalidRequest('explanation must be text up to 4000 characters')
