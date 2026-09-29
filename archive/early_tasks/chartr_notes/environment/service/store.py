from contextlib import contextmanager
import datetime as dt
import json
import re
import sqlite3
import uuid
from pathlib import Path

from fhir import NOW, VERSION, STATUSES, SCHEMA, canonical, digest, determination, episode, validate, submission

HERE = Path(__file__).parent
# R4 string pattern; checked up front so agent text is a 400, never a schema-failure 500.
FHIR_STRING = re.compile(SCHEMA["definitions"]["string"]["pattern"])
FIELDS = ("status", "plan", "course", "doses", "completion_date", "due_date", "result", "branch", "paused_days", "explanation")


class InvalidRequest(ValueError):
    pass


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20, isolation_level=None)
        db.execute("PRAGMA busy_timeout=20000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        """New container only. Reset means destroy this state and start a new container."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise RuntimeError("Refusing to reuse an existing trial database")
        fixture = json.loads((HERE / "fixture.json").read_text())
        for resource in fixture["sources"]:
            validate(resource)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE source (id TEXT PRIMARY KEY, resource TEXT NOT NULL);
                CREATE TABLE determinations (id TEXT PRIMARY KEY, resource TEXT NOT NULL);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE audit (seq INTEGER PRIMARY KEY, event TEXT NOT NULL);
            ''')
            db.executemany("INSERT INTO source VALUES (?,?)", [(r["id"], canonical(r)) for r in fixture["sources"]])
            db.executemany("INSERT INTO meta VALUES (?,?)", [(k, canonical(v)) for k, v in {
                "version": VERSION, "evaluation_time": NOW, "initial_digest": digest(fixture),
                "targets": fixture["targets"],
                "nonce": str(uuid.uuid4()), "trial_id": None, "frozen": False, "faults": 0, "next_id": 1001,
            }.items()])
            for table in ("source",):
                for operation in ("INSERT", "UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER {table}_no_{operation} BEFORE {operation} ON {table} "
                               "BEGIN SELECT RAISE(ABORT, 'Clinical sources are read-only'); END")

    @staticmethod
    def rows(db, table):
        if table not in {"source", "determinations", "audit"}:
            raise ValueError("Invalid table")
        col, order = ("event", "seq") if table == "audit" else ("resource", "id")
        return [json.loads(row[0]) for row in db.execute(f"SELECT {col} FROM {table} ORDER BY {order}")]

    @staticmethod
    def metadata(db):
        return {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}

    @staticmethod
    def set_meta(db, key, value):
        db.execute("UPDATE meta SET value=? WHERE key=?", (canonical(value), key))

    def fixture_view(self, db, m):
        return {"version": m["version"], "evaluation_time": m["evaluation_time"], "targets": m["targets"], "sources": self.rows(db, "source")}

    def attest(self, trial_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["trial_id"] is not None or self.rows(db, "audit") or self.rows(db, "determinations"):
                raise RuntimeError("Trial state was already used before attestation")
            self.set_meta(db, "trial_id", trial_id)
            m["trial_id"] = trial_id
            if digest(self.fixture_view(db, m)) != m["initial_digest"]:
                raise RuntimeError("Initial state integrity check failed")
            return m

    def collect(self):
        # Serializes with every request. Later requests are rejected before any mutation.
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if not m["trial_id"] or m["frozen"]:
                raise RuntimeError("Cannot collect unbound or already frozen state")
            self.set_meta(db, "frozen", True)
            m["frozen"] = True
            return {"metadata": m, "sources": self.rows(db, "source"),
                    "determinations": self.rows(db, "determinations"), "audit": self.rows(db, "audit")}

    def request(self, method, path, data=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["frozen"]:
                return 409, {"error": "Trial closed; writes and reads are no longer accepted"}
            if not m["trial_id"]:
                return 503, {"error": "Trial initialization pending"}
            seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM audit").fetchone()[0]
            before = self.rows(db, "determinations")
            db.execute("SAVEPOINT operation")
            try:
                response = self._operation(db, m, method, path, data, seq)
                status = 200
            except InvalidRequest as exc:
                db.execute("ROLLBACK TO operation")
                status, response = 400, {"error": str(exc)}
            except Exception:
                db.execute("ROLLBACK TO operation")
                self.set_meta(db, "faults", m["faults"] + 1)
                status, response = 500, {"error": "Internal service error; evaluation infrastructure fault"}
            db.execute("RELEASE operation")
            event = {"seq": seq, "method": method, "path": path, "arguments": data,
                     "status": status, "result": response, "before": before,
                     "after": self.rows(db, "determinations"), "clinical_time": NOW}
            db.execute("INSERT INTO audit VALUES (?,?)", (seq, canonical(event)))
            return status, response

    def _operation(self, db, m, method, path, data, seq):
        sources = self.rows(db, "source")
        by_id = {r["id"]: r for r in sources}
        cohort = set(m["targets"])
        parts = path.strip("/").split("/")
        if method == "GET":
            if path == "/patients":
                return {"complete": True, "evaluation_time": NOW, "patients": [
                    {"patient": r, "target_episodes": m["targets"][r["id"]], "checkpoints": ["first","second"], "episodes": [e for e in sources if e["resourceType"] == "EpisodeOfCare"
                                               and e["patient"]["reference"] == "Patient/" + r["id"]]}
                    for r in sources if r["resourceType"] == "Patient" and r["id"] in cohort]}
            if len(parts) == 2 and parts[0] == "records" and parts[1] in cohort:
                chart = [r for r in sources if r.get("subject", r.get("patient", {})).get("reference")
                         == "Patient/" + parts[1] or r["id"] == parts[1]]
                return {"complete": True, "resources": sorted(chart, key=lambda r: (next(
                    (e["valueDateTime"] for e in r.get("extension", []) if e["url"].endswith("/event-time")), ""), r["id"]))}
            if parts[0] == "determinations" and len(parts) in (1, 2):
                if len(parts) == 2 and parts[1] not in cohort:
                    raise InvalidRequest("Unknown current-cohort patient")
                return {"complete": True, "determinations": [r for r in self.rows(db, "determinations")
                        if len(parts) == 1 or r["for"]["reference"] == "Patient/" + parts[1]]}
            raise InvalidRequest("Unknown read route or patient")
        if not isinstance(data, dict):
            raise InvalidRequest("Request must be a JSON object")
        if method == "POST" and path == "/determinations":
            if set(data) != {"patient", "episode", "checkpoint", *FIELDS}:
                raise InvalidRequest("Determination requires exactly: " + ", ".join(sorted({"patient", "episode", "checkpoint", *FIELDS})))
            patient = data["patient"]
            if not isinstance(patient, str):
                raise InvalidRequest("patient must be a patient ID string")
            if patient not in cohort:
                raise InvalidRequest("Unknown current-cohort patient")
            if not isinstance(data['episode'],str) or data["episode"] not in m["targets"][patient]:
                raise InvalidRequest("episode must be one of this patient's target episodes")
            if not isinstance(data['checkpoint'],str) or data['checkpoint'] not in ('first','second'):
                raise InvalidRequest('checkpoint must be first or second')
            fields = self._validate(data, patient, by_id)
            item_id = "D" + str(m["next_id"])
            self.set_meta(db, "next_id", m["next_id"] + 1)
            result = determination(item_id, patient, data['episode'], data['checkpoint'], *fields, by_id, seq=seq)
            db.execute("INSERT INTO determinations VALUES (?,?)", (item_id, canonical(result)))
            return result
        if method == "PATCH" and len(parts) == 2 and parts[0] == "determinations":
            if not data or set(data) - set(FIELDS):
                raise InvalidRequest("Update permits only " + ", ".join(FIELDS) + "; supply at least one")
            row = db.execute("SELECT resource FROM determinations WHERE id=?", (parts[1],)).fetchone()
            if row is None:
                raise InvalidRequest("Unknown determination")
            original = json.loads(row[0])
            patient = original["for"]["reference"].split("/")[1]
            merged = {**submission(original), **data}
            fields = self._validate(merged, patient, by_id)
            checkpoint=next(e['valueCode'] for e in original['extension'] if e['url'].endswith('/checkpoint'))
            result = determination(original["id"], patient, original['focus']['reference'].split('/')[-1], checkpoint, *fields, by_id, seq=seq)
            db.execute("UPDATE determinations SET resource=? WHERE id=?", (canonical(result), original["id"]))
            return result
        raise InvalidRequest("Unknown operation; clinical sources are read-only")

    @staticmethod
    def _record(ref, patient, by_id, what):
        if ref is None:
            return None
        if not isinstance(ref, str):
            raise InvalidRequest(what + " must be a record ID string or null")
        # Bare record IDs and typed references ("ServiceRequest/R123456") are both accepted.
        kind, _, record_id = ref.rpartition("/")
        r = by_id.get(record_id, {})
        if (kind and r.get("resourceType") != kind) or r.get("subject", {}).get("reference") != "Patient/" + patient:
            raise InvalidRequest(what + " must reference a record in this patient's chart")
        return record_id

    def _validate(self, data, patient, by_id):
        status, explanation = data["status"], data["explanation"]
        if not isinstance(status,str) or status not in STATUSES:
            raise InvalidRequest("Unknown determination status")
        values={}
        for key,kind in (("plan","ServiceRequest"),("course","MedicationRequest"),("result","Observation")):
            values[key]=self._record(data[key],patient,by_id,key)
            if values[key] and by_id[values[key]]["resourceType"]!=kind:
                raise InvalidRequest(key+" must reference "+kind)
        if not isinstance(data["doses"],list) or len(data["doses"])>40:
            raise InvalidRequest("doses must be an array of at most 40 administration IDs")
        values["doses"]=[self._record(v,patient,by_id,"dose") for v in data["doses"]]
        if any(v is None or by_id[v]["resourceType"]!="MedicationAdministration" for v in values["doses"]):
            raise InvalidRequest("Each dose must be a MedicationAdministration")
        for key in ("completion_date","due_date"):
            v=data[key]
            if v is not None:
                try:
                    if not isinstance(v,str) or len(v)!=10: raise ValueError
                    dt.date.fromisoformat(v)
                except ValueError: raise InvalidRequest(key+" must be YYYY-MM-DD or null")
            values[key]=v
        if not isinstance(explanation,str) or not explanation.strip() or len(explanation)>4000 or not FHIR_STRING.search(explanation):
            raise InvalidRequest("explanation must be nonempty R4 text, at most 4000 characters")
        if data['branch'] is not None and (not isinstance(data['branch'],str) or data['branch'] not in ('routine','accelerated')):
            raise InvalidRequest('branch must be routine, accelerated, or null')
        if data['paused_days'] is not None and (type(data['paused_days']) is not int or not 0<=data['paused_days']<=10000):
            raise InvalidRequest('paused_days must be a nonnegative integer or null')
        return status,values["plan"],values["course"],values["doses"],values["completion_date"],values["due_date"],values["result"],data['branch'],data['paused_days'],explanation
