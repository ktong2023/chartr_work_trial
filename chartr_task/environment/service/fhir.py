"""Small R4 representation, not a FHIR server or full conformance validator."""
import hashlib
import json
from pathlib import Path
from jsonschema import Draft6Validator

BASE = "https://chartr.example/fhir"
NOW = "2026-09-24T12:00:00Z"
VERSION = "chartr-treatment-review-0.1.0"
STATUS = {"open": "requested", "needs_clarification": "requested", "resolved": "completed"}
REASONS = {"UNRESOLVED_TREATMENT_CONCERN", "CONFLICTING_ACTIVE_PLANS"}
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


def episode(resource):
    if resource["resourceType"] == "EpisodeOfCare":
        return resource["id"]
    return next(e["valueReference"]["reference"].split("/")[1]
                for e in resource.get("extension", []) if e["url"].endswith("/episode"))


def review(item_id, patient, ep, reason, status, evidence, explanation, sources, created=NOW, seq=0):
    task = {
        "resourceType": "Task", "id": item_id, "intent": "order", "status": STATUS[status],
        "businessStatus": concept("review-status", status), "code": concept("category", "treatment_review"),
        "reasonCode": concept("review-reason", reason), "for": {"reference": "Patient/" + patient},
        "focus": {"reference": "EpisodeOfCare/" + ep},
        "owner": {"reference": "Organization/clinical-review"},
        "authoredOn": created, "lastModified": NOW if seq else created,
        "description": explanation,
        "extension": [extension("episode", "Reference", {"reference": "EpisodeOfCare/" + ep}),
                      extension("event-sequence", "Integer", seq)],
        "input": [{"type": concept("input", "evidence"),
                   "valueReference": {"reference": sources[e]["resourceType"] + "/" + e}}
                  for e in sorted(set(evidence))],
    }
    validate(task)
    return task
