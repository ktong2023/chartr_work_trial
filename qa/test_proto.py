"""Offline checks for the follow-up induction prototype: grading, service contract and fairness coverage."""
import copy
import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROTO = ROOT / "chartr_proto"
sys.path.insert(0, str(ROOT / "qa"))
from proto_cases import CURRENT, HISTORY  # noqa: E402
from proto_rules import MISCONCEPTIONS, answer, coverage, determine  # noqa: E402


def _isolated(paths, names):
    """Import the prototype's modules without clobbering the main task's same-named modules."""
    saved = {name: sys.modules.pop(name) for name in names if name in sys.modules}
    sys.path[:0] = [str(p) for p in paths]
    try:
        return {name: importlib.import_module(name) for name in names}
    finally:
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
        for p in paths:
            sys.path.remove(str(p))


M = _isolated([PROTO / "environment/service", PROTO / "tests", PROTO / "solution", ROOT / "qa"],
              ["fhir", "store", "server", "grade", "reference", "build_proto"])
fhir, store, server, grade, reference, build = (M[n] for n in ("fhir", "store", "server", "grade", "reference", "build_proto"))
CLI = PROTO / "environment/public/clinic.py"


def concrete(case, mis=frozenset()):
    """A determination request for one case, as the rule engine (or a misconception) would record it."""
    status, plan, due, completion = answer(case, mis)
    pid = case["pid"]
    return {"patient": pid, "status": status, "plan": build.rid(f"{pid}.{plan}") if plan else None, "due_date": due,
            "completion": build.rid(f"{pid}.{completion}") if completion else None, "explanation": "Determination."}


class ProtoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fresh()

    def fresh(self):
        self.store = store.Store(Path(tempfile.mkdtemp(dir=self.tmp.name)) / "clinic.sqlite")
        self.store.initialize()
        self.attestation = self.store.attest("offline-trial")
        server.STORE = self.store

    def direct(self, *args, error=False):
        """In-process twin of the clinic CLI."""
        command, rest = args[0], list(args[1:])
        routes = {"patients": ("GET", "/patients", None), "history": ("GET", "/history", None)}
        if command in routes:
            call = routes[command]
        elif command == "records":
            call = ("GET", "/records/" + rest[0], None)
        elif command == "determinations":
            call = ("GET", "/determinations" + ("/" + rest[1] if rest else ""), None)
        elif command == "determine":
            call = ("POST", "/determinations", json.loads(rest[1]))
        else:
            call = ("PATCH", "/determinations/" + rest[0], json.loads(rest[2]))
        status, body = self.store.request(*call)
        self.assertEqual(status, 400 if error else 200, body)
        return body

    def finish(self):
        snapshot = self.store.collect()
        for resource in snapshot["sources"] + snapshot["history"] + snapshot["determinations"]:
            fhir.validate(resource)
        return snapshot, grade.grade(snapshot, self.attestation)

    def solve(self, answers):
        with patch.object(reference, "clinic", self.direct):
            reference.solve(answers)

    def test_reference_passes_and_regrade_is_identical(self):
        self.solve(None)
        snapshot, result = self.finish()
        self.assertEqual(result["reward"], 1, result)
        self.assertEqual(grade.grade(snapshot, self.attestation), result)

    def test_reference_through_the_real_cli(self):
        http = HTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (http.shutdown(), http.server_close(), thread.join()))
        env = {**os.environ, "CLINIC_URL": f"http://127.0.0.1:{http.server_port}"}

        def cli(*args):
            out = subprocess.run([sys.executable, str(CLI), *args], env=env, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            return json.loads(out.stdout)
        with patch.object(reference, "clinic", cli):
            reference.solve()
        self.assertEqual(self.finish()[1]["reward"], 1)

    def test_noop_fails(self):
        result = self.finish()[1]
        self.assertEqual(result["reward"], 0)
        self.assertFalse(result["global"]["total_determinations"])

    def test_expected_answers_come_from_the_rule_engine(self):
        for case in CURRENT:
            pid, result = case["pid"], determine(case)
            self.assertEqual(grade.EXPECTED[pid]["status"], result["status"], pid)
            self.assertEqual(grade.EXPECTED[pid]["due_date"], result["due"], pid)

    def test_every_misconception_is_refuted_twice_and_tested(self):
        for name, report in coverage(HISTORY, CURRENT).items():
            with self.subTest(name):
                self.assertGreaterEqual(len(report["refuted_by"]), 2)
                self.assertTrue(report["fails_current"])

    def test_each_misconception_fails_every_case_it_affects(self):
        correct = {case["pid"]: concrete(case) for case in CURRENT}
        for name, report in coverage(HISTORY, CURRENT).items():
            for pid in report["fails_current"]:
                with self.subTest(misconception=name, patient=pid):
                    self.fresh()
                    case = next(c for c in CURRENT if c["pid"] == pid)
                    self.solve([concrete(case, {name}) if p == pid else a for p, a in correct.items()])
                    result = self.finish()[1]
                    self.assertEqual(result["reward"], 0)
                    self.assertFalse(all(result["patients"][pid].values()))

    def test_duplicate_or_missing_determinations_fail(self):
        answers = [concrete(case) for case in CURRENT]
        self.solve(answers + [answers[0]])
        self.assertEqual(self.finish()[1]["reward"], 0)
        self.fresh()
        self.solve(answers[1:])
        self.assertEqual(self.finish()[1]["reward"], 0)

    def test_service_contract(self):
        good = concrete(CURRENT[0])
        for patient in ([], {}, None, 123, True):
            self.direct("determine", "--json", json.dumps({**good, "patient": patient}), error=True)
        with self.store.connect() as db:
            self.assertEqual(self.store.metadata(db)["faults"], 0)
        self.direct("determine", "--json", json.dumps({**good, "patient": "H201"}), error=True)
        self.direct("determine", "--json", json.dumps({**good, "patient": "P999"}), error=True)
        self.direct("determine", "--json", json.dumps({k: v for k, v in good.items() if k != "completion"}), error=True)
        self.direct("determine", "--json", json.dumps({**good, "due_date": "2026-9-30"}), error=True)
        self.direct("determine", "--json", json.dumps({**good, "status": "done"}), error=True)
        baseline_rpr = build.rid("P301.rpr0")
        self.direct("determine", "--json", json.dumps({**good, "plan": baseline_rpr}), error=True)
        self.direct("determine", "--json", json.dumps({**good, "completion": build.rid("P302.rpr0")}), error=True)
        saved = self.direct("determine", "--json", json.dumps({**good, "plan": "ServiceRequest/" + good["plan"]}))
        self.direct("redetermine", saved["id"], "--json", '{"patient": "P302"}', error=True)
        updated = self.direct("redetermine", saved["id"], "--json", '{"status": "unclear", "plan": null, "due_date": null}')
        self.assertEqual(grade.fields(updated)[:3], ("unclear", None, None))
        self.assertEqual(len(self.direct("history")["determinations"]), len(HISTORY))
        self.assertEqual({e["patient"]["id"] for e in self.direct("patients")["patients"]}, {c["pid"] for c in CURRENT})
        with self.store.connect() as db:
            for sql in ("UPDATE history SET resource='{}'", "DELETE FROM source"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute(sql)
        self.finish()
        self.assertEqual(self.store.request("GET", "/history")[0], 409)

    def test_charts_are_chronological_and_fit_tool_output(self):
        for pid in [c["pid"] for c in CURRENT + HISTORY]:
            with self.subTest(pid):
                resources = self.direct("records", pid)["resources"]
                times = [next((e["valueDateTime"] for e in r.get("extension", []) if e["url"].endswith("/event-time")), "")
                         for r in resources]
                self.assertEqual(times, sorted(times))
                self.assertLess(len(json.dumps({"complete": True, "resources": resources}, indent=2)), 30000)

    def test_invalid_evaluation_is_distinct_from_failure(self):
        snapshot, result = self.finish()
        self.assertEqual(result["validity"], "valid")
        for key, value in (("nonce", "wrong"), ("frozen", False), ("faults", 1)):
            altered = copy.deepcopy(snapshot)
            altered["metadata"][key] = value
            with self.assertRaises(grade.EvaluationError):
                grade.grade(altered, self.attestation)
        with tempfile.TemporaryDirectory() as out:
            run = subprocess.run([sys.executable, str(PROTO / "tests/grade.py"), str(Path(out) / "missing.json"),
                                  str(Path(out) / "missing-attestation.json"), out])
            self.assertEqual(run.returncode, 2)
            self.assertFalse((Path(out) / "reward.txt").exists())


if __name__ == "__main__":
    unittest.main()
