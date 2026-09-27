"""Private, independent deterministic grading of controller-collected evidence (interacting requirements).

Row fields are compared exactly with the authored answers. The evidence allocation is checked as a
constraint problem instead: any valid assignment that reaches the patient's maximum is accepted, and
each unassigned row's status is checked against the assignment the agent actually saved.
"""
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
BASELINE = json.loads((HERE / "baseline.json").read_text())
# Per patient: authored rows keyed "episode:checkpoint", effective report facts, and the maximum
# number of checkpoints any valid joint assignment can complete.
EXPECTED = json.loads((HERE / "expected.json").read_text())
PREFIX = "https://chartr.example/fhir/"
EVAL = dt.date(2026, 9, 24)
ROW_FIELDS = ("plan", "course", "branch", "completion_date", "due_date", "paused_days")


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
    out = {"status": None, "plan": None, "course": None, "result": None, "doses": [], "completion_date": None,
           "due_date": None, "branch": None, "paused_days": None, "checkpoint": None,
           "episode": task.get("focus", {}).get("reference", "").split("/")[-1]}
    out["status"] = next((c.get("code") for c in task.get("businessStatus", {}).get("coding", [])
                          if c.get("system") == PREFIX + "CodeSystem/determination-status"), None)
    for entry in task.get("input", []):
        role = entry["type"]["coding"][0]["code"]
        ref = entry["valueReference"]["reference"].split("/")[-1]
        if role == "dose":
            out["doses"].append(ref)
        else:
            out[role] = ref
    for ext in task.get("extension", []):
        name = ext["url"].split("/")[-1]
        if name in ("completion-date", "due-date"):
            out[name.replace("-", "_")] = ext["valueDate"]
        elif name == "schedule-branch":
            out["branch"] = ext["valueCode"]
        elif name == "paused-days":
            out["paused_days"] = ext["valueInteger"]
        elif name == "checkpoint":
            out["checkpoint"] = ext["valueCode"]
    return out


def day(value):
    return dt.date.fromisoformat(value)


def candidate(row, report):
    """Whether a report can complete this checkpoint under the policy's per-checkpoint rules."""
    if report is None or not report["eligible"] or row["course"] not in report["courses"]:
        return False
    collected, due = day(report["date"]), day(row["due_date"])
    return day(row["completion_date"]) < collected and due - dt.timedelta(days=21) <= collected <= due + dt.timedelta(days=35)


def grade_patient(patient, expected, items):
    found = {}
    for item in items:
        f = fields(item)
        found.setdefault(f["episode"] + ":" + str(f["checkpoint"]), []).append((item, f))
    rows = {key: {"count": len(found.get(key, [])) == 1} for key in expected["rows"]}
    if not all(r["count"] for r in rows.values()):
        return rows, {}
    actual = {key: found[key][0][1] for key in expected["rows"]}
    for key, row in expected["rows"].items():
        got, result = actual[key], rows[key]
        item = found[key][0][0]
        result["explanation"] = isinstance(item.get("description"), str) and bool(item["description"].strip())
        if row["fixed_status"]:
            result["status"] = got["status"] == row["fixed_status"]
            result["empty_fields"] = (all(got[k] is None for k in ROW_FIELDS) and not got["doses"]
                                      and got["result"] is None)
            continue
        for k in ROW_FIELDS:
            result[k] = got[k] == row[k]
        result["doses"] = set(got["doses"]) == set(row["doses"]) and len(got["doses"]) == len(set(got["doses"]))
        result["result"] = got["result"] is None or candidate(row, expected["reports"].get(got["result"]))
    # Joint allocation: judged on the saved assignment, whatever maximum the agent chose.
    assigned = {key: actual[key]["result"] for key, row in expected["rows"].items()
                if not row["fixed_status"] and rows[key]["result"] and actual[key]["result"]}
    specimens = [expected["reports"][r]["specimen"] for r in assigned.values()]
    allocation = {"specimens_unique": len(specimens) == len(set(specimens)), "prerequisites": True,
                  "maximum": len(assigned) == expected["optimum"]}
    for key, row in expected["rows"].items():
        if row["fixed_status"]:
            continue
        first_key = row["episode"] + ":first"
        if row["checkpoint"] == "second" and key in assigned:
            first = assigned.get(first_key)
            if not first or (day(expected["reports"][assigned[key]]["date"])
                             - day(expected["reports"][first]["date"])).days < row["separation"]:
                allocation["prerequisites"] = False
        if key in assigned:
            status = "completed"
        elif row["completion_date"] is None:
            status = "not_due"
        elif row["checkpoint"] == "second" and first_key not in assigned:
            status = "blocked"
        else:
            status = "overdue" if day(row["due_date"]) <= EVAL else "not_due"
        rows[key]["status"] = actual[key]["status"] == status
    return rows, allocation


def grade(snapshot, attestation):
    check_evidence_integrity(snapshot, attestation)
    items = snapshot["determinations"]
    total = sum(len(p["rows"]) for p in EXPECTED.values())
    checks = {"source_integrity": digest(snapshot["sources"]) == BASELINE["sources_digest"],
              "total_determinations": len(items) == total, "unique_ids": len({i["id"] for i in items}) == len(items)}
    patients = {}
    for patient, expected in EXPECTED.items():
        mine = [i for i in items if i.get("for", {}).get("reference") == "Patient/" + patient]
        rows, allocation = grade_patient(patient, expected, mine)
        patients[patient] = {"rows": rows, "allocation": allocation}
    passed = all(checks.values()) and all(
        all(all(r.values()) for r in p["rows"].values()) and all(p["allocation"].values()) and p["allocation"]
        for p in patients.values())
    return {"validity": "valid", "reward": int(passed), "global": checks, "patients": patients,
            "narrative_limit": "Explanation is checked for nonempty text only."}


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
