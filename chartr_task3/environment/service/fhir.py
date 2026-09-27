"""Small R4 representation, not a FHIR server or full conformance validator."""
import hashlib
import json
from pathlib import Path
from jsonschema import Draft6Validator

BASE = "https://chartr.example/fhir"
NOW = "2026-09-24T12:00:00Z"
VERSION = "chartr-cohort-audit-0.2.1"
ISSUES = ("INADEQUATE_TREATMENT", "FOLLOW_UP_OVERDUE", "MISFILED_RESULT", "PREGNANCY_TREATMENT_INADEQUATE")
DISPOSITIONS = ("confirmed", "not_an_issue", "cannot_determine")
CODES = ("RESULT_PENDING", "OUTSIDE_RECORD_NOT_RECEIVED", "UNRESOLVED_SOURCE_CONFLICT")
_schema_bytes = (Path(__file__).parent / "schema/fhir.schema.json").read_bytes()
if hashlib.sha256(_schema_bytes).hexdigest() != "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01":
    raise RuntimeError("Pinned HL7 R4 4.0.1 schema checksum mismatch")
SCHEMA = json.loads(_schema_bytes)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def validate(resource):
    schema = {"$ref": "#/definitions/" + resource["resourceType"], "definitions": SCHEMA["definitions"]}
    Draft6Validator(schema).validate(resource)


def concept(system, code):
    return {"coding": [{"system": BASE + "/CodeSystem/" + system, "code": code}]}


def extension(name, kind, value):
    return {"url": BASE + "/StructureDefinition/" + name, "value" + kind: value}


def subject(resource):
    """Patient ID whose chart holds the record, or None for clinic-level records."""
    ref = (resource.get("subject") or resource.get("patient") or {}).get("reference", "")
    return ref.split("/")[1] if ref.startswith("Patient/") else None


def item(item_id, patient, episode, issue, disposition, code, evidence, explanation, sources, seq=0):
    task = {"resourceType": "Task", "id": item_id, "status": "completed", "intent": "order",
            "code": concept("audit-issue", issue), "businessStatus": concept("audit-disposition", disposition),
            "for": {"reference": "Patient/" + patient}, "focus": {"reference": "EpisodeOfCare/" + episode},
            "authoredOn": NOW, "lastModified": NOW, "description": explanation,
            "extension": [extension("event-sequence", "Integer", seq)],
            "input": [{"type": concept("input", "evidence"),
                       "valueReference": {"reference": sources[r]["resourceType"] + "/" + r}} for r in evidence]}
    if code:
        task["extension"].append(extension("missing-evidence", "Code", code))
    validate(task)
    return task


def submission(task):
    return {"issue": task["code"]["coding"][0]["code"],
            "disposition": task["businessStatus"]["coding"][0]["code"],
            "missing_evidence": next((e["valueCode"] for e in task["extension"]
                                      if e["url"].endswith("/missing-evidence")), None),
            "evidence": [i["valueReference"]["reference"].split("/")[-1] for i in task.get("input", [])],
            "explanation": task["description"]}
