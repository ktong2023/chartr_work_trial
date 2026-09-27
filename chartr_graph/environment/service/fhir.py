"""Small R4 representation, not a FHIR server or full conformance validator."""
import hashlib
import json
from pathlib import Path
from jsonschema import Draft6Validator

BASE = "https://chartr.example/fhir"
NOW = "2026-09-24T12:00:00Z"
VERSION = "chartr-interacting-requirements-0.1.0"
STATUSES = ("no_requirement", "not_due", "overdue", "completed", "unclear", "blocked")
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


def determination(item_id, patient, ep, checkpoint, status, plan, course, doses, completion_date, due_date, result, branch, paused_days, explanation, sources, seq=0):
    extensions = [extension("episode", "Reference", {"reference": "EpisodeOfCare/"+ep}), extension("event-sequence", "Integer", seq)]
    for name,value in (("completion-date",completion_date),("due-date",due_date)):
        if value: extensions.append(extension(name,"Date",value))
    extensions.append(extension("checkpoint","Code",checkpoint))
    if branch is not None: extensions.append(extension("schedule-branch","Code",branch))
    if paused_days is not None: extensions.append(extension("paused-days","Integer",paused_days))
    inputs = [{"type":concept("input",role),"valueReference":{"reference":sources[ref]["resourceType"]+"/"+ref}}
              for role,ref in [("plan",plan),("course",course),("result",result)]+[("dose",d) for d in doses] if ref]
    task={"resourceType":"Task","id":item_id,"intent":"order","status":"completed",
          "businessStatus":concept("determination-status",status),"code":concept("category","follow_up_determination"),
          "for":{"reference":"Patient/"+patient},"focus":{"reference":"EpisodeOfCare/"+ep},
          "authoredOn":NOW,"lastModified":NOW,"description":explanation,"extension":extensions}
    if inputs: task["input"]=inputs
    validate(task)
    return task


def submission(task):
    data={"status":task["businessStatus"]["coding"][0]["code"],"plan":None,"course":None,"result":None,"doses":[],
          "completion_date":None,"due_date":None,"branch":None,"paused_days":None,"explanation":task["description"]}
    for i in task.get("input",[]):
        key=i["type"]["coding"][0]["code"];value=i["valueReference"]["reference"].split("/")[-1]
        if key=="dose":data["doses"].append(value)
        else:data[key]=value
    for e in task["extension"]:
        key=e["url"].split("/")[-1].replace("-","_")
        if key in ("completion_date","due_date"):data[key]=e["valueDate"]
        if key=='schedule_branch':data['branch']=e['valueCode']
        if key=='paused_days':data[key]=e['valueInteger']
    return data
