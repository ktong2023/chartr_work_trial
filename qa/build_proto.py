"""Build the follow-up induction prototype's fixture and private answer files from the case facts."""
import base64
import datetime as dt
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TASK = ROOT / "chartr_proto"
sys.path[:0] = [str(TASK / "environment/service"), str(ROOT / "qa")]
from fhir import NOW, VERSION, concept, digest, determination, extension, validate  # noqa: E402
from proto_cases import CURRENT, HISTORY  # noqa: E402
from proto_rules import answer, coverage, determine  # noqa: E402

CLINICIANS = ["Casey Nguyen", "Jordan Blake", "Alex Moreno", "Priya Raman", "Luis Ortega", "Hana Sato"]
NURSES = ["Riley Chen", "Sam Ortiz", "Dana Kim", "Pat Quinn"]
FRONT_DESK = ["Avery Hughes", "Chris Lowe"]
FIRST = ["Elena", "Marcus", "Tessa", "Wendell", "Nadia", "Owen", "Grace", "Rafael", "Dmitri", "Aisha", "Lucia",
         "Theo", "Brianna", "Kofi", "Ingrid", "Mei", "Samir", "Nia", "Victor", "Hannah", "Leila", "Omar",
         "Beatriz", "Callum", "Yuki", "Amara", "Pieter", "Rosa", "Tomasz", "Imani", "Felix", "Soraya", "Anders",
         "Keiko", "Mateo", "Zara", "Idris"]
LAST = ["Ruiz", "Hale", "Okafor", "Park", "Farrell", "Castillo", "Lindqvist", "Soto", "Volkov", "Rahman",
        "Ferreira", "Nakamura", "Walsh", "Mensah", "Solberg", "Tanaka", "Haddad", "Oyelaran", "Almeida", "Cho",
        "Moradi", "Farouk", "Santos", "Reid", "Watanabe", "Nwosu", "de Vries", "Delgado", "Nowak", "Adeyemi",
        "Brandt", "Karimi", "Holm", "Sato", "Varga", "Ibrahim", "Quist"]
AMBULATORY = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"}


def rid(key):
    """Opaque, stable record ID with no patient, chronology, type or relevance signal."""
    return "R" + str(int(hashlib.sha256(("chartr-proto:" + key).encode()).hexdigest(), 16) % 900000 + 100000)


def pick(seq, pid, salt=""):
    return seq[int(hashlib.sha256((pid + salt).encode()).hexdigest(), 16) % len(seq)]


def day(value, delta=0):
    return (dt.date.fromisoformat(value) + dt.timedelta(days=delta)).isoformat()


def human(value):
    d = dt.date.fromisoformat(value)
    return f"{d:%B} {d.day}"


def plan_text(p):
    if p["due"]:
        return f"Repeat RPR titer due by {p['due']}."
    after = "completing treatment" if p["anchor"] == "completion" else "treatment"
    return f"Repeat RPR titer {p['months']} months after {after}."


def render(case, index):
    pid, sources = case["pid"], []
    ep = "E" + pid[1:]
    first = min(d["date"] for d in case["doses"])
    clinician = pick(CLINICIANS, pid)
    others = [c for c in CLINICIANS if c != clinician]
    nurse, desk = pick(NURSES, pid, "n"), pick(FRONT_DESK, pid, "f")
    sources.append({"resourceType": "Patient", "id": pid, "name": [{"text": f"{FIRST[index]} {LAST[index]}"}]})
    sources.append({"resourceType": "EpisodeOfCare", "id": ep, "status": "active",
                    "patient": {"reference": "Patient/" + pid}, "period": {"start": day(first, -1)}})

    def common(rtype, key, time, role):
        return {"resourceType": rtype, "id": rid(f"{pid}.{key}"),
                "extension": [extension("episode", "Reference", {"reference": "EpisodeOfCare/" + ep}),
                              extension("event-time", "DateTime", time), extension("author-role", "Code", role)],
                "subject": {"reference": "Patient/" + pid}}

    def ref(rtype, key):
        return {"reference": f"{rtype}/{rid(f'{pid}.{key}')}"}

    def note(key, time, role, doctype, author, body, signed=False):
        r = common("DocumentReference", key, time, role)
        r.update(status="current", date=time, description=body, type={"text": doctype}, author=[{"display": author}],
                 content=[{"attachment": {"contentType": "text/plain", "creation": time,
                                          "data": base64.b64encode(body.encode()).decode()}}])
        if signed:
            r.update(docStatus="final", authenticator={"display": author})
        sources.append(r)

    def order(key, time, code, author, status="completed"):
        r = common("ServiceRequest", key, time, "treating-clinician")
        r.update(status=status, intent="order", code={"text": code}, authoredOn=time, requester={"display": author})
        sources.append(r)

    def observation(key, collected, issued, code, value, based_on):
        r = common("Observation", key, collected, "laboratory")
        r.update(status="final", code={"text": code}, effectiveDateTime=collected, issued=issued, valueString=value,
                 performer=[{"display": "Clinic laboratory"}], basedOn=[ref("ServiceRequest", based_on)])
        sources.append(r)

    single = case["regimen"] == "single"
    regimen = ("Benzathine penicillin G 2.4 million units IM once." if single else
               "Benzathine penicillin G 2.4 million units IM weekly for three doses.")
    note("reg", f"{day(first, -1)}T09:00:00Z", "front-desk", "Registration", desk,
         "New patient registration completed. Insurance information recorded.")
    base = case["results"][0]
    order("rpr0order", f"{day(first, -1)}T09:20:00Z", "RPR titer", clinician)
    observation("rpr0", f"{base['collected']}T09:30:00Z", f"{base['collected']}T16:00:00Z", "RPR titer",
                "Reactive, 1:32" if single else "Reactive, 1:16", "rpr0order")
    note("vitals", f"{first}T08:50:00Z", "nurse", "Vital signs", nurse,
         "BP 120/78, HR 72, temperature 36.8 C, RR 14, SpO2 99% on room air.")
    same_day = [p for p in case["plans"] if p["date"] == first and p["role"] == "treating-clinician" and not p["replaces"]]
    diagnosis = ("Primary syphilis: genital ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today."
                 if single else "Latent syphilis of unknown duration: RPR 1:16 with reactive treponemal antibody, no signs "
                 "or symptoms. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today.")
    note("treat", f"{first}T09:00:00Z", "treating-clinician", "Progress note", clinician,
         " ".join([diagnosis] + [plan_text(p) for p in same_day]), True)
    complete = sum(d["status"] == "given" for d in case["doses"]) >= (1 if single else 3)
    rx = common("MedicationRequest", "rx", f"{first}T09:05:00Z", "treating-clinician")
    rx.update(status="completed" if complete else "active", intent="order", authoredOn=f"{first}T09:05:00Z",
              requester={"display": clinician}, medicationCodeableConcept={"text": "Benzathine penicillin G"},
              dosageInstruction=[{"text": regimen}], supportingInformation=[ref("DocumentReference", "treat")])
    sources.append(rx)
    seen = {}
    for n, dose in enumerate(sorted(case["doses"], key=lambda d: d["date"]), 1):
        seen[dose["date"]] = seen.get(dose["date"], 0) + 1
        time = f"{dose['date']}T09:30:00Z" if seen[dose["date"]] == 1 else f"{dose['date']}T11:40:00Z"
        r = common("MedicationAdministration", f"d{n}", time, "nurse")
        r.update(status="completed", medicationCodeableConcept={"text": "Benzathine penicillin G"},
                 effectiveDateTime=time, request=ref("MedicationRequest", "rx"),
                 dosage={"text": "2.4 million units IM"}, performer=[{"actor": {"display": nurse}}])
        sources.append(r)
        if dose["status"] == "duplicate":
            note(f"d{n}note", f"{dose['date']}T12:00:00Z", "nurse", "Nursing note", nurse,
                 f"The {human(dose['date'])} injection was charted twice; one injection was given.")
        if dose["status"] == "not_given":
            note(f"d{n}note", f"{dose['date']}T11:00:00Z", "nurse", "Nursing note", nurse,
                 f"The {human(dose['date'])} injection was charted in error; the patient left before it was given.")
    for n, restart in enumerate(case["restarts"], 1):
        note(f"restart{n}", f"{restart['date']}T09:00:00Z", "treating-clinician", "Progress note", others[0],
             "More than 14 days since the previous dose; restarting the three-dose series today.", True)
        if restart.get("retracted"):
            note(f"restart{n}corr", f"{day(restart['date'], 18)}T16:00:00Z", "treating-clinician", "Addendum",
                 others[0], f"Correction to the {human(restart['date'])} note: the interval since the previous dose "
                 "was within the 14-day window, so no restart was needed and the original series continued.", True)
    for n, p in enumerate(case["plans"]):
        nurse_plan = p["role"] == "nurse"
        author = nurse if nurse_plan else (clinician if p["date"] == first and not p["replaces"] else others[1 + n % 4])
        time = f"{p['date']}T{'09:10' if p in same_day else '14:10'}:00Z"
        if p not in same_day:
            text = plan_text(p)
            replaced = [q for q in case["plans"] if q["key"] in p["replaces"]]
            sentence = "".join(f" This replaces the follow-up plan from {human(q['date'])}." for q in replaced)
            if nurse_plan:
                note(f"{p['key']}note", f"{p['date']}T14:00:00Z", "nurse", "Nursing note", nurse,
                     f"Entered a follow-up recall per clinic protocol: {text}{sentence}")
            else:
                note(f"{p['key']}note", f"{p['date']}T14:00:00Z", "treating-clinician", "Progress note", author,
                     f"Follow-up visit. {text}{sentence}", True)
        r = common("ServiceRequest", p["key"], time, "nurse" if nurse_plan else "treating-clinician")
        r.update(status="active", intent="plan", code={"text": "RPR titer"}, authoredOn=time,
                 requester={"display": author}, note=[{"text": plan_text(p)}],
                 supportingInfo=[ref("DocumentReference", "treat" if p in same_day else f"{p['key']}note")])
        sources.append(r)
        if p.get("retracted"):
            note(f"{p['key']}retract", f"{day(p['date'], 1)}T09:00:00Z", "treating-clinician", "Addendum", author,
                 f"The {human(p['date'])} progress note and its follow-up plan were entered on this chart in error "
                 "and are retracted.", True)
    for res in case["results"][1:]:
        key, collected = res["key"], res["collected"]
        if res["source"] == "outside":
            note(key, f"{day(collected, 5)}T14:20:00Z", "front-desk", "Outside lab report", desk,
                 f"Scanned outside laboratory report from County Public Health Laboratory. Specimen collected "
                 f"{collected}. Test: RPR titer. Result: reactive, 1:2.")
            continue
        hiv = res["test"] == "HIV"
        order(f"{key}order", f"{collected}T09:00:00Z", "HIV-1/2 antigen/antibody" if hiv else "RPR titer", clinician)
        observation(key, f"{collected}T09:20:00Z", f"{day(collected, 1)}T08:00:00Z",
                    "HIV-1/2 antigen/antibody" if hiv else "RPR titer", "Nonreactive" if hiv else "Reactive, 1:4",
                    f"{key}order")
        if res.get("rejected"):
            note(f"{key}reject", f"{day(collected, 4)}T11:00:00Z", "laboratory", "Laboratory communication",
                 "Clinic laboratory", f"The specimen collected {collected} was hemolyzed. The RPR result reported "
                 f"{day(collected, 1)} is invalid and has been rejected. Recollection requested.")
    for b in case["bookings"]:
        note(b["key"], f"{b['booked']}T13:00:00Z", "front-desk", "Scheduling note", desk,
             f"Patient called to book a follow-up blood test visit. Booked for {b['visit']} 09:30.")
        r = common("Encounter", b["key"] + "visit", f"{b['visit']}T09:30:00Z", "front-desk")
        r.update({"status": "planned", "class": AMBULATORY, "type": [{"text": "Follow-up visit"}],
                  "reasonCode": [{"text": "Repeat RPR titer"}], "period": {"start": f"{b['visit']}T09:30:00Z"}})
        sources.append(r)
    for m in case["selfreports"]:
        note(m["key"], f"{m['date']}T19:00:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
             "Patient writes that they had a follow-up blood test at a community health fair last month and that "
             "everything was fine.")
    note("msg", f"{min(day(first, 40), '2026-09-20')}T18:15:00Z", "telephone-staff", "Patient portal message",
         "Taylor Brooks",
         pick(["Patient asked for clinic parking information. Parking details sent.",
               "Patient asked to update their pharmacy. Pharmacy updated.",
               "Patient asked for a copy of their visit receipt. Sent through the portal."], pid, "m"))
    size = len(json.dumps({"complete": True, "resources": sources}, indent=2))
    if size > 30000:  # adapter tool output is capped at 100,000 characters
        raise RuntimeError(f"{pid} chart is {size} characters; keep charts under 30,000")
    return sources


def build():
    sources, history_tasks, expected, answers = [], [], {}, {}
    for index, case in enumerate(HISTORY + CURRENT):
        sources += render(case, index)
    by_id = {r["id"]: r for r in sources}
    for n, case in enumerate(HISTORY):
        status, plan, due, completion = answer(case)
        pid = case["pid"]
        history_tasks.append(determination(
            f"D{101 + n}", pid, "E" + pid[1:], status, rid(f"{pid}.{plan}") if plan else None, due,
            rid(f"{pid}.{completion}") if completion else None, "Reviewed by follow-up coordination.", by_id))
    for case in CURRENT:
        pid, result = case["pid"], determine(case)
        status, plan, due, completion = answer(case)
        expected[pid] = {"status": result["status"], "plan": rid(f"{pid}.{plan}") if plan else None, "due_date": due,
                         "completion": [rid(f"{pid}.{k}") for k in result["completion"]]}
        answers[pid] = {"patient": pid, "status": status, "plan": expected[pid]["plan"], "due_date": due,
                        "completion": rid(f"{pid}.{completion}") if completion else None,
                        "explanation": "Determined by applying the standards shown in the review history."}
    for r in sources + history_tasks:
        validate(r)
    ids = [r["id"] for r in sources]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Record ID collision; change the rid() salt")
    report = coverage(HISTORY, CURRENT)
    weak = {k: v for k, v in report.items() if len(v["refuted_by"]) < 2 or not v["fails_current"]}
    if weak:
        raise RuntimeError(f"Misconceptions not refuted twice by history or not tested by the cohort: {weak}")
    fixture = {"version": VERSION, "evaluation_time": NOW, "cohort": [c["pid"] for c in CURRENT],
               "history_patients": [h["pid"] for h in HISTORY], "sources": sorted(sources, key=lambda r: r["id"]),
               "history": history_tasks}
    return fixture, expected, answers, report


def main():
    fixture, expected, answers, report = build()
    (TASK / "environment/service/fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    (TASK / "tests/baseline.json").write_text(json.dumps({
        "version": VERSION, "evaluation_time": NOW, "initial_digest": digest(fixture),
        "sources_digest": digest(fixture["sources"]), "history_digest": digest(fixture["history"])}, indent=2) + "\n")
    (TASK / "tests/expected.json").write_text(json.dumps(expected, indent=2) + "\n")
    (TASK / "solution/answers.json").write_text(json.dumps(list(answers.values()), indent=2) + "\n")
    print(f"{len(fixture['sources'])} records, {len(fixture['history'])} history determinations, "
          f"{len(expected)} current patients; initial digest {digest(fixture)}")
    for name, r in report.items():
        print(f"  {name:17s} refuted by {len(r['refuted_by'])} precedents; fails {r['fails_current']}")


if __name__ == "__main__":
    main()
