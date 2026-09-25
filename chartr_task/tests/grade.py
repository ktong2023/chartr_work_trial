"""Private, independent deterministic grading of controller-collected evidence."""
import hashlib
import json
import sys
from pathlib import Path

BASELINE = json.loads((Path(__file__).parent / "baseline.json").read_text())
PREFIX = "https://chartr.example/fhir/"
EXPECTED = {
    "P101": {"episode": "E101", "reason": "UNRESOLVED_TREATMENT_CONCERN", "status": "open",
             "required": [{"S02"}, {"S01", "S03"}, {"S04"}], "allowed": {"S01", "S02", "S03", "S04", "S05"}},
    "P102": {"episode": "E102", "reason": "UNRESOLVED_TREATMENT_CONCERN", "status": "resolved",
             "required": [{"D03"}, {"D01", "D04"}], "allowed": {"D01", "D02", "D03", "D04", "D05"}},
    "P103": {"episode": "E103", "reason": "CONFLICTING_ACTIVE_PLANS", "status": "needs_clarification",
             "required": [{"M02"}, {"M04"}], "allowed": {"M01", "M02", "M03", "M04", "M05"}},
}


class EvaluationError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def code(item, field, system):
    coding = item.get(field, {}).get("coding", [])
    return next((c.get("code") for c in coding if c.get("system") == PREFIX + "CodeSystem/" + system), None)


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
        current = [BASELINE["q102"]]
        for seq, event in enumerate(snapshot["audit"], 1):
            if event["seq"] != seq or event["before"] != current:
                raise EvaluationError("Audit sequence/state continuity broken")
            if event["status"] >= 500:
                raise EvaluationError("Service failed during evaluation")
            if (event["method"] == "GET" or event["status"] != 200) and event["after"] != current:
                raise EvaluationError("Read/rejected operation changed state")
            current = event["after"]
        if snapshot["queue"] != current:
            raise EvaluationError("Final queue differs from service audit")
    except (KeyError, TypeError) as exc:
        raise EvaluationError("Missing or malformed trusted evidence") from exc


def grade(snapshot, attestation):
    check_evidence_integrity(snapshot, attestation)
    queue = snapshot["queue"]
    sources = {r["id"]: r for r in snapshot["sources"]}
    checks = {"source_integrity": digest(snapshot["sources"]) == BASELINE["sources_digest"],
              "total_items": len(queue) == 3,
              "unique_ids": len({r["id"] for r in queue}) == len(queue)}
    diagnostics = {}
    for patient, expected in EXPECTED.items():
        items = [r for r in queue if r.get("for", {}).get("reference") == "Patient/" + patient]
        case = {"item_count": len(items) == 1}
        if len(items) == 1:
            item = items[0]
            refs = [i.get("valueReference", {}).get("reference", "") for i in item.get("input", [])]
            ids = {r.split("/")[-1] for r in refs}
            valid_refs = all(ref == sources.get(ref.split("/")[-1], {}).get("resourceType", "") + "/" + ref.split("/")[-1]
                             and sources.get(ref.split("/")[-1], {}).get("subject", {}).get("reference") == "Patient/" + patient
                             for ref in refs)
            case.update(
                identity=item["id"] == "Q102" if patient == "P102" else item["id"] != "Q102",
                episode=item.get("focus", {}).get("reference") == "EpisodeOfCare/" + expected["episode"]
                    and any(e.get("url") == PREFIX + "StructureDefinition/episode" and
                            e.get("valueReference", {}).get("reference") == "EpisodeOfCare/" + expected["episode"]
                            for e in item.get("extension", [])),
                category=code(item, "code", "category") == "treatment_review",
                reason=code(item, "reasonCode", "review-reason") == expected["reason"],
                destination=item.get("owner", {}).get("reference") == "Organization/clinical-review",
                disposition=code(item, "businessStatus", "review-status") == expected["status"]
                    and item.get("status") == ("completed" if expected["status"] == "resolved" else "requested"),
                evidence=valid_refs and ids <= expected["allowed"] and all(ids & group for group in expected["required"]),
                explanation=isinstance(item.get("description"), str) and bool(item["description"].strip()),
            )
            if patient == "P102":
                case["original_creation"] = item.get("authoredOn") == BASELINE["q102"]["authoredOn"]
        diagnostics[patient] = case
    passed = all(checks.values()) and all(all(c.values()) for c in diagnostics.values())
    return {"validity": "valid", "reward": int(passed), "global": checks, "patients": diagnostics,
            "narrative_limit": "Explanation is checked for nonempty text only; factual prose needs human QA."}


def main():
    snapshot_path, attestation_path, output = map(Path, sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    try:
        result = grade(json.loads(snapshot_path.read_text()), json.loads(attestation_path.read_text()))
    except Exception as exc:
        (output / "diagnostics.json").write_text(json.dumps({"validity": "evaluation_error", "error": str(exc)}, indent=2))
        # Never manufacture reward=0 for an invalid evaluation.
        raise SystemExit(2)
    (output / "diagnostics.json").write_text(json.dumps(result, indent=2))
    (output / "reward.txt").write_text(str(result["reward"]) + "\n")


if __name__ == "__main__":
    main()
