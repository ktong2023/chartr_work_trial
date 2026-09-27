"""Private, independent deterministic grading of controller-collected evidence (follow-up induction)."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
BASELINE = json.loads((HERE / "baseline.json").read_text())
# Per current patient: status, governing plan, due date, and the accepted completion records.
EXPECTED = json.loads((HERE / "expected.json").read_text())
PREFIX = "https://chartr.example/fhir/"


class EvaluationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def check_evidence_integrity(snapshot, attestation):
    try:
        meta = snapshot["metadata"]
        for key in ("trial_id", "nonce", "initial_digest", "version", "evaluation_time"):
            if not meta[key] or meta[key] != attestation[key]:
                raise EvaluationError("Snapshot does not match controller attestation: " + key)
        for key in ("initial_digest", "version", "evaluation_time"):
            if meta[key] != BASELINE[key]:
                raise EvaluationError("Incorrect fixture baseline: " + key)
        if not meta["frozen"] or meta["faults"] != 0:
            raise EvaluationError("Snapshot was not frozen or service recorded an infrastructure fault")
        current = []
        for seq, event in enumerate(snapshot["audit"], 1):
            if event["seq"] != seq or event["before"] != current:
                raise EvaluationError("Audit sequence/state continuity broken")
            if event["status"] >= 500:
                raise EvaluationError("Service failed during evaluation")
            if (event["method"] == "GET" or event["status"] != 200) and event["after"] != current:
                raise EvaluationError("Read/rejected operation changed state")
            current = event["after"]
        if snapshot["determinations"] != current:
            raise EvaluationError("Final determinations differ from service audit")
    except (KeyError, TypeError) as exc:
        raise EvaluationError("Missing or malformed trusted evidence") from exc


def fields(task):
    status = next((c.get("code") for c in task.get("businessStatus", {}).get("coding", [])
                   if c.get("system") == PREFIX + "CodeSystem/determination-status"), None)
    inputs = {i["type"]["coding"][0]["code"]: i["valueReference"]["reference"].split("/")[-1]
              for i in task.get("input", [])}
    due = next((e.get("valueDate") for e in task.get("extension", [])
                if e.get("url") == PREFIX + "StructureDefinition/due-date"), None)
    return status, inputs.get("governing-plan"), due, inputs.get("completion"), task.get("description")


def grade(snapshot, attestation):
    check_evidence_integrity(snapshot, attestation)
    determinations = snapshot["determinations"]
    checks = {"source_integrity": digest(snapshot["sources"]) == BASELINE["sources_digest"],
              "history_integrity": digest(snapshot["history"]) == BASELINE["history_digest"],
              "total_determinations": len(determinations) == len(EXPECTED)}
    diagnostics = {}
    for patient, expected in EXPECTED.items():
        items = [d for d in determinations if d.get("for", {}).get("reference") == "Patient/" + patient]
        result = {"count": len(items) == 1}
        if len(items) == 1:
            status, plan, due, completion, explanation = fields(items[0])
            result.update(
                status=status == expected["status"],
                plan=plan == expected["plan"],
                due_date=due == expected["due_date"],
                completion=completion in expected["completion"] if expected["completion"] else completion is None,
                explanation=isinstance(explanation, str) and bool(explanation.strip()),
            )
        diagnostics[patient] = result
    passed = all(checks.values()) and all(all(c.values()) for c in diagnostics.values())
    return {"validity": "valid", "reward": int(passed), "global": checks, "patients": diagnostics,
            "narrative_limit": "Explanation is checked for nonempty text only; factual prose needs human QA."}


def main():
    snapshot_path, attestation_path, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    for name in ("reward.txt", "reward.json"):
        (output / name).unlink(missing_ok=True)
    try:
        termination_path = snapshot_path.parent / "termination.json"
        if termination_path.exists():
            termination = json.loads(termination_path.read_text())
            if termination["validity"] != "valid":
                raise EvaluationError("Adapter did not complete a valid attempt: " + termination["reason"])
        result = grade(json.loads(snapshot_path.read_text()), json.loads(attestation_path.read_text()))
    except Exception as exc:
        (output / "diagnostics.json").write_text(json.dumps({"validity": "evaluation_error", "error": str(exc)}, indent=2))
        # Never manufacture reward=0 for an invalid evaluation.
        raise SystemExit(2)
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2))
    (output / "reward.txt").write_text(str(result["reward"]) + "\n")


if __name__ == "__main__":
    main()
