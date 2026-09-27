"""Private, independent deterministic grading of controller-collected evidence (cohort audit).

Every candidate (episode x issue) is graded on its disposition and, for cannot_determine, its
missing-evidence code. A candidate without an item counts as not_an_issue, except that a candidate named
in a review request needs an explicit item. Pass requires every candidate exact (zero tolerance) and valid
evidence on every item. Citation sufficiency and explanation prose are not graded.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
BASELINE = json.loads((HERE / "baseline.json").read_text())
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
        if snapshot["items"] != current:
            raise EvaluationError("Final items differ from service audit")
    except (KeyError, TypeError) as exc:
        raise EvaluationError("Missing or malformed trusted evidence") from exc


def fields(task):
    code = lambda system: next((c.get("code") for c in task.get(system, {}).get("coding", [])), None)
    return {"patient": task.get("for", {}).get("reference", "").split("/")[-1],
            "episode": task.get("focus", {}).get("reference", "").split("/")[-1],
            "issue": code("code"), "disposition": code("businessStatus"),
            "code": next((e.get("valueCode") for e in task.get("extension", []) if e.get("url") == PREFIX + "StructureDefinition/missing-evidence"), None),
            "evidence": [i["valueReference"]["reference"].split("/")[-1] for i in task.get("input", [])],
            "explanation": task.get("description")}


def evidence_ok(f, sources):
    """Evidence must exist in the item's patient chart, in the chart of any patient sharing a specimen
    accession with it (both sides of a misfile), or be a clinic-level record."""
    allowed = set(EXPECTED["charts"].get(f["patient"], [])) | set(EXPECTED["linked"].get(f["patient"], []))
    for partner in EXPECTED["partners"].get(f["patient"], []):
        allowed |= set(EXPECTED["charts"].get(partner, []))
    clinic_level = {r["id"] for r in sources if "subject" not in r and "patient" not in r and "for" not in r
                    and r["resourceType"] not in ("Patient", "EpisodeOfCare")}
    return bool(f["evidence"]) and all(e in allowed or e in clinic_level for e in f["evidence"])


def grade(snapshot, attestation):
    check_evidence_integrity(snapshot, attestation)
    sources = snapshot["sources"]
    items = [fields(i) for i in snapshot["items"]]
    by_key = {}
    for f in items:
        by_key.setdefault(f"{f['patient']}|{f['episode']}|{f['issue']}", []).append(f)
    candidates, confusion = {}, {}
    for key, want in EXPECTED["candidates"].items():
        found = by_key.get(key, [])
        got = found[0] if len(found) == 1 else None
        disposition = got["disposition"] if got else ("missing" if want["requested"] else "not_an_issue")
        if len(found) > 1:
            disposition = "duplicate"
        code = got["code"] if got else None
        ok = disposition == want["disposition"] and (want["disposition"] != "cannot_determine" or code == want["code"])
        error = None
        if not ok:
            if want["disposition"] == "cannot_determine" and disposition in ("confirmed", "not_an_issue"):
                error = "overclaim"
            elif disposition == "cannot_determine" and want["disposition"] != "cannot_determine":
                error = "underclaim"
            elif disposition == "cannot_determine":
                error = "wrong_code"
            elif disposition in ("missing", "duplicate"):
                error = disposition
            else:
                error = "false_flag" if disposition == "confirmed" else "missed"
        candidates[key] = {"patient_key": want["patient_key"], "kind": want["kind"], "requested": want["requested"],
                           "expected": [want["disposition"], want["code"]], "got": [disposition, code], "pass": ok, "error": error}
        issue = key.split("|")[2]
        cell = confusion.setdefault(want["kind"], {}).setdefault(issue, {"total": 0, "pass": 0})
        cell["total"] += 1
        cell["pass"] += ok
    known = set(EXPECTED["candidates"])
    evidence = {i: evidence_ok(f, sources) for i, f in enumerate(items)}
    checks = {"source_integrity": digest(sources) == BASELINE["sources_digest"],
              "items_on_cohort_candidates": all(f"{f['patient']}|{f['episode']}|{f['issue']}" in known for f in items),
              "evidence_valid": all(evidence.values()),
              "explanations_nonempty": all(isinstance(f["explanation"], str) and f["explanation"].strip() for f in items)}
    errors = {}
    for c in candidates.values():
        if c["error"]:
            errors[c["error"]] = errors.get(c["error"], 0) + 1
    split = {}
    for group, members in (("requested", [c for c in candidates.values() if c["requested"]]),
                           ("unrequested_nondefault", [c for c in candidates.values()
                                                       if not c["requested"] and c["expected"][0] != "not_an_issue"])):
        split[group] = {"total": len(members), "pass": sum(c["pass"] for c in members)}
    passed = all(checks.values()) and all(c["pass"] for c in candidates.values())
    return {"validity": "valid", "reward": int(passed), "global": checks, "errors": errors,
            "by_kind_and_issue": confusion, "requested_vs_unrequested": split,
            "failed_candidates": {k: v for k, v in candidates.items() if not v["pass"]},
            "candidates": candidates,
            "narrative_limit": "Explanations are checked for nonempty text only; citation sufficiency is not graded."}


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
