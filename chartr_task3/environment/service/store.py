from contextlib import contextmanager
import json
import re
import sqlite3
import uuid
from pathlib import Path

from fhir import NOW, VERSION, SCHEMA, ISSUES, DISPOSITIONS, CODES, canonical, digest, item, validate, submission, subject

HERE = Path(__file__).parent
# R4 string pattern; checked up front so agent text is a 400, never a schema-failure 500.
FHIR_STRING = re.compile(SCHEMA["definitions"]["string"]["pattern"])
CREATE = ("patient", "episode", "issue", "disposition", "missing_evidence", "evidence", "explanation")
MUTABLE = ("disposition", "missing_evidence", "evidence", "explanation")


class InvalidRequest(ValueError):
    pass


def event_time(r):
    return next((e["valueDateTime"] for e in r.get("extension", []) if e["url"].endswith("/event-time")), "")


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self._sources = None

    def sources(self, db):
        # Clinical sources are immutable (write triggers abort), so they are parsed once per process.
        if self._sources is None:
            rows = self.rows(db, "source")
            self._sources = (rows, {r["id"]: r for r in rows})
        return self._sources

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
                CREATE TABLE items (id TEXT PRIMARY KEY, resource TEXT NOT NULL);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE audit (seq INTEGER PRIMARY KEY, event TEXT NOT NULL);
            ''')
            db.executemany("INSERT INTO source VALUES (?,?)", [(r["id"], canonical(r)) for r in fixture["sources"]])
            db.executemany("INSERT INTO meta VALUES (?,?)", [(k, canonical(v)) for k, v in {
                "version": VERSION, "evaluation_time": NOW, "initial_digest": digest(fixture),
                "episodes": fixture["episodes"],
                "nonce": str(uuid.uuid4()), "trial_id": None, "frozen": False, "faults": 0, "next_id": 1001,
            }.items()])
            for operation in ("INSERT", "UPDATE", "DELETE"):
                db.execute(f"CREATE TRIGGER source_no_{operation} BEFORE {operation} ON source "
                           "BEGIN SELECT RAISE(ABORT, 'Clinical sources are read-only'); END")

    @staticmethod
    def rows(db, table):
        if table not in {"source", "items", "audit"}:
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
        return {"version": m["version"], "evaluation_time": m["evaluation_time"], "episodes": m["episodes"],
                "sources": self.rows(db, "source")}

    def attest(self, trial_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["trial_id"] is not None or self.rows(db, "audit") or self.rows(db, "items"):
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
                    "items": self.rows(db, "items"), "audit": self.rows(db, "audit")}

    def request(self, method, path, data=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["frozen"]:
                return 409, {"error": "Trial closed; writes and reads are no longer accepted"}
            if not m["trial_id"]:
                return 503, {"error": "Trial initialization pending"}
            seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM audit").fetchone()[0]
            before = digest(self.rows(db, "items"))
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
            # Linear-size audit: item-state digests before and after, the one item a successful write changed,
            # and a digest of each successful read (sources are immutable and attested).
            write = method in ("POST", "PATCH") and status == 200
            logged = {"digest": digest(response)} if method == "GET" and status == 200 else {"id": response["id"]} if write else response
            event = {"seq": seq, "method": method, "path": path, "arguments": data,
                     "status": status, "result": logged, "before": before,
                     "after": digest(self.rows(db, "items")), "changed": response if write else None,
                     "clinical_time": NOW}
            db.execute("INSERT INTO audit VALUES (?,?)", (seq, canonical(event)))
            return status, response

    def _operation(self, db, m, method, path, data, seq):
        sources, by_id = self.sources(db)
        cohort = m["episodes"]
        parts = path.strip("/").split("/")
        if method == "GET":
            if path == "/patients":
                return {"complete": True, "evaluation_time": NOW, "patients": [
                    {"patient": by_id[p], "episodes": [by_id[e] for e in eps]} for p, eps in sorted(cohort.items())]}
            if len(parts) == 2 and parts[0] == "records" and parts[1] in cohort:
                chart = [r for r in sources if subject(r) == parts[1]]
                return {"complete": True, "resources": sorted(chart, key=lambda r: (event_time(r), r["id"]))}
            if path == "/export":
                ordered = sorted(sources, key=lambda r: (r["resourceType"], r["id"]))
                return {"complete": True, "evaluation_time": NOW, "resources": ordered}
            if path == "/requests":
                return {"complete": True, "requests": [r for r in sources if r["resourceType"] == "Task"]}
            if parts[0] == "items" and len(parts) in (1, 2):
                if len(parts) == 2 and parts[1] not in cohort:
                    raise InvalidRequest("Unknown cohort patient")
                return {"complete": True, "items": [r for r in self.rows(db, "items")
                        if len(parts) == 1 or r["for"]["reference"] == "Patient/" + parts[1]]}
            raise InvalidRequest("Unknown read route or patient")
        if not isinstance(data, dict):
            raise InvalidRequest("Request must be a JSON object")
        if method == "POST" and path == "/items":
            if set(data) != set(CREATE):
                raise InvalidRequest("Item requires exactly: " + ", ".join(CREATE))
            patient, episode, issue = data["patient"], data["episode"], data["issue"]
            if not isinstance(patient, str) or patient not in cohort:
                raise InvalidRequest("patient must be a cohort patient ID string")
            if not isinstance(episode, str) or episode not in cohort[patient]:
                raise InvalidRequest("episode must be one of this patient's episodes")
            if not isinstance(issue, str) or issue not in ISSUES:
                raise InvalidRequest("issue must be one of: " + ", ".join(ISSUES))
            for row in self.rows(db, "items"):
                if submission(row)["issue"] == issue and row["focus"]["reference"] == "EpisodeOfCare/" + episode:
                    raise InvalidRequest("An item for this episode and issue already exists (" + row["id"] + "); update it instead")
            fields = self._validate(data, by_id)
            item_id = "I" + str(m["next_id"])
            self.set_meta(db, "next_id", m["next_id"] + 1)
            result = item(item_id, patient, episode, issue, *fields, by_id, seq=seq)
            db.execute("INSERT INTO items VALUES (?,?)", (item_id, canonical(result)))
            return result
        if method == "PATCH" and len(parts) == 2 and parts[0] == "items":
            if not data or set(data) - set(MUTABLE):
                raise InvalidRequest("Update permits only " + ", ".join(MUTABLE) + "; supply at least one")
            row = db.execute("SELECT resource FROM items WHERE id=?", (parts[1],)).fetchone()
            if row is None:
                raise InvalidRequest("Unknown item")
            original = json.loads(row[0])
            merged = {**submission(original), **data}
            fields = self._validate(merged, by_id)
            result = item(original["id"], original["for"]["reference"].split("/")[1],
                          original["focus"]["reference"].split("/")[1], merged["issue"], *fields, by_id, seq=seq)
            db.execute("UPDATE items SET resource=? WHERE id=?", (canonical(result), original["id"]))
            return result
        raise InvalidRequest("Unknown operation; clinical sources are read-only")

    @staticmethod
    def _validate(data, by_id):
        disposition, code, evidence, explanation = (data["disposition"], data["missing_evidence"],
                                                    data["evidence"], data["explanation"])
        if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
            raise InvalidRequest("disposition must be one of: " + ", ".join(DISPOSITIONS))
        if disposition == "cannot_determine":
            if not isinstance(code, str) or code not in CODES:
                raise InvalidRequest("cannot_determine requires missing_evidence, one of: " + ", ".join(CODES))
        elif code is not None:
            raise InvalidRequest("missing_evidence must be null unless disposition is cannot_determine")
        if not isinstance(evidence, list) or not 1 <= len(evidence) <= 30:
            raise InvalidRequest("evidence must be an array of 1 to 30 record IDs")
        ids = []
        for ref in evidence:
            if not isinstance(ref, str):
                raise InvalidRequest("evidence entries must be record ID strings")
            kind, _, record_id = ref.rpartition("/")
            if record_id not in by_id or (kind and by_id[record_id]["resourceType"] != kind):
                raise InvalidRequest("Unknown evidence record: " + ref)
            ids.append(record_id)
        if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 4000 or not FHIR_STRING.search(explanation):
            raise InvalidRequest("explanation must be nonempty R4 text, at most 4000 characters")
        return disposition, code, ids, explanation
