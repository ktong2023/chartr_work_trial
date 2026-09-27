"""Regenerate PUBLIC fixtures from the supplied synthetic case facts (no answers)."""
import base64
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chartr_task/environment/service"))
from fhir import extension, review, validate, VERSION, NOW, digest

AMBULATORY = {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"}
PATIENTS = [("P101", "Samantha Lee", "E101", "2026-09-23"), ("P102", "Darrow Jones", "E102", "2026-08-31"),
            ("P103", "Morgan Patel", "E103", "2026-09-23"), ("P104", "Elena Ruiz", "E104", "2026-03-17"),
            ("P105", "Marcus Hale", "E105", "2026-02-27"), ("P106", "Tessa Okafor", "E106", "2026-03-04"),
            ("P107", "Wendell Park", "E107", "2026-06-01"), ("P108", "Nadia Farrell", "E108", "2026-02-27"),
            ("P109", "Owen Castillo", "E109", "2026-02-09"), ("P110", "Grace Lindqvist", "E110", "2026-01-19")]


def rid(key):
    """Opaque, stable public record ID. Carries no patient, chronology, record-type or relevance signal;
    the internal key never leaves this generator."""
    return "R" + str(int(hashlib.sha256(("chartr-record:" + key).encode()).hexdigest(), 16) % 900000 + 100000)


def build():
    sources = []
    for patient, name, ep, start in PATIENTS:
        sources.extend([
            {"resourceType": "Patient", "id": patient, "name": [{"text": name}]},
            {"resourceType": "EpisodeOfCare", "id": ep, "status": "active",
             "patient": {"reference": "Patient/" + patient}, "period": {"start": start}},
        ])
    sources.append({"resourceType": "Organization", "id": "clinical-review", "name": "Clinical review"})
    sources.append({"resourceType": "Organization", "id": "follow-up-coordination", "name": "Follow-up coordination"})

    def common(rtype, key, patient, time, role):
        ep = "E" + patient[1:]
        return {"resourceType": rtype, "id": rid(key),
                "extension": [extension("episode", "Reference", {"reference": "EpisodeOfCare/" + ep}),
                              extension("event-time", "DateTime", time),
                              extension("author-role", "Code", role)],
                "subject": {"reference": "Patient/" + patient}}

    def ref(rtype, key):
        return {"reference": rtype + "/" + rid(key)}

    def note(key, patient, time, role, doctype, author, body, signed=False):
        # Document type and author display are realistic chart labels; they never encode
        # signature status or authority. Those live only in docStatus/authenticator/author-role.
        r = common("DocumentReference", key, patient, time, role)
        r.update(status="current", date=time, description=body, type={"text": doctype},
                 author=[{"display": author}],
                 content=[{"attachment": {"contentType": "text/plain", "creation": time,
                                          "data": base64.b64encode(body.encode()).decode()}}])
        if signed:
            r.update(docStatus="final", authenticator={"display": author})
        sources.append(r)
        return r

    def med(key, patient, time, status, intent, medication, instructions, support, prescriber):
        # Instruction text carries only the clinical instruction. Status, links, cancellation
        # and replacement history are structured fields and are never restated in prose.
        r = common("MedicationRequest", key, patient, time, "treating-clinician")
        r.update(status=status, intent=intent, authoredOn=time, requester={"display": prescriber},
                 medicationCodeableConcept={"text": medication}, dosageInstruction=[{"text": instructions}])
        if support:
            r["supportingInformation"] = [ref("DocumentReference", s) for s in support]
        sources.append(r)
        return r

    def dose(key, patient, time, medication, dosage, order, nurse):
        r = common("MedicationAdministration", key, patient, time, "nurse")
        r.update(status="completed", medicationCodeableConcept={"text": medication}, effectiveDateTime=time,
                 request=ref("MedicationRequest", order), dosage={"text": dosage},
                 performer=[{"actor": {"display": nurse}}])
        sources.append(r)

    def service(key, patient, time, intent, status, code, author, text=None, support=(), based_on=None,
                due=None, role="treating-clinician"):
        # intent "plan" is a follow-up plan; intent "order" requests a service such as a test.
        r = common("ServiceRequest", key, patient, time, role)
        r.update(status=status, intent=intent, code={"text": code}, authoredOn=time, requester={"display": author})
        if text:
            r["note"] = [{"text": text}]
        if support:
            r["supportingInfo"] = [ref("DocumentReference", s) for s in support]
        if based_on:
            r["basedOn"] = [ref("ServiceRequest", based_on)]
        if due:
            r["extension"].append(extension("due-by", "Date", due))
        sources.append(r)
        return r

    def result(key, patient, collected, issued, code, value, based_on=None):
        r = common("Observation", key, patient, collected, "laboratory")
        r.update(status="final", code={"text": code}, effectiveDateTime=collected, issued=issued,
                 valueString=value, performer=[{"display": "Clinic laboratory"}])
        if based_on:
            r["basedOn"] = [ref("ServiceRequest", based_on)]
        sources.append(r)

    def visit(key, patient, start, status, role, vtype, reason, end=None):
        r = common("Encounter", key, patient, start, role)
        r.update({"status": status, "class": AMBULATORY, "type": [{"text": vtype}],
                  "reasonCode": [{"text": reason}], "period": {"start": start, **({"end": end} if end else {})}})
        sources.append(r)

    def rpr(key, patient, collected, issued, titer):
        result(key, patient, collected, issued, "RPR titer", "Reactive, " + titer)

    bpg, bpg_dose = "Benzathine penicillin G", "2.4 million units IM"
    once = "Benzathine penicillin G 2.4 million units IM once."
    doxy = "Doxycycline 100 mg orally twice daily for 14 days."

    # P101 Samantha Lee
    note("S01", "P101", "2026-09-23T09:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Primary syphilis. Patient reports a penicillin allergy. Considering oral doxycycline as an alternative. Pregnancy status not yet established; treatment selection to be reviewed once pregnancy status is known.", True)
    med("S02", "P101", "2026-09-23T09:15:00Z", "draft", "proposal", "Doxycycline",
        "Oral doxycycline course (proposed). Not released; pending prescriber review once pregnancy status is known.", ["S01"], "Casey Nguyen")
    note("S03", "P101", "2026-09-23T10:00:00Z", "nurse", "Nursing note", "Riley Chen",
         "Patient reports a late menstrual period. Pregnancy testing requested by clinician; specimen not collected during this visit. Clinician informed.")
    lab = common("ServiceRequest", "S04", "P101", "2026-09-24T08:00:00Z", "laboratory")
    lab.update(status="active", intent="order", code={"text": "Pregnancy test"}, authoredOn="2026-09-24T08:00:00Z",
               note=[{"text": "Specimen not collected. No result available."}],
               supportingInfo=[ref("DocumentReference", "S03")])
    sources.append(lab)
    note("S05", "P101", "2026-09-24T09:00:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient called; plans to attend clinic today. Message forwarded to treating clinician.")
    note("S06", "P101", "2026-09-23T08:40:00Z", "front-desk", "Registration", "Avery Hughes",
         "Insurance information verified. Mailing address and phone number updated. Preferred pharmacy recorded.")
    note("S07", "P101", "2026-09-23T08:50:00Z", "nurse", "Vital signs", "Riley Chen",
         "BP 118/74, HR 76, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    note("S08", "P101", "2026-09-24T10:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for clinic parking information. Directions and parking details sent.")

    # P102 Darrow Jones
    old = med("D01", "P102", "2026-08-31T09:00:00Z", "cancelled", "order", bpg,
              "Primary syphilis. Benzathine penicillin G 2.4 million units IM once.", [], "Jordan Blake")
    old["statusReason"] = {"text": "Discontinued by prescriber"}
    old["extension"].extend([extension("cancelled-at", "DateTime", "2026-09-01T08:00:00Z"),
                             extension("cancelled-by", "Reference", ref("DocumentReference", "D03")),
                             extension("replaced-by", "Reference", ref("MedicationRequest", "D04"))])
    note("D02", "P102", "2026-08-31T09:20:00Z", "nurse", "Nursing note", "Sam Ortiz",
         "Patient reports prior immediate hives and breathing difficulty after penicillin. Medication not administered. Prescriber contacted.")
    note("D03", "P102", "2026-09-01T08:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Reviewed nursing report from Aug. 31 of prior immediate hives and breathing difficulty after penicillin. Discontinue the Aug. 31 benzathine penicillin G order. Adult patient; pregnancy not applicable; no documented neurologic, ocular, or auditory symptoms. New plan: oral doxycycline 100 mg twice daily for 14 days. Follow-up arranged.", True)
    replacement = med("D04", "P102", "2026-09-01T08:10:00Z", "active", "order", "Doxycycline", doxy, ["D03"], "Jordan Blake")
    replacement["priorPrescription"] = ref("MedicationRequest", "D01")
    note("D05", "P102", "2026-09-15T16:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Patient reports completing the prescribed course. Serologic follow-up planned.", True)
    service("D09", "P102", "2026-09-15T16:05:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer due by 2027-03-15.", ["D05"], due="2027-03-15")
    note("D06", "P102", "2026-08-31T08:30:00Z", "front-desk", "Registration", "Avery Hughes",
         "Photo ID verified. Emergency contact updated.")
    note("D07", "P102", "2026-08-31T08:50:00Z", "nurse", "Vital signs", "Sam Ortiz",
         "BP 126/80, HR 70, temperature 36.9 C, RR 16, SpO2 98% on room air.")
    note("D08", "P102", "2026-09-15T16:30:00Z", "front-desk", "Administrative note", "Avery Hughes",
         "Work attendance letter for today's visit provided at patient request.")

    # P103 Morgan Patel
    note("M01", "P103", "2026-09-23T09:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Latent syphilis; duration cannot be established from the available history. Plan for benzathine penicillin G 2.4 million units IM weekly for three doses.", True)
    med("M02", "P103", "2026-09-23T09:10:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["M01"], "Alex Moreno")
    note("M03", "P103", "2026-09-23T15:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Assessment: early latent syphilis. Plan for benzathine penicillin G 2.4 million units IM once.", True)
    med("M04", "P103", "2026-09-23T15:10:00Z", "active", "order", bpg, once, ["M03"], "Priya Raman")
    note("M05", "P103", "2026-09-24T09:00:00Z", "scheduling-staff", "Scheduling note", "Jamie Ellis",
         "First treatment appointment booked for Sept. 24 at 14:00 UTC.")
    note("M06", "P103", "2026-09-23T08:30:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Contact details and insurance recorded.")
    note("M07", "P103", "2026-09-23T08:45:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 130/84, HR 78, temperature 36.6 C, RR 16, SpO2 99% on room air.")
    note("M08", "P103", "2026-09-23T18:00:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked whether the clinic validates parking. Replied that validation is available at the front desk.")

    # P104 Elena Ruiz
    note("P104.reg", "P104", "2026-03-17T08:10:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance card scanned.")
    rpr("P104.rpr0", "P104", "2026-03-17T08:40:00Z", "2026-03-17T16:20:00Z", "1:16")
    service("P104.sti", "P104", "2026-03-17T08:35:00Z", "order", "completed",
            "Chlamydia and gonorrhea NAAT", "Luis Ortega")
    result("P104.stires", "P104", "2026-03-17T08:40:00Z", "2026-03-18T12:00:00Z",
           "Chlamydia trachomatis and Neisseria gonorrhoeae NAAT", "Not detected", "P104.sti")
    note("P104.vitals", "P104", "2026-03-18T09:10:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 122/78, HR 72, temperature 36.8 C, RR 14, SpO2 99% on room air.")
    note("P104.note", "P104", "2026-03-18T09:30:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Latent syphilis of unknown duration: RPR 1:16 with reactive treponemal antibody, no signs or symptoms, no prior test results available. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 6 months after the final dose.", True)
    med("P104.rx", "P104", "2026-03-18T09:40:00Z", "completed", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P104.note"], "Luis Ortega")
    service("P104.plan", "P104", "2026-03-18T09:45:00Z", "plan", "active", "RPR titer", "Luis Ortega",
            "Repeat RPR titer 6 months after the final dose of benzathine penicillin G.", ["P104.note"])
    dose("P104.d1", "P104", "2026-03-18T10:05:00Z", bpg, bpg_dose, "P104.rx", "Pat Quinn")
    dose("P104.d2", "P104", "2026-03-25T10:10:00Z", bpg, bpg_dose, "P104.rx", "Riley Chen")
    note("P104.nurse", "P104", "2026-03-25T10:25:00Z", "nurse", "Nursing note", "Riley Chen",
         "Second weekly injection given. Patient tolerated it well and left in stable condition.")
    dose("P104.d3", "P104", "2026-04-01T09:55:00Z", bpg, bpg_dose, "P104.rx", "Pat Quinn")
    note("P104.recall", "P104", "2026-04-01T10:30:00Z", "scheduling-staff", "Recall note", "Jamie Ellis",
         "Added to RPR recall list. Recall reminder set for 2026-09-17.")
    note("P104.book", "P104", "2026-09-17T13:15:00Z", "front-desk", "Scheduling note", "Avery Hughes",
         "Patient called after recall reminder. Follow-up blood test visit booked for 2026-09-29 08:45.")
    visit("P104.visit", "P104", "2026-09-29T08:45:00Z", "planned", "front-desk", "Follow-up visit", "Repeat RPR titer")

    # P105 Marcus Hale
    note("P105.reg", "P105", "2026-02-27T13:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "Photo ID verified. Insurance information recorded.")
    rpr("P105.rpr0", "P105", "2026-02-27T13:40:00Z", "2026-02-28T09:15:00Z", "1:64")
    note("P105.vitals", "P105", "2026-03-01T09:50:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 128/82, HR 80, temperature 36.9 C, RR 16, SpO2 98% on room air.")
    note("P105.note", "P105", "2026-03-01T10:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Primary syphilis: painless penile ulcer, RPR 1:64. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 6 months after treatment.", True)
    med("P105.rx", "P105", "2026-03-01T10:05:00Z", "completed", "order", bpg, once, ["P105.note"], "Luis Ortega")
    service("P105.plan", "P105", "2026-03-01T10:10:00Z", "plan", "active", "RPR titer", "Luis Ortega",
            "Repeat RPR titer 6 months after treatment.", ["P105.note"])
    dose("P105.dose", "P105", "2026-03-01T10:20:00Z", bpg, bpg_dose, "P105.rx", "Dana Kim")
    note("P105.msg0", "P105", "2026-06-03T18:05:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked to change his preferred pharmacy. Pharmacy updated.")
    note("P105.cnote", "P105", "2026-05-06T15:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Seen for a right ankle sprain after a fall while running. Swelling without bony tenderness. Ice, elevation and ibuprofen as needed.", True)
    note("P105.recall", "P105", "2026-09-03T11:00:00Z", "scheduling-staff", "Recall note", "Jamie Ellis",
         "Recall call for follow-up blood test. Patient declined to schedule. Removed from recall list.")
    note("P105.msg1", "P105", "2026-09-10T19:20:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient writes that he was tested at a community health fair in August and that \"everything was fine.\" Asked patient to upload the report.")

    # P106 Tessa Okafor
    note("P106.reg", "P106", "2026-03-04T11:30:00Z", "front-desk", "Registration", "Chris Lowe",
         "Registration completed. Mailing address confirmed.")
    rpr("P106.rpr0", "P106", "2026-03-04T12:10:00Z", "2026-03-04T17:45:00Z", "1:32")
    note("P106.note", "P106", "2026-03-05T09:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Secondary syphilis: diffuse rash including palms and soles, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-09-05.", True)
    med("P106.rx", "P106", "2026-03-05T09:05:00Z", "completed", "order", bpg, once, ["P106.note"], "Casey Nguyen")
    service("P106.plan", "P106", "2026-03-05T09:10:00Z", "plan", "active", "RPR titer", "Casey Nguyen",
            "Repeat RPR titer due by 2026-09-05.", ["P106.note"], due="2026-09-05")
    dose("P106.dose", "P106", "2026-03-05T09:30:00Z", bpg, bpg_dose, "P106.rx", "Dana Kim")
    note("P106.nurse", "P106", "2026-03-05T09:50:00Z", "nurse", "Nursing note", "Dana Kim",
         "Observed 15 minutes after injection. Mild soreness at injection site; resolved before discharge.")
    visit("P106.cvisit", "P106", "2026-06-12T15:00:00Z", "finished", "treating-clinician", "Office visit",
          "Contraception", end="2026-06-12T15:30:00Z")
    note("P106.cnote", "P106", "2026-06-12T15:30:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Contraception visit. Continues combined oral contraceptive; refilled for 12 months. No new symptoms.", True)
    note("P106.book", "P106", "2026-09-18T14:00:00Z", "front-desk", "Scheduling note", "Avery Hughes",
         "Patient called to book follow-up blood test visit. Booked for 2026-10-01 09:30.")
    visit("P106.visit", "P106", "2026-10-01T09:30:00Z", "planned", "front-desk", "Follow-up visit", "Repeat RPR titer")

    # P107 Wendell Park
    note("P107.reg", "P107", "2026-06-01T15:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "Registration updated. Emergency contact recorded.")
    rpr("P107.rpr0", "P107", "2026-06-01T15:30:00Z", "2026-06-02T08:05:00Z", "1:8")
    note("P107.note", "P107", "2026-06-02T10:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Early latent syphilis: RPR 1:8 with reactive treponemal antibody; nonreactive syphilis testing in January 2026; no signs or symptoms. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 3 months after treatment.", True)
    med("P107.rx", "P107", "2026-06-02T10:05:00Z", "completed", "order", bpg, once, ["P107.note"], "Alex Moreno")
    service("P107.planA", "P107", "2026-06-02T10:10:00Z", "plan", "active", "RPR titer", "Alex Moreno",
            "Repeat RPR titer 3 months after treatment.", ["P107.note"])
    dose("P107.dose", "P107", "2026-06-02T10:25:00Z", bpg, bpg_dose, "P107.rx", "Sam Ortiz")
    note("P107.vitals", "P107", "2026-07-15T13:50:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 118/76, HR 66, temperature 36.6 C, RR 14, SpO2 99% on room air.")
    note("P107.note2", "P107", "2026-07-15T14:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Visit to discuss syphilis treated in June. No new symptoms. Reviewed prior results and treatment. Plan: repeat RPR titer 6 months after treatment.", True)
    service("P107.planB", "P107", "2026-07-15T14:10:00Z", "plan", "active", "RPR titer", "Priya Raman",
            "Repeat RPR titer 6 months after treatment.", ["P107.note2"])
    note("P107.cnote", "P107", "2026-08-05T10:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Seen for three days of cough and sore throat. Viral upper respiratory infection. Supportive care.", True)
    note("P107.msg", "P107", "2026-08-20T09:40:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient updated his email address.")

    # P108 Nadia Farrell
    note("P108.reg", "P108", "2026-02-27T10:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "Registration completed. Insurance information recorded.")
    rpr("P108.rpr0", "P108", "2026-02-27T10:30:00Z", "2026-02-28T08:40:00Z", "1:32")
    note("P108.note", "P108", "2026-03-01T11:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Primary syphilis: genital ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-09-01, and again 12 months after treatment.", True)
    med("P108.rx", "P108", "2026-03-01T11:05:00Z", "completed", "order", bpg, once, ["P108.note"], "Jordan Blake")
    service("P108.plan6", "P108", "2026-03-01T11:10:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer due by 2026-09-01.", ["P108.note"], due="2026-09-01")
    service("P108.plan12", "P108", "2026-03-01T11:12:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 12 months after treatment.", ["P108.note"])
    note("P108.cnote", "P108", "2026-04-22T14:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Travel consultation before a trip abroad. Hepatitis A vaccine given. Traveler's diarrhea precautions reviewed.", True)
    dose("P108.dose", "P108", "2026-03-01T11:20:00Z", bpg, bpg_dose, "P108.rx", "Riley Chen")
    note("P108.vitals", "P108", "2026-09-15T09:50:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 116/72, HR 74, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    service("P108.order", "P108", "2026-09-15T10:00:00Z", "order", "completed", "RPR titer", "Jordan Blake",
            based_on="P108.plan6")
    service("P108.sti", "P108", "2026-09-15T10:02:00Z", "order", "completed",
            "Chlamydia and gonorrhea NAAT", "Jordan Blake")
    result("P108.rpr1", "P108", "2026-09-15T10:30:00Z", "2026-09-16T08:00:00Z", "RPR titer", "Reactive, 1:2", "P108.order")
    result("P108.stires", "P108", "2026-09-15T10:30:00Z", "2026-09-16T11:30:00Z",
           "Chlamydia trachomatis and Neisseria gonorrhoeae NAAT", "Not detected", "P108.sti")
    note("P108.review", "P108", "2026-09-17T09:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Reviewed repeat RPR: 1:2, down from 1:32 at diagnosis. Next RPR titer 12 months after treatment as planned.", True)

    # P109 Owen Castillo
    note("P109.reg", "P109", "2026-02-09T14:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Contact details recorded.")
    rpr("P109.rpr0", "P109", "2026-02-09T14:30:00Z", "2026-02-09T19:10:00Z", "1:64")
    note("P109.vitals", "P109", "2026-02-10T08:50:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 124/80, HR 82, temperature 37.0 C, RR 16, SpO2 98% on room air.")
    note("P109.note", "P109", "2026-02-10T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Secondary syphilis: generalized rash and oral mucous patches, RPR 1:64. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 6 months after treatment.", True)
    med("P109.rx", "P109", "2026-02-10T09:05:00Z", "completed", "order", bpg, once, ["P109.note"], "Hana Sato")
    service("P109.plan", "P109", "2026-02-10T09:10:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer 6 months after treatment.", ["P109.note"])
    dose("P109.dose", "P109", "2026-02-10T09:25:00Z", bpg, bpg_dose, "P109.rx", "Pat Quinn")
    note("P109.msg", "P109", "2026-04-02T12:15:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient requested a copy of his vaccination record. Sent through the portal.")
    note("P109.cnote", "P109", "2026-05-14T11:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Seen for seasonal allergies with sneezing and itchy eyes. Loratadine 10 mg daily as needed.", True)
    note("P109.tel", "P109", "2026-09-07T10:20:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient called to confirm the time of tomorrow's vaccine appointment. Confirmed 15:00.")
    visit("P109.visit", "P109", "2026-09-08T15:00:00Z", "finished", "nurse", "Nurse visit",
          "Hepatitis B vaccine dose 2", end="2026-09-08T15:30:00Z")
    service("P109.hivorder", "P109", "2026-09-08T15:10:00Z", "order", "completed",
            "HIV-1/2 antigen/antibody", "Hana Sato")
    note("P109.nurse", "P109", "2026-09-08T15:20:00Z", "nurse", "Nursing note", "Pat Quinn",
         "Hepatitis B vaccine dose 2 of 3 given, left deltoid. HIV test collected at patient request.")
    result("P109.hiv", "P109", "2026-09-08T15:25:00Z", "2026-09-09T10:00:00Z",
           "HIV-1/2 antigen/antibody", "Nonreactive", "P109.hivorder")

    # P110 Grace Lindqvist
    note("P110.reg", "P110", "2026-01-19T09:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "Registration completed. Insurance card scanned.")
    rpr("P110.rpr0", "P110", "2026-01-19T09:30:00Z", "2026-01-19T16:00:00Z", "1:16")
    note("P110.note", "P110", "2026-01-20T10:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Primary syphilis: vulvar ulcer, RPR 1:16. History of anaphylaxis to penicillin. Urine pregnancy test negative. Doxycycline 100 mg orally twice daily for 14 days. Repeat RPR titer due by 2026-07-20.", True)
    first = med("P110.rx1", "P110", "2026-01-20T10:05:00Z", "stopped", "order", "Doxycycline", doxy, ["P110.note"], "Casey Nguyen")
    first["statusReason"] = {"text": "Stopped by patient after about 5 days because of nausea"}
    r1 = service("P110.plan1", "P110", "2026-01-20T10:10:00Z", "plan", "revoked", "RPR titer", "Casey Nguyen",
                 "Repeat RPR titer due by 2026-07-20.", ["P110.note"], due="2026-07-20")
    r1["extension"].extend([extension("cancelled-at", "DateTime", "2026-08-28T11:00:00Z"),
                            extension("cancelled-by", "Reference", ref("DocumentReference", "P110.note2")),
                            extension("replaced-by", "Reference", ref("ServiceRequest", "P110.plan2"))])
    note("P110.msg", "P110", "2026-05-11T08:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked about clinic hours on Memorial Day. Replied with holiday hours.")
    note("P110.tel", "P110", "2026-08-26T16:00:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient returned recall call. States she stopped doxycycline after about 5 days in January because of nausea. Message sent to treating clinician.")
    note("P110.vitals", "P110", "2026-08-28T10:45:00Z", "nurse", "Vital signs", "Sam Ortiz",
         "BP 112/70, HR 68, temperature 36.5 C, RR 14, SpO2 100% on room air.")
    note("P110.note2", "P110", "2026-08-28T11:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Seen after report of stopping doxycycline after about 5 days in January because of nausea. January course incomplete. Re-treat with doxycycline 100 mg orally twice daily for 14 days starting today, taken with food. Urine pregnancy test negative. The January follow-up RPR plan is replaced: repeat RPR titer due by 2027-03-10.", True)
    second = med("P110.rx2", "P110", "2026-08-28T11:05:00Z", "active", "order", "Doxycycline", doxy, ["P110.note2"], "Casey Nguyen")
    second["priorPrescription"] = ref("MedicationRequest", "P110.rx1")
    service("P110.plan2", "P110", "2026-08-28T11:10:00Z", "plan", "active", "RPR titer", "Casey Nguyen",
            "Repeat RPR titer due by 2027-03-10.", ["P110.note2"], due="2027-03-10")

    for patient, *_ in PATIENTS:
        chart = [r for r in sources if r.get("subject", r.get("patient", {})).get("reference") == "Patient/" + patient
                 or r["id"] == patient]
        if len(json.dumps({"complete": True, "resources": chart}, indent=2)) > 20000:
            raise RuntimeError(patient + " chart exceeds 20,000 characters")
    ids = [r["id"] for r in sources]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Record ID collision; change the rid() salt")
    sources.sort(key=lambda r: r["id"])
    by_id = {r["id"]: r for r in sources}
    # Seeded items, numbered in creation order; none shares a number with its patient.
    queue = [
        review("Q2081", "P110", "E110", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P110.plan1")],
               "Repeat RPR titer was due by 2026-07-20; no result is on file.", by_id, created="2026-07-25T08:30:00Z"),
        review("Q2146", "P102", "E102", "treatment_review", "UNRESOLVED_TREATMENT_CONCERN", "open", [rid("D01"), rid("D02")],
               "Penicillin order requires prescriber review in light of the reported reaction; medication has not been administered.",
               by_id, created="2026-08-31T09:30:00Z"),
        review("Q2203", "P105", "E105", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P105.plan"), rid("P105.dose")],
               "Repeat RPR titer was due 6 months after the March 1 treatment; no result is on file.", by_id,
               created="2026-09-05T09:00:00Z"),
        review("Q2217", "P108", "E108", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P108.plan6")],
               "Repeat RPR titer was due by 2026-09-01; no result is on file.", by_id, created="2026-09-12T08:00:00Z"),
    ]
    for r in sources + queue:
        validate(r)
    return {"version": VERSION, "evaluation_time": NOW, "sources": sources, "queue": queue}


def main():
    fixture = build()
    (ROOT / "chartr_task/environment/service/fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    # Independent private integrity baseline. Explicitly regenerate only after fixture review.
    (ROOT / "chartr_task/tests/baseline.json").write_text(json.dumps({
        "version": VERSION, "evaluation_time": NOW, "initial_digest": digest(fixture),
        "sources_digest": digest(fixture["sources"]), "queue": fixture["queue"]}, indent=2) + "\n")
    print(f"Validated {len(fixture['sources']) + len(fixture['queue'])} resources; initial digest {digest(fixture)}")


if __name__ == "__main__":
    main()
