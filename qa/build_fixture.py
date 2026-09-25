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

    def note(rid, patient, ep, date, role, body, signed=False):
        r = common("DocumentReference", rid, patient, ep, date, role)
        r.update(status="current", date=date, description=body,
                 type={"text": "Signed clinician note" if signed else role + " note"},
                 author=[{"display": role}],
                 content=[{"attachment": {"contentType": "text/plain", "creation": date,
                                          "data": base64.b64encode(body.encode()).decode()}}])
        if signed:
            r.update(docStatus="final", authenticator={"display": role})
        sources.append(r)

    def med(rid, patient, ep, date, status, intent, medication, instructions, support):
        r = common("MedicationRequest", rid, patient, ep, date, "treating-clinician")
        r.update(status=status, intent=intent, authoredOn=date, medicationCodeableConcept={"text": medication},
                 dosageInstruction=[{"text": instructions}],
                 supportingInformation=[{"reference": "DocumentReference/" + s} for s in support])
        sources.append(r)
        return r

    note("S01", "P101", "E101", "2026-09-23T09:00:00Z", "treating-clinician",
         "Primary syphilis documented. Patient reports a penicillin allergy. Oral doxycycline is being considered as an alternative. Pregnancy status has not been established; treatment selection requires clinician review after assessment.", True)
    med("S02", "P101", "E101", "2026-09-23T09:15:00Z", "draft", "proposal", "Doxycycline",
        "Proposed oral doxycycline course. Draft, not released. Final selection pending the assessment requested in S01.", ["S01"])
    note("S03", "P101", "E101", "2026-09-23T10:00:00Z", "nurse",
         "Patient reports a late menstrual period. Pregnancy testing requested by clinician; specimen not collected during this visit. Clinician informed.")
    lab = common("ServiceRequest", "S04", "P101", "E101", "2026-09-24T08:00:00Z", "order-status")
    lab.update(status="active", intent="order", code={"text": "Pregnancy test"},
               note=[{"text": "Pregnancy test ordered; specimen not collected; no result available."}],
               supportingInfo=[{"reference": "DocumentReference/S03"}])
    sources.append(lab)
    note("S05", "P101", "E101", "2026-09-24T09:00:00Z", "telephone-staff",
         "Patient plans to attend today. Message sent to treating clinician for review. No treatment decision documented in this encounter.")
    old = med("D01", "P102", "E102", "2026-08-31T09:00:00Z", "cancelled", "order", "Benzathine penicillin G",
              "Primary syphilis. Benzathine penicillin G 2.4 million units IM once. Cancelled September 1 at 08:00 by D03; replacement order D04.", [])
    old.pop("supportingInformation")
    old["statusReason"] = {"text": "Cancelled by D03; replaced by D04"}
    old["extension"].extend([extension("cancelled-at", "DateTime", "2026-09-01T08:00:00Z"),
                             extension("cancelled-by", "Reference", {"reference": "DocumentReference/D03"}),
                             extension("replaced-by", "Reference", {"reference": "MedicationRequest/D04"})])
    note("D02", "P102", "E102", "2026-08-31T09:20:00Z", "nurse",
         "Patient reports prior immediate hives and breathing difficulty after penicillin. Medication not administered. Prescriber contacted to reconcile the plan.")
    note("D03", "P102", "E102", "2026-09-01T08:00:00Z", "treating-clinician",
         "Reviewed the reported penicillin reaction. Cancel D01. For this adult patient, for whom pregnancy is not applicable and with no documented neurologic, ocular, or auditory symptoms, use oral doxycycline 100 mg twice daily for 14 days. Follow-up arranged. This replaces the Aug. 31 plan and addresses the medication concern in D02.", True)
    replacement = med("D04", "P102", "E102", "2026-09-01T08:10:00Z", "active", "order", "Doxycycline",
                      "Doxycycline 100 mg orally twice daily for 14 days. Linked to D03 and replacing D01. Order history preserves the replacement relationship.", ["D03"])
    replacement["priorPrescription"] = {"reference": "MedicationRequest/D01"}
    note("D05", "P102", "E102", "2026-09-15T16:00:00Z", "treating-clinician",
         "Patient reports completing the prescribed course. No new treatment concern identified. Planned serologic follow-up remains in place.", True)
    note("M01", "P103", "E103", "2026-09-23T09:00:00Z", "treating-clinician-A",
         "Latent syphilis; duration cannot be established from the available history. Plan for benzathine penicillin G 2.4 million units IM weekly for three doses.", True)
    med("M02", "P103", "E103", "2026-09-23T09:10:00Z", "active", "order", "Benzathine penicillin G",
        "Benzathine penicillin G 2.4 million units IM weekly for three doses. Active. Linked to M01. No cancellation or replacement relationship.", ["M01"])
    note("M03", "P103", "E103", "2026-09-23T15:00:00Z", "treating-clinician-B",
         "Assessment: early latent syphilis. Plan for benzathine penicillin G 2.4 million units IM once. No statement addressing M01 or replacing its plan.", True)
    med("M04", "P103", "E103", "2026-09-23T15:10:00Z", "active", "order", "Benzathine penicillin G",
        "Benzathine penicillin G 2.4 million units IM once. Active. Linked to M03. No cancellation or replacement relationship.", ["M03"])
    note("M05", "P103", "E103", "2026-09-24T09:00:00Z", "scheduling-staff",
         "First treatment appointment booked for Sept. 24 at 14:00 UTC. No medication administration recorded for this episode.")
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
