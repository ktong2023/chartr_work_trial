"""Private, independent deterministic grading of controller-collected evidence (dependent histories)."""
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
    result={"status":None,"plan":None,"course":None,"doses":[],"completion_date":None,"due_date":None,"result":None}
    result["status"]=next((c.get("code") for c in task.get("businessStatus",{}).get("coding",[]) if c.get("system")==PREFIX+"CodeSystem/determination-status"),None)
    for entry in task.get("input",[]):
        role=entry["type"]["coding"][0]["code"];ref=entry["valueReference"]["reference"].split("/")[-1]
        if role=="dose":result["doses"].append(ref)
        else:result[role]=ref
    for ext in task.get("extension",[]):
        name=ext["url"].split("/")[-1].replace("-","_")
        if name in ("completion_date","due_date"):result[name]=ext["valueDate"]
    return result


def grade(snapshot,attestation):
    check_evidence_integrity(snapshot,attestation)
    items=snapshot["determinations"]
    checks={"source_integrity":digest(snapshot["sources"])==BASELINE["sources_digest"],
            "total_determinations":len(items)==len(EXPECTED),"unique_ids":len({i["id"] for i in items})==len(items)}
    patients={}
    for patient,expected in EXPECTED.items():
        found=[i for i in items if i.get("for",{}).get("reference")=="Patient/"+patient]
        result={"count":len(found)==1}
        if len(found)==1:
            item=found[0];actual=fields(item)
            result["episode"]=item.get("focus",{}).get("reference")=="EpisodeOfCare/"+expected["episode"]
            for key in ("status","plan","course","completion_date","due_date"):result[key]=actual[key]==expected[key]
            result["doses"]=set(actual["doses"])==set(expected["doses"]) and len(actual["doses"])==len(set(actual["doses"]))
            result["result"]=actual["result"] in expected["results"] if expected["results"] else actual["result"] is None
            result["explanation"]=isinstance(item.get("description"),str) and bool(item["description"].strip())
        patients[patient]=result
    return {"validity":"valid","reward":int(all(checks.values()) and all(all(c.values()) for c in patients.values())),
            "global":checks,"patients":patients,"narrative_limit":"Explanation is checked for nonempty text only."}


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
