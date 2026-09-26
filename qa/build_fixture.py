"""Regenerate PUBLIC fixtures from the supplied synthetic case facts (no answers)."""
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chartr_task/environment/service"))
from fhir import concept, extension, review, validate, VERSION, NOW, digest


def main():
    sources = []
    patients = [("P101", "Samantha Lee", "E101", "2026-09-23"),
                ("P102", "Darrow Jones", "E102", "2026-08-31"),
                ("P103", "Morgan Patel", "E103", "2026-09-23")]
    for patient, name, ep, start in patients:
        sources.extend([
            {"resourceType": "Patient", "id": patient, "name": [{"text": name}]},
            {"resourceType": "EpisodeOfCare", "id": ep, "status": "active",
             "patient": {"reference": "Patient/" + patient}, "period": {"start": start}},
        ])
    sources.append({"resourceType": "Organization", "id": "clinical-review", "name": "Clinical review"})

    def common(rtype, rid, patient, ep, date, role):
        return {"resourceType": rtype, "id": rid,
                "extension": [extension("episode", "Reference", {"reference": "EpisodeOfCare/" + ep}),
                              extension("event-time", "DateTime", date),
                              extension("author-role", "Code", role)],
                "subject": {"reference": "Patient/" + patient}}

    def note(rid, patient, ep, date, role, doctype, author, body, signed=False):
        # Document type and author display are realistic chart labels; they never encode
        # signature status or authority. Those live only in docStatus/authenticator/author-role.
        r = common("DocumentReference", rid, patient, ep, date, role)
        r.update(status="current", date=date, description=body,
                 type={"text": doctype},
                 author=[{"display": author}],
                 content=[{"attachment": {"contentType": "text/plain", "creation": date,
                                          "data": base64.b64encode(body.encode()).decode()}}])
        if signed:
            r.update(docStatus="final", authenticator={"display": author})
        sources.append(r)

    def med(rid, patient, ep, date, status, intent, medication, instructions, support):
        # Instruction text carries only the clinical instruction. Status, links, cancellation
        # and replacement history are structured fields and are never restated in prose.
        r = common("MedicationRequest", rid, patient, ep, date, "treating-clinician")
        r.update(status=status, intent=intent, authoredOn=date, medicationCodeableConcept={"text": medication},
                 dosageInstruction=[{"text": instructions}],
                 supportingInformation=[{"reference": "DocumentReference/" + s} for s in support])
        sources.append(r)
        return r

    note("S01", "P101", "E101", "2026-09-23T09:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Primary syphilis. Patient reports a penicillin allergy. Considering oral doxycycline as an alternative. Pregnancy status not yet established; treatment selection to be reviewed once pregnancy status is known.", True)
    med("S02", "P101", "E101", "2026-09-23T09:15:00Z", "draft", "proposal", "Doxycycline",
        "Oral doxycycline course (proposed). Not released; pending prescriber review once pregnancy status is known.", ["S01"])
    note("S03", "P101", "E101", "2026-09-23T10:00:00Z", "nurse", "Nursing note", "Riley Chen",
         "Patient reports a late menstrual period. Pregnancy testing requested by clinician; specimen not collected during this visit. Clinician informed.")
    lab = common("ServiceRequest", "S04", "P101", "E101", "2026-09-24T08:00:00Z", "laboratory")
    lab.update(status="active", intent="order", code={"text": "Pregnancy test"},
               note=[{"text": "Specimen not collected. No result available."}],
               supportingInfo=[{"reference": "DocumentReference/S03"}])
    sources.append(lab)
    note("S05", "P101", "E101", "2026-09-24T09:00:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient called; plans to attend clinic today. Message forwarded to treating clinician.")
    old = med("D01", "P102", "E102", "2026-08-31T09:00:00Z", "cancelled", "order", "Benzathine penicillin G",
              "Primary syphilis. Benzathine penicillin G 2.4 million units IM once.", [])
    old.pop("supportingInformation")
    old["statusReason"] = {"text": "Discontinued by prescriber"}
    old["extension"].extend([extension("cancelled-at", "DateTime", "2026-09-01T08:00:00Z"),
                             extension("cancelled-by", "Reference", {"reference": "DocumentReference/D03"}),
                             extension("replaced-by", "Reference", {"reference": "MedicationRequest/D04"})])
    note("D02", "P102", "E102", "2026-08-31T09:20:00Z", "nurse", "Nursing note", "Sam Ortiz",
         "Patient reports prior immediate hives and breathing difficulty after penicillin. Medication not administered. Prescriber contacted.")
    note("D03", "P102", "E102", "2026-09-01T08:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Reviewed nursing report from Aug. 31 of prior immediate hives and breathing difficulty after penicillin. Discontinue the Aug. 31 benzathine penicillin G order. Adult patient; pregnancy not applicable; no documented neurologic, ocular, or auditory symptoms. New plan: oral doxycycline 100 mg twice daily for 14 days. Follow-up arranged.", True)
    replacement = med("D04", "P102", "E102", "2026-09-01T08:10:00Z", "active", "order", "Doxycycline",
                      "Doxycycline 100 mg orally twice daily for 14 days.", ["D03"])
    replacement["priorPrescription"] = {"reference": "MedicationRequest/D01"}
    note("D05", "P102", "E102", "2026-09-15T16:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Patient reports completing the prescribed course. Serologic follow-up planned.", True)
    note("M01", "P103", "E103", "2026-09-23T09:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Latent syphilis; duration cannot be established from the available history. Plan for benzathine penicillin G 2.4 million units IM weekly for three doses.", True)
    med("M02", "P103", "E103", "2026-09-23T09:10:00Z", "active", "order", "Benzathine penicillin G",
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["M01"])
    note("M03", "P103", "E103", "2026-09-23T15:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Assessment: early latent syphilis. Plan for benzathine penicillin G 2.4 million units IM once.", True)
    med("M04", "P103", "E103", "2026-09-23T15:10:00Z", "active", "order", "Benzathine penicillin G",
        "Benzathine penicillin G 2.4 million units IM once.", ["M03"])
    note("M05", "P103", "E103", "2026-09-24T09:00:00Z", "scheduling-staff", "Scheduling note", "Jamie Ellis",
         "First treatment appointment booked for Sept. 24 at 14:00 UTC.")
    # Extraneous same-episode records (v0.1.4). Routine chart content with no bearing on any
    # treatment-review concern; deliberately excluded from the grader's allowed evidence sets,
    # so citing them fails the evidence check. Same note shape, roles and authors as real ones.
    note("S06", "P101", "E101", "2026-09-23T08:40:00Z", "front-desk", "Registration", "Avery Hughes",
         "Insurance information verified. Mailing address and phone number updated. Preferred pharmacy recorded.")
    note("S07", "P101", "E101", "2026-09-23T08:50:00Z", "nurse", "Vital signs", "Riley Chen",
         "BP 118/74, HR 76, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    note("S08", "P101", "E101", "2026-09-24T10:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for clinic parking information. Directions and parking details sent.")
    note("D06", "P102", "E102", "2026-08-31T08:30:00Z", "front-desk", "Registration", "Avery Hughes",
         "Photo ID verified. Emergency contact updated.")
    note("D07", "P102", "E102", "2026-08-31T08:50:00Z", "nurse", "Vital signs", "Sam Ortiz",
         "BP 126/80, HR 70, temperature 36.9 C, RR 16, SpO2 98% on room air.")
    note("D08", "P102", "E102", "2026-09-15T16:30:00Z", "front-desk", "Administrative note", "Avery Hughes",
         "Work attendance letter for today's visit provided at patient request.")
    note("M06", "P103", "E103", "2026-09-23T08:30:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Contact details and insurance recorded.")
    note("M07", "P103", "E103", "2026-09-23T08:45:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 130/84, HR 78, temperature 36.6 C, RR 16, SpO2 99% on room air.")
    note("M08", "P103", "E103", "2026-09-23T18:00:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked whether the clinic validates parking. Replied that validation is available at the front desk.")
    sources.sort(key=lambda r: r["id"])
    queue = [review("Q102", "P102", "E102", "UNRESOLVED_TREATMENT_CONCERN", "open", ["D01", "D02"],
                    "Penicillin order requires prescriber review in light of the reported reaction; medication has not been administered.",
                    {r["id"]: r for r in sources}, created="2026-08-31T09:30:00Z")]
    for r in sources + queue:
        validate(r)
    fixture = {"version": VERSION, "evaluation_time": NOW, "sources": sources, "queue": queue}
    (ROOT / "chartr_task/environment/service/fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    # Independent private integrity baseline. Explicitly regenerate only after fixture review.
    (ROOT / "chartr_task/tests/baseline.json").write_text(json.dumps({"version": VERSION, "evaluation_time": NOW,
        "initial_digest": digest(fixture), "sources_digest": digest(sources), "q102": queue[0]}, indent=2) + "\n")
    print(f"Validated {len(sources) + len(queue)} resources; initial digest {digest(fixture)}")


if __name__ == "__main__":
    main()
