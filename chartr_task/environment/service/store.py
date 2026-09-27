from contextlib import contextmanager
import json
import re
import sqlite3
import uuid
from pathlib import Path

from fhir import NOW, VERSION, STATUS, CATEGORIES, SCHEMA, canonical, digest, episode, review, validate

HERE = Path(__file__).parent
# R4 string pattern; checked up front so agent text is a 400, never a schema-failure 500.
FHIR_STRING = re.compile(SCHEMA["definitions"]["string"]["pattern"])


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
        for resource in fixture["sources"] + fixture["queue"]:
            validate(resource)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE source (id TEXT PRIMARY KEY, resource TEXT NOT NULL);
                CREATE TABLE queue (id TEXT PRIMARY KEY, resource TEXT NOT NULL);
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE audit (seq INTEGER PRIMARY KEY, event TEXT NOT NULL);
            ''')
            db.executemany("INSERT INTO source VALUES (?,?)", [(r["id"], canonical(r)) for r in fixture["sources"]])
            db.executemany("INSERT INTO queue VALUES (?,?)", [(r["id"], canonical(r)) for r in fixture["queue"]])
            db.executemany("INSERT INTO meta VALUES (?,?)", [(k, canonical(v)) for k, v in {
                "version": VERSION, "evaluation_time": NOW, "initial_digest": digest(fixture),
                "nonce": str(uuid.uuid4()), "trial_id": None, "frozen": False, "faults": 0,
                # Generated IDs continue after the highest seeded item ID.
                "next_id": max(int(r["id"][1:]) for r in fixture["queue"]) + 1,
            }.items()])
            for operation in ("INSERT", "UPDATE", "DELETE"):
                db.execute(f"CREATE TRIGGER source_no_{operation} BEFORE {operation} ON source "
                           "BEGIN SELECT RAISE(ABORT, 'Clinical sources are read-only'); END")

    @staticmethod
    def rows(db, table):
        if table not in {"source", "queue", "audit"}:
            raise ValueError("Invalid table")
        col, order = ("event", "seq") if table == "audit" else ("resource", "id")
        return [json.loads(row[0]) for row in db.execute(f"SELECT {col} FROM {table} ORDER BY {order}")]

    @staticmethod
    def metadata(db):
        return {k: json.loads(v) for k, v in db.execute("SELECT key,value FROM meta")}

    @staticmethod
    def set_meta(db, key, value):
        db.execute("UPDATE meta SET value=? WHERE key=?", (canonical(value), key))

    def attest(self, trial_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["trial_id"] is not None or self.rows(db, "audit"):
                raise RuntimeError("Trial state was already used before attestation")
            self.set_meta(db, "trial_id", trial_id)
            m["trial_id"] = trial_id
            fixture = {k: m[k] for k in ("version", "evaluation_time")}
            fixture.update(sources=self.rows(db, "source"), queue=self.rows(db, "queue"))
            if digest(fixture) != m["initial_digest"]:
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
                    "queue": self.rows(db, "queue"), "audit": self.rows(db, "audit")}

    def request(self, method, path, data=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            m = self.metadata(db)
            if m["frozen"]:
                return 409, {"error": "Trial closed; writes and reads are no longer accepted"}
            if not m["trial_id"]:
                return 503, {"error": "Trial initialization pending"}
            seq = db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM audit").fetchone()[0]
            before = self.rows(db, "queue")
            db.execute("SAVEPOINT operation")
            try:
                response = self._operation(db, method, path, data, seq)
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
                     "after": self.rows(db, "queue"), "clinical_time": NOW}
            db.execute("INSERT INTO audit VALUES (?,?)", (seq, canonical(event)))
            return status, response

    def _operation(self, db, method, path, data, seq):
        sources = self.rows(db, "source")
        by_id = {r["id"]: r for r in sources}
        patients = {r["id"] for r in sources if r["resourceType"] == "Patient"}
        parts = path.strip("/").split("/")
        if method == "GET":
            if path == "/patients":
                return {"complete": True, "evaluation_time": NOW, "patients": [
                    {"patient": r, "episodes": [e for e in sources if e["resourceType"] == "EpisodeOfCare"
                                               and e["patient"]["reference"] == "Patient/" + r["id"]]}
                    for r in sources if r["id"] in patients]}
            if len(parts) == 2 and parts[0] == "records" and parts[1] in patients:
                chart = [r for r in sources if
                         r.get("subject", r.get("patient", {})).get("reference") == "Patient/" + parts[1]
                         or r["id"] == parts[1]]
                return {"complete": True, "resources": sorted(chart, key=lambda r: (next(
                    (e["valueDateTime"] for e in r.get("extension", []) if e["url"].endswith("/event-time")), ""), r["id"]))}
            if parts[0] == "reviews" and len(parts) in (1, 2):
                if len(parts) == 2 and parts[1] not in patients:
                    raise InvalidRequest("Unknown patient")
                return {"complete": True, "items": [r for r in self.rows(db, "queue") if len(parts) == 1
                         or r["for"]["reference"] == "Patient/" + parts[1]]}
            raise InvalidRequest("Unknown read route or patient")
        if not isinstance(data, dict):
            raise InvalidRequest("Request must be a JSON object")
        if method == "POST" and path == "/reviews":
            required = {"patient", "episode", "category", "reason", "destination", "status", "evidence", "explanation"}
            if set(data) != required:
                raise InvalidRequest("Create requires exactly: " + ", ".join(sorted(required)))
            if not all(isinstance(data[k], str) for k in required - {"evidence"}):
                raise InvalidRequest("All fields except evidence must be strings")
            if data["patient"] not in patients or by_id.get(data["episode"], {}).get("patient", {}).get("reference") != "Patient/" + data["patient"]:
                raise InvalidRequest("Patient/episode relationship does not exist")
            spec = CATEGORIES.get(data["category"])
            if spec is None or data["destination"] != spec["destination"] or data["reason"] not in spec["reasons"]:
                raise InvalidRequest("Unsupported category, or destination/reason not allowed for that category")
            self._validate_changes(data, data["patient"], data["episode"], by_id)
            item_id = "Q" + str(self.metadata(db)["next_id"])
            self.set_meta(db, "next_id", self.metadata(db)["next_id"] + 1)
            result = review(item_id, data["patient"], data["episode"], data["category"], data["reason"],
                            data["status"], data["evidence"], data["explanation"], by_id, seq=seq)
            db.execute("INSERT INTO queue VALUES (?,?)", (item_id, canonical(result)))
            return result
        if method == "PATCH" and len(parts) == 2 and parts[0] == "reviews":
            if not data or set(data) - {"status", "evidence", "explanation"}:
                raise InvalidRequest("Update permits only status, evidence, explanation; supply at least one")
            row = db.execute("SELECT resource FROM queue WHERE id=?", (parts[1],)).fetchone()
            if row is None:
                raise InvalidRequest("Unknown review item")
            original = json.loads(row[0])
            patient, ep = original["for"]["reference"].split("/")[1], episode(original)
            merged = {"status": original["businessStatus"]["coding"][0]["code"],
                      "evidence": [i["valueReference"]["reference"].split("/")[1] for i in original["input"]],
                      "explanation": original["description"], **data}
            self._validate_changes(merged, patient, ep, by_id)
            result = review(original["id"], patient, ep, original["code"]["coding"][0]["code"],
                            original["reasonCode"]["coding"][0]["code"], merged["status"], merged["evidence"],
                            merged["explanation"], by_id, created=original["authoredOn"], seq=seq)
            db.execute("UPDATE queue SET resource=? WHERE id=?", (canonical(result), original["id"]))
            return result
        raise InvalidRequest("Unknown operation; clinical sources are read-only")

    @staticmethod
    def _validate_changes(data, patient, ep, sources):
        if not isinstance(data["status"], str) or data["status"] not in STATUS:
            raise InvalidRequest("status must be open, needs_clarification, or resolved")
        if not isinstance(data["explanation"], str) or not data["explanation"].strip() or len(data["explanation"]) > 4000:
            raise InvalidRequest("explanation must be nonempty text, at most 4000 characters")
        if not FHIR_STRING.search(data["explanation"]):
            raise InvalidRequest("explanation whitespace must be space, tab, carriage return or line feed")
        refs = data["evidence"]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 20 or not all(isinstance(x, str) for x in refs):
            raise InvalidRequest("evidence must be a nonempty list of up to 20 record IDs")
        for ref in refs:
            r = sources.get(ref, {})
            if r.get("subject", {}).get("reference") != "Patient/" + patient or episode(r) != ep:
                raise InvalidRequest("Evidence must reference clinical records in the same patient and episode")
