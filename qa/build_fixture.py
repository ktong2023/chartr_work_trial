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
            ("P109", "Owen Castillo", "E109", "2026-02-09"), ("P110", "Grace Lindqvist", "E110", "2026-01-19"),
            ("P111", "Rafael Soto", "E111", "2026-09-02"), ("P112", "Dmitri Volkov", "E112", "2026-04-09"),
            ("P113", "Aisha Rahman", "E113", "2026-02-14"), ("P114", "Lucia Ferreira", "E114", "2026-09-16"),
            ("P115", "Theo Nakamura", "E115", "2026-01-11"), ("P116", "Brianna Walsh", "E116", "2026-03-01"),
            ("P117", "Kofi Mensah", "E117", "2026-03-01"), ("P118", "Ingrid Solberg", "E118", "2026-02-25"),
            ("P119", "Mei Tanaka", "E119", "2026-08-31"), ("P120", "Samir Haddad", "E120", "2026-05-04"),
            ("P121", "Nia Oyelaran", "E121", "2026-09-08"), ("P122", "Victor Almeida", "E122", "2026-09-01"),
            ("P123", "Hannah Cho", "E123", "2026-09-02"), ("P124", "Leila Moradi", "E124", "2026-06-09"),
            ("P125", "Omar Farouk", "E125", "2026-09-01"), ("P126", "Beatriz Santos", "E126", "2026-03-01"),
            ("P127", "Callum Reid", "E127", "2026-03-08"), ("P128", "Yuki Watanabe", "E128", "2026-02-19"),
            ("P129", "Amara Nwosu", "E129", "2026-08-31"), ("P130", "Pieter de Vries", "E130", "2026-08-02"),
            ("P131", "Rosa Delgado", "E131", "2026-02-09"), ("P132", "Tomasz Nowak", "E132", "2026-02-22")]
# Calibration switch: patients left out here are absent from the fixture, grader and reference.
# 0.5.0 switches off the eight cases every pilot solved, in favour of the event-history cases.
COHORT = {patient for patient, *_ in PATIENTS} - {"P104", "P106", "P109", "P111", "P113", "P115", "P116", "P120"}


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

    def service(key, patient, time, intent, status, code, author, text=None, support=(), role="treating-clinician"):
        # intent "plan" is a follow-up plan; intent "order" requests a service such as a test.
        # Timing lives only in the text, and plans are not updated after later documentation.
        r = common("ServiceRequest", key, patient, time, role)
        r.update(status=status, intent=intent, code={"text": code}, authoredOn=time, requester={"display": author})
        if text:
            r["note"] = [{"text": text}]
        if support:
            r["supportingInfo"] = [ref("DocumentReference", s) for s in support]
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
            "Repeat RPR titer due by 2027-03-15.", ["D05"])
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
            "Repeat RPR titer due by 2026-09-05.", ["P106.note"])
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
            "Repeat RPR titer due by 2026-09-01.", ["P108.note"])
    service("P108.plan12", "P108", "2026-03-01T11:12:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 12 months after treatment.", ["P108.note"])
    note("P108.cnote", "P108", "2026-04-22T14:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Travel consultation before a trip abroad. Hepatitis A vaccine given. Traveler's diarrhea precautions reviewed.", True)
    dose("P108.dose", "P108", "2026-03-01T11:20:00Z", bpg, bpg_dose, "P108.rx", "Riley Chen")
    note("P108.vitals", "P108", "2026-09-15T09:50:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 116/72, HR 74, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    service("P108.order", "P108", "2026-09-15T10:00:00Z", "order", "completed", "RPR titer", "Jordan Blake")
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
    service("P110.plan1", "P110", "2026-01-20T10:10:00Z", "plan", "active", "RPR titer", "Casey Nguyen",
            "Repeat RPR titer due by 2026-07-20.", ["P110.note"])
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
            "Repeat RPR titer due by 2027-03-10.", ["P110.note2"])

    # P111 Rafael Soto
    note("P111.reg", "P111", "2026-09-03T08:30:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance information recorded.")
    rpr("P111.rpr0", "P111", "2026-09-02T16:00:00Z", "2026-09-03T07:45:00Z", "1:4")
    note("P111.vitals", "P111", "2026-09-03T08:50:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 124/82, HR 70, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    note("P111.note", "P111", "2026-09-03T09:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Latent syphilis of unknown duration: RPR 1:4 with reactive treponemal antibody, no signs or symptoms, no prior test results available. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 6 months after completing treatment.", True)
    med("P111.rxA", "P111", "2026-09-03T09:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P111.note"], "Alex Moreno")
    med("P111.rxB", "P111", "2026-09-03T09:12:00Z", "active", "order", bpg, once, [], "Hana Sato")
    service("P111.plan", "P111", "2026-09-03T09:15:00Z", "plan", "active", "RPR titer", "Alex Moreno",
            "Repeat RPR titer 6 months after completing treatment.", ["P111.note"])
    dose("P111.d1", "P111", "2026-09-03T09:40:00Z", bpg, bpg_dose, "P111.rxA", "Sam Ortiz")
    note("P111.note2", "P111", "2026-09-04T08:15:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Chart review: a single-dose benzathine penicillin G order was entered on 9/3 in error. Discontinue that single-dose order. Continue the weekly three-dose series; next doses 9/10 and 9/17.", True)
    dose("P111.d2", "P111", "2026-09-10T09:35:00Z", bpg, bpg_dose, "P111.rxA", "Riley Chen")
    note("P111.msg", "P111", "2026-09-12T20:10:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for a work note for the 9/10 visit. Sent through the portal.")
    dose("P111.d3", "P111", "2026-09-17T09:30:00Z", bpg, bpg_dose, "P111.rxA", "Sam Ortiz")

    # P112 Dmitri Volkov
    note("P112.reg", "P112", "2026-04-09T15:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "Registration updated. Emergency contact recorded.")
    rpr("P112.rpr0", "P112", "2026-04-09T15:30:00Z", "2026-04-10T08:10:00Z", "1:64")
    note("P112.vitals", "P112", "2026-04-10T09:40:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 132/84, HR 88, temperature 37.1 C, RR 16, SpO2 98% on room air.")
    service("P112.hivorder", "P112", "2026-04-10T09:50:00Z", "order", "completed", "HIV-1/2 antigen/antibody", "Luis Ortega")
    note("P112.note", "P112", "2026-04-10T10:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Secondary syphilis: rash on trunk and palms, RPR 1:64. Benzathine penicillin G 2.4 million units IM once, given today. HIV test sent. Repeat RPR titer 6 months after treatment.", True)
    med("P112.rx", "P112", "2026-04-10T10:05:00Z", "completed", "order", bpg, once, ["P112.note"], "Luis Ortega")
    service("P112.plan", "P112", "2026-04-10T10:10:00Z", "plan", "active", "RPR titer", "Luis Ortega",
            "Repeat RPR titer 6 months after treatment.", ["P112.note"])
    dose("P112.dose", "P112", "2026-04-10T10:25:00Z", bpg, bpg_dose, "P112.rx", "Pat Quinn")
    result("P112.hiv", "P112", "2026-04-10T10:00:00Z", "2026-04-13T09:00:00Z", "HIV-1/2 antigen/antibody",
           "Reactive; HIV-1 confirmed by differentiation assay", "P112.hivorder")
    note("P112.addendum", "P112", "2026-04-14T16:00:00Z", "treating-clinician", "Addendum", "Luis Ortega",
         "Addendum to the 4/10 progress note: HIV-1 infection confirmed; referred to HIV care. Correction to the follow-up plan: repeat RPR titer 3 months after treatment.", True)
    note("P112.sched", "P112", "2026-04-20T11:00:00Z", "scheduling-staff", "Scheduling note", "Jamie Ellis",
         "HIV care intake appointment booked for 2026-04-28 10:00.")

    # P113 Aisha Rahman
    note("P113.reg", "P113", "2026-02-14T11:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance card scanned.")
    rpr("P113.rpr0", "P113", "2026-02-14T11:30:00Z", "2026-02-14T18:00:00Z", "1:32")
    note("P113.vitals", "P113", "2026-02-15T09:45:00Z", "nurse", "Vital signs", "Riley Chen",
         "BP 110/70, HR 72, temperature 36.6 C, RR 14, SpO2 99% on room air.")
    note("P113.note", "P113", "2026-02-15T10:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Primary syphilis: genital ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-08-15.", True)
    med("P113.rx", "P113", "2026-02-15T10:05:00Z", "completed", "order", bpg, once, ["P113.note"], "Priya Raman")
    service("P113.plan", "P113", "2026-02-15T10:10:00Z", "plan", "active", "RPR titer", "Priya Raman",
            "Repeat RPR titer due by 2026-08-15.", ["P113.note"])
    dose("P113.dose", "P113", "2026-02-15T10:25:00Z", bpg, bpg_dose, "P113.rx", "Dana Kim")
    note("P113.msg0", "P113", "2026-05-02T12:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked to update her mailing address. Address updated.")
    note("P113.msg1", "P113", "2026-08-25T19:40:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient writes that she had her follow-up blood test at the county health department last week and that they will send the results.")
    note("P113.outside", "P113", "2026-09-03T14:20:00Z", "front-desk", "Outside lab report", "Avery Hughes",
         "Scanned outside laboratory report from County Public Health Laboratory. Specimen collected 2026-08-28. Test: RPR titer. Result: reactive, 1:2.")

    # P114 Lucia Ferreira
    note("P114.reg", "P114", "2026-09-16T08:30:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Preferred pharmacy recorded.")
    note("P114.vitals", "P114", "2026-09-16T08:50:00Z", "nurse", "Vital signs", "Riley Chen",
         "BP 114/72, HR 78, temperature 36.8 C, RR 14, SpO2 99% on room air.")
    rpr("P114.rpr0", "P114", "2026-09-15T17:00:00Z", "2026-09-16T08:05:00Z", "1:16")
    note("P114.note", "P114", "2026-09-16T09:10:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Primary syphilis: painless vulvar ulcer, RPR 1:16. Reports a penicillin allergy (hives as a child). Considering oral doxycycline as an alternative. Pregnancy status not established; treatment selection to be reviewed once pregnancy status is known.", True)
    med("P114.rx", "P114", "2026-09-16T09:20:00Z", "draft", "proposal", "Doxycycline",
        "Oral doxycycline course (proposed). Not released; pending prescriber review once pregnancy status is known.", ["P114.note"], "Casey Nguyen")
    service("P114.hcgorder", "P114", "2026-09-16T09:25:00Z", "order", "completed", "Serum hCG", "Casey Nguyen")
    result("P114.hcg", "P114", "2026-09-16T09:40:00Z", "2026-09-18T11:00:00Z", "Serum hCG (quantitative)",
           "Negative (<5 mIU/mL)", "P114.hcgorder")
    note("P114.nurse", "P114", "2026-09-18T14:00:00Z", "nurse", "Nursing note", "Riley Chen",
         "Serum pregnancy test negative. Treating clinician notified.")
    note("P114.msg", "P114", "2026-09-19T18:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for directions to the laboratory entrance. Directions sent.")
    note("P114.tel", "P114", "2026-09-22T10:15:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient called asking when she can start treatment. Message forwarded to treating clinician.")

    # P115 Theo Nakamura
    note("P115.reg", "P115", "2026-01-11T10:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "Registration completed. Insurance information recorded.")
    rpr("P115.rpr0", "P115", "2026-01-11T10:30:00Z", "2026-01-11T17:00:00Z", "1:32")
    note("P115.note", "P115", "2026-01-12T09:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Primary syphilis: penile ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 6 months after treatment and again 12 months after treatment.", True)
    med("P115.rx", "P115", "2026-01-12T09:05:00Z", "completed", "order", bpg, once, ["P115.note"], "Jordan Blake")
    service("P115.plan6", "P115", "2026-01-12T09:10:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 6 months after treatment.", ["P115.note"])
    service("P115.plan12", "P115", "2026-01-12T09:12:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 12 months after treatment.", ["P115.note"])
    dose("P115.dose", "P115", "2026-01-12T09:25:00Z", bpg, bpg_dose, "P115.rx", "Sam Ortiz")
    note("P115.addendum", "P115", "2026-01-13T08:00:00Z", "front-desk", "Addendum", "Chris Lowe",
         "Addendum to registration: preferred phone number corrected.")
    note("P115.outside", "P115", "2026-05-20T13:00:00Z", "front-desk", "Outside lab report", "Avery Hughes",
         "Scanned outside laboratory report from an employer health screening. Specimen collected 2026-05-14. Test: lipid panel. Result: within reference ranges.")
    note("P115.vitals", "P115", "2026-07-14T09:50:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 120/78, HR 64, temperature 36.6 C, RR 12, SpO2 99% on room air.")
    service("P115.order", "P115", "2026-07-14T10:00:00Z", "order", "completed", "RPR titer", "Jordan Blake")
    result("P115.rpr1", "P115", "2026-07-14T10:20:00Z", "2026-07-15T08:30:00Z", "RPR titer", "Reactive, 1:4", "P115.order")
    note("P115.review", "P115", "2026-07-16T09:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Reviewed repeat RPR: 1:4, down from 1:32 at diagnosis. Next RPR titer 12 months after treatment as planned.", True)

    # P116 Brianna Walsh
    note("P116.reg", "P116", "2026-03-01T13:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "Registration completed. Contact details confirmed.")
    rpr("P116.rpr0", "P116", "2026-03-01T13:30:00Z", "2026-03-01T19:00:00Z", "1:32")
    note("P116.vitals", "P116", "2026-03-02T09:45:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 108/68, HR 76, temperature 36.9 C, RR 16, SpO2 99% on room air.")
    note("P116.note", "P116", "2026-03-02T10:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Secondary syphilis: rash including palms, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-09-02.", True)
    med("P116.rx", "P116", "2026-03-02T10:05:00Z", "completed", "order", bpg, once, ["P116.note"], "Hana Sato")
    service("P116.plan", "P116", "2026-03-02T10:10:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer due by 2026-09-02.", ["P116.note"])
    dose("P116.dose", "P116", "2026-03-02T10:30:00Z", bpg, bpg_dose, "P116.rx", "Riley Chen")
    note("P116.portal", "P116", "2026-06-18T17:45:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked whether the clinic offers flu vaccines. Replied with vaccine clinic hours.")
    result("P116.misfiled", "P116", "2026-09-11T15:00:00Z", "2026-09-12T09:30:00Z", "RPR titer", "Reactive, 1:8")
    note("P116.nurse", "P116", "2026-09-15T11:40:00Z", "nurse", "Nursing note", "Pat Quinn",
         "Clinic laboratory called: the RPR result filed to this chart on 9/12 is another patient's result and was filed here in error. Treating clinician informed.")

    # P117 Kofi Mensah
    note("P117.reg", "P117", "2026-03-01T14:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Contact details recorded.")
    rpr("P117.rpr0", "P117", "2026-03-01T14:30:00Z", "2026-03-02T08:00:00Z", "1:16")
    note("P117.vitals", "P117", "2026-03-02T08:50:00Z", "nurse", "Vital signs", "Sam Ortiz",
         "BP 128/80, HR 74, temperature 36.7 C, RR 14, SpO2 98% on room air.")
    note("P117.noteA", "P117", "2026-03-02T09:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Latent syphilis; no prior testing available, so duration cannot be established. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer due by 2026-09-02.", True)
    med("P117.rxA", "P117", "2026-03-02T09:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P117.noteA"], "Luis Ortega")
    service("P117.plan", "P117", "2026-03-02T09:10:00Z", "plan", "active", "RPR titer", "Luis Ortega",
            "Repeat RPR titer due by 2026-09-02.", ["P117.noteA"])
    dose("P117.dose", "P117", "2026-03-02T09:30:00Z", bpg, bpg_dose, "P117.rxA", "Dana Kim")
    note("P117.noteB", "P117", "2026-03-05T15:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Outside records received: nonreactive syphilis testing in October 2025, so infection was acquired within the past year. Assessment: early latent syphilis. Plan: benzathine penicillin G 2.4 million units IM once.", True)
    med("P117.rxB", "P117", "2026-03-05T15:05:00Z", "active", "order", bpg, once, ["P117.noteB"], "Jordan Blake")
    note("P117.msg", "P117", "2026-05-10T09:20:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for a copy of his immunization record. Sent through the portal.")
    note("P117.tel", "P117", "2026-09-15T13:20:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient returned recall call about the follow-up blood test. Message sent to treating clinician.")

    # P118 Ingrid Solberg
    note("P118.reg", "P118", "2026-02-25T09:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance card scanned.")
    rpr("P118.rpr0", "P118", "2026-02-25T09:30:00Z", "2026-02-25T16:40:00Z", "1:8")
    note("P118.vitals", "P118", "2026-02-26T09:40:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 116/74, HR 68, temperature 36.5 C, RR 14, SpO2 100% on room air.")
    note("P118.note1", "P118", "2026-02-26T10:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Latent syphilis of unknown duration: RPR 1:8 with reactive treponemal antibody, no signs or symptoms. HIV test pending. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 3 months after completing treatment.", True)
    med("P118.rx", "P118", "2026-02-26T10:05:00Z", "completed", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P118.note1"], "Jordan Blake")
    service("P118.planA", "P118", "2026-02-26T10:10:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 3 months after completing treatment.", ["P118.note1"])
    dose("P118.d1", "P118", "2026-02-26T10:30:00Z", bpg, bpg_dose, "P118.rx", "Pat Quinn")
    result("P118.hiv", "P118", "2026-02-26T10:00:00Z", "2026-03-02T09:00:00Z", "HIV-1/2 antigen/antibody", "Nonreactive")
    dose("P118.d2", "P118", "2026-03-05T10:15:00Z", bpg, bpg_dose, "P118.rx", "Riley Chen")
    note("P118.nurse", "P118", "2026-03-13T16:00:00Z", "nurse", "Nursing note", "Dana Kim",
         "Patient did not attend the third weekly injection appointment on 3/12. Rescheduled; treating clinician informed.")
    note("P118.note2", "P118", "2026-03-20T09:30:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Third dose was not given, and it has been more than 14 days since the second dose. Restarting the full three-dose series today.", True)
    dose("P118.d3", "P118", "2026-03-20T09:50:00Z", bpg, bpg_dose, "P118.rx", "Pat Quinn")
    dose("P118.d4", "P118", "2026-03-27T10:05:00Z", bpg, bpg_dose, "P118.rx", "Sam Ortiz")
    dose("P118.d5", "P118", "2026-04-03T09:45:00Z", bpg, bpg_dose, "P118.rx", "Pat Quinn")
    note("P118.note3", "P118", "2026-04-20T11:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "HIV test nonreactive. Revised follow-up plan: repeat RPR titer 6 months after completing treatment. This replaces the 3-month follow-up plan.", True)
    service("P118.planB", "P118", "2026-04-20T11:10:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer 6 months after completing treatment.", ["P118.note3"])

    # P119 Mei Tanaka
    note("P119.reg", "P119", "2026-08-31T09:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Preferred pharmacy recorded.")
    rpr("P119.rpr0", "P119", "2026-08-31T09:30:00Z", "2026-08-31T17:30:00Z", "1:16")
    note("P119.vitals", "P119", "2026-09-01T09:45:00Z", "nurse", "Vital signs", "Dana Kim",
         "BP 106/66, HR 70, temperature 36.6 C, RR 14, SpO2 99% on room air.")
    note("P119.note", "P119", "2026-09-01T10:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Early latent syphilis: RPR 1:16; nonreactive syphilis testing in March 2026; no signs or symptoms. History of anaphylaxis to penicillin. Doxycycline 100 mg orally twice daily for 14 days.", True)
    med("P119.rx", "P119", "2026-09-01T10:05:00Z", "active", "order", "Doxycycline", doxy, ["P119.note"], "Priya Raman")
    note("P119.tel", "P119", "2026-09-03T11:30:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Pharmacist called: patient also takes isotretinoin, and doxycycline with isotretinoin raises the risk of intracranial hypertension. Pharmacist is holding the doxycycline prescription and requests prescriber review.")
    note("P119.note2", "P119", "2026-09-10T14:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Reviewed penicillin allergy history with patient: anaphylaxis after amoxicillin in 2019. Referred to the allergy clinic for evaluation and possible penicillin desensitization.", True)
    note("P119.msg", "P119", "2026-09-14T17:05:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked whether the clinic validates parking. Replied that validation is available at the front desk.")

    # P120 Samir Haddad
    note("P120.reg", "P120", "2026-05-04T12:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance information recorded.")
    rpr("P120.rpr0", "P120", "2026-05-04T12:30:00Z", "2026-05-04T18:20:00Z", "1:32")
    note("P120.vitals", "P120", "2026-05-05T08:50:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 126/80, HR 72, temperature 36.8 C, RR 14, SpO2 98% on room air.")
    note("P120.note", "P120", "2026-05-05T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Primary syphilis: penile ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 6 months after treatment.", True)
    med("P120.rx", "P120", "2026-05-05T09:05:00Z", "completed", "order", bpg, once, ["P120.note"], "Hana Sato")
    service("P120.plan", "P120", "2026-05-05T09:10:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer 6 months after treatment.", ["P120.note"])
    dose("P120.dose", "P120", "2026-05-05T09:25:00Z", bpg, bpg_dose, "P120.rx", "Dana Kim")
    note("P120.nurse", "P120", "2026-05-05T09:45:00Z", "nurse", "Nursing note", "Dana Kim",
         "Patient education on syphilis treatment and partner notification provided. Entered recall for a repeat RPR in about 3 months.")
    service("P120.nplan", "P120", "2026-05-05T09:50:00Z", "plan", "active", "RPR titer", "Dana Kim",
            "Repeat RPR titer 3 months after treatment.", ["P120.nurse"], role="nurse")
    note("P120.msg", "P120", "2026-07-01T11:10:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for a copy of his visit receipt. Sent through the portal.")


    # P121 Nia Oyelaran
    note("P121.reg", "P121", "2026-09-08T08:20:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Insurance information recorded.")
    rpr("P121.rpr0", "P121", "2026-09-08T08:40:00Z", "2026-09-08T16:30:00Z", "1:64")
    note("P121.vitals", "P121", "2026-09-08T08:55:00Z", "nurse", "Vital signs", "Riley Chen",
         "BP 118/76, HR 74, temperature 36.8 C, RR 14, SpO2 99% on room air.")
    note("P121.noteA", "P121", "2026-09-08T09:10:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Latent syphilis of unknown duration: RPR 1:64 with reactive treponemal antibody; no symptoms reported; no prior test results available. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today.", True)
    med("P121.rxA", "P121", "2026-09-08T09:15:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P121.noteA"], "Alex Moreno")
    dose("P121.dose1", "P121", "2026-09-08T09:35:00Z", bpg, bpg_dose, "P121.rxA", "Riley Chen")
    note("P121.noteB", "P121", "2026-09-11T14:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Follow-up visit. On further history the patient describes a rash on the palms that began about three weeks ago and is fading; exam shows a resolving papular rash on both palms. Assessment: secondary syphilis. Plan: benzathine penicillin G 2.4 million units IM once. Repeat RPR titer due by 2027-03-11.", True)
    med("P121.rxB", "P121", "2026-09-11T14:05:00Z", "active", "order", bpg, once, ["P121.noteB"], "Priya Raman")
    service("P121.plan", "P121", "2026-09-11T14:10:00Z", "plan", "active", "RPR titer", "Priya Raman",
            "Repeat RPR titer due by 2027-03-11.", ["P121.noteB"])
    note("P121.msg", "P121", "2026-09-12T19:00:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for a work note for the 9/11 visit. Sent through the portal.")

    # P122 Victor Almeida
    note("P122.reg", "P122", "2026-09-01T09:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Contact details recorded.")
    rpr("P122.rpr0", "P122", "2026-09-01T09:20:00Z", "2026-09-01T15:00:00Z", "1:128")
    note("P122.vitals", "P122", "2026-09-01T09:40:00Z", "nurse", "Vital signs", "Pat Quinn",
         "BP 134/86, HR 80, temperature 36.9 C, RR 16, SpO2 98% on room air.")
    note("P122.noteA", "P122", "2026-09-01T10:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Syphilis with one week of blurred vision in the left eye; RPR 1:128. Possible ocular syphilis. Plan: aqueous crystalline penicillin G 4 million units IV every 4 hours for 14 days by home infusion; ophthalmology referral; lumbar puncture scheduled.", True)
    med("P122.rxA", "P122", "2026-09-01T10:05:00Z", "active", "order", "Aqueous crystalline penicillin G",
        "Aqueous crystalline penicillin G 4 million units IV every 4 hours for 14 days.", ["P122.noteA"], "Luis Ortega")
    result("P122.csf", "P122", "2026-09-05T11:00:00Z", "2026-09-06T09:00:00Z", "CSF VDRL, cell count and protein",
           "VDRL nonreactive; WBC 2/uL; protein 35 mg/dL")
    note("P122.noteB", "P122", "2026-09-08T11:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Ophthalmology examination on 9/4 was normal; blurred vision attributed to uncorrected refractive error. Lumbar puncture on 9/5 showed normal CSF. Assessment: early latent syphilis without neurologic or ocular involvement. Plan: benzathine penicillin G 2.4 million units IM once.", True)
    med("P122.rxB", "P122", "2026-09-08T11:05:00Z", "active", "order", bpg, once, ["P122.noteB"], "Jordan Blake")
    note("P122.msg", "P122", "2026-09-10T16:20:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked to update his emergency contact. Contact updated.")

    # P123 Hannah Cho
    note("P123.reg", "P123", "2026-09-02T08:30:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Insurance card scanned.")
    rpr("P123.rpr0", "P123", "2026-09-01T16:00:00Z", "2026-09-02T07:50:00Z", "1:8")
    note("P123.noteA", "P123", "2026-09-02T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Latent syphilis of unknown duration: RPR 1:8 with reactive treponemal antibody, no signs or symptoms. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today.", True)
    med("P123.rxA", "P123", "2026-09-02T09:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P123.noteA"], "Hana Sato")
    dose("P123.d1", "P123", "2026-09-02T09:25:00Z", bpg, bpg_dose, "P123.rxA", "Dana Kim")
    note("P123.noteB", "P123", "2026-09-05T15:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Outside records received: nonreactive syphilis testing in July 2026, so infection was acquired within the past year. Assessment: early latent syphilis. Plan: benzathine penicillin G 2.4 million units IM once.", True)
    med("P123.rxB", "P123", "2026-09-05T15:05:00Z", "active", "order", bpg, once, ["P123.noteB"], "Casey Nguyen")
    note("P123.note3", "P123", "2026-09-09T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Follow-up visit. Two partners identified and referred for testing. Reviewed the 9/5 assessment with Dr. Nguyen: because the patient had already started the weekly series, we agreed to complete it. The single-dose benzathine penicillin G order from 9/5 is cancelled; continue the weekly series, next dose 9/16. Counseled on the Jarisch-Herxheimer reaction. Contraception counseling provided.", True)
    dose("P123.d2", "P123", "2026-09-09T09:20:00Z", bpg, bpg_dose, "P123.rxA", "Dana Kim")
    dose("P123.d3", "P123", "2026-09-16T09:25:00Z", bpg, bpg_dose, "P123.rxA", "Pat Quinn")
    service("P123.plan", "P123", "2026-09-16T09:40:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer due by 2027-03-16.", ["P123.note3"])

    # P124 Leila Moradi
    note("P124.reg", "P124", "2026-06-09T10:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance information recorded.")
    rpr("P124.rpr0", "P124", "2026-06-09T10:20:00Z", "2026-06-09T17:10:00Z", "1:32")
    note("P124.vitals", "P124", "2026-06-10T08:50:00Z", "nurse", "Vital signs", "Sam Ortiz",
         "BP 112/72, HR 76, temperature 36.7 C, RR 14, SpO2 99% on room air.")
    service("P124.hivorder", "P124", "2026-06-10T08:55:00Z", "order", "completed", "HIV-1/2 antigen/antibody", "Casey Nguyen")
    note("P124.noteA", "P124", "2026-06-10T09:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Secondary syphilis: rash on trunk and palms, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. HIV test sent. Repeat RPR titer 3 months after treatment.", True)
    med("P124.rx", "P124", "2026-06-10T09:05:00Z", "completed", "order", bpg, once, ["P124.noteA"], "Casey Nguyen")
    service("P124.planA", "P124", "2026-06-10T09:10:00Z", "plan", "active", "RPR titer", "Casey Nguyen",
            "Repeat RPR titer 3 months after treatment.", ["P124.noteA"])
    dose("P124.dose", "P124", "2026-06-10T09:25:00Z", bpg, bpg_dose, "P124.rx", "Sam Ortiz")
    result("P124.hiv", "P124", "2026-06-10T09:00:00Z", "2026-06-13T10:00:00Z", "HIV-1/2 antigen/antibody",
           "Nonreactive", "P124.hivorder")
    note("P124.noteB", "P124", "2026-07-01T14:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Telehealth visit to review results. HIV test nonreactive. Rash resolved. Repeat RPR titer 6 months after treatment.", True)
    service("P124.planB", "P124", "2026-07-01T14:10:00Z", "plan", "active", "RPR titer", "Alex Moreno",
            "Repeat RPR titer 6 months after treatment.", ["P124.noteB"])
    note("P124.msg", "P124", "2026-08-12T12:40:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for clinic hours during the holiday weekend. Hours sent.")

    # P125 Omar Farouk: penicillin series held and never resumed; doxycycline alone is current.
    note("P125.reg", "P125", "2026-09-01T15:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Insurance card scanned.")
    rpr("P125.rpr0", "P125", "2026-09-01T15:30:00Z", "2026-09-02T07:40:00Z", "1:16")
    note("P125.note", "P125", "2026-09-02T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Latent syphilis of unknown duration: RPR 1:16 with reactive treponemal antibody, no signs or symptoms. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 6 months after completing treatment.", True)
    med("P125.rxA", "P125", "2026-09-02T09:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P125.note"], "Hana Sato")
    service("P125.plan", "P125", "2026-09-02T09:10:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer 6 months after completing treatment.", ["P125.note"])
    dose("P125.d1", "P125", "2026-09-02T09:30:00Z", bpg, bpg_dose, "P125.rxA", "Dana Kim")
    note("P125.addendum", "P125", "2026-09-02T08:00:00Z", "front-desk", "Addendum", "Chris Lowe",
         "Addendum to registration: preferred phone number corrected.")
    note("P125.nurse", "P125", "2026-09-03T16:10:00Z", "nurse", "Nursing note", "Dana Kim",
         "Patient called: hives and throat tightness the evening after the injection, treated at urgent care and resolved. Treating clinician notified.")
    note("P125.note2", "P125", "2026-09-04T10:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Possible immediate reaction to penicillin. Hold the benzathine penicillin G series pending allergy evaluation. Start doxycycline 100 mg orally twice daily for 28 days.", True)
    med("P125.rxB", "P125", "2026-09-04T10:05:00Z", "active", "order", "Doxycycline",
        "Doxycycline 100 mg orally twice daily for 28 days.", ["P125.note2"], "Jordan Blake")
    note("P125.lab", "P125", "2026-09-10T08:30:00Z", "laboratory", "Laboratory communication", "Clinic laboratory",
         "Specimen for chlamydia and gonorrhea NAAT received; results to follow.")
    note("P125.allergy", "P125", "2026-09-15T13:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Allergy clinic: penicillin skin testing positive. Penicillin allergy confirmed; avoid penicillins.", True)

    # P126 Beatriz Santos: a follow-up revision was retracted, so the original plan governs.
    note("P126.reg", "P126", "2026-03-01T10:30:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Contact details recorded.")
    rpr("P126.rpr0", "P126", "2026-03-01T11:00:00Z", "2026-03-01T17:20:00Z", "1:32")
    note("P126.noteA", "P126", "2026-03-02T09:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Primary syphilis: genital ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-09-02.", True)
    med("P126.rx", "P126", "2026-03-02T09:05:00Z", "completed", "order", bpg, once, ["P126.noteA"], "Luis Ortega")
    service("P126.planA", "P126", "2026-03-02T09:10:00Z", "plan", "active", "RPR titer", "Luis Ortega",
            "Repeat RPR titer due by 2026-09-02.", ["P126.noteA"])
    dose("P126.dose", "P126", "2026-03-02T09:25:00Z", bpg, bpg_dose, "P126.rx", "Sam Ortiz")
    note("P126.noteB", "P126", "2026-06-15T14:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Follow-up visit. Revised follow-up plan: repeat RPR titer due by 2026-12-15; this replaces the September plan.", True)
    service("P126.planB", "P126", "2026-06-15T14:10:00Z", "plan", "active", "RPR titer", "Alex Moreno",
            "Repeat RPR titer due by 2026-12-15.", ["P126.noteB"])
    note("P126.retract", "P126", "2026-06-16T09:00:00Z", "treating-clinician", "Addendum", "Alex Moreno",
         "The 6/15 progress note and its follow-up plan were entered on this chart in error; they belong to a different patient and are retracted.", True)
    note("P126.msg", "P126", "2026-07-22T18:30:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked to update her pharmacy. Pharmacy updated.")

    # P127 Callum Reid: one dose charted twice and one charted but not given; completion is Mar 30.
    note("P127.reg", "P127", "2026-03-08T14:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Insurance information recorded.")
    rpr("P127.rpr0", "P127", "2026-03-08T14:20:00Z", "2026-03-08T20:00:00Z", "1:8")
    note("P127.note", "P127", "2026-03-09T09:30:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Latent syphilis of unknown duration: RPR 1:8 with reactive treponemal antibody, no signs or symptoms. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 6 months after completing treatment.", True)
    med("P127.rx", "P127", "2026-03-09T09:35:00Z", "completed", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P127.note"], "Casey Nguyen")
    service("P127.plan", "P127", "2026-03-09T09:40:00Z", "plan", "active", "RPR titer", "Casey Nguyen",
            "Repeat RPR titer 6 months after completing treatment.", ["P127.note"])
    dose("P127.d1", "P127", "2026-03-09T10:00:00Z", bpg, bpg_dose, "P127.rx", "Riley Chen")
    dose("P127.d2", "P127", "2026-03-16T10:05:00Z", bpg, bpg_dose, "P127.rx", "Pat Quinn")
    dose("P127.d2dup", "P127", "2026-03-16T12:10:00Z", bpg, bpg_dose, "P127.rx", "Pat Quinn")
    note("P127.dupnote", "P127", "2026-03-16T13:00:00Z", "nurse", "Nursing note", "Pat Quinn",
         "The 3/16 injection was charted twice; one injection was given.")
    dose("P127.d3err", "P127", "2026-03-23T10:00:00Z", bpg, bpg_dose, "P127.rx", "Riley Chen")
    note("P127.errnote", "P127", "2026-03-23T11:00:00Z", "nurse", "Nursing note", "Riley Chen",
         "The 3/23 injection was charted in error; the patient left before it was given. Rescheduled.")
    dose("P127.d3", "P127", "2026-03-30T09:55:00Z", bpg, bpg_dose, "P127.rx", "Riley Chen")
    note("P127.recall", "P127", "2026-03-30T10:30:00Z", "scheduling-staff", "Recall note", "Jamie Ellis",
         "Added to RPR recall list. Recall reminder set for 2026-09-20.")
    note("P127.cnote", "P127", "2026-06-18T15:00:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "Seen for a right wrist sprain after a fall. No bony tenderness. Splint and ibuprofen as needed.", True)
    note("P127.msg", "P127", "2026-05-04T17:15:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for a copy of his immunization record. Sent through the portal.")

    # P128 Yuki Watanabe: first specimen rejected; the recollected result (later corrected) completes the plan.
    note("P128.reg", "P128", "2026-02-19T09:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance card scanned.")
    rpr("P128.rpr0", "P128", "2026-02-19T09:20:00Z", "2026-02-19T16:00:00Z", "1:32")
    note("P128.note", "P128", "2026-02-20T10:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "Primary syphilis: penile ulcer, RPR 1:32. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer due by 2026-08-20.", True)
    med("P128.rx", "P128", "2026-02-20T10:05:00Z", "completed", "order", bpg, once, ["P128.note"], "Jordan Blake")
    service("P128.plan", "P128", "2026-02-20T10:10:00Z", "plan", "active", "RPR titer", "Jordan Blake",
            "Repeat RPR titer due by 2026-08-20.", ["P128.note"])
    dose("P128.dose", "P128", "2026-02-20T10:25:00Z", bpg, bpg_dose, "P128.rx", "Dana Kim")
    service("P128.order1", "P128", "2026-08-18T09:00:00Z", "order", "completed", "RPR titer", "Jordan Blake")
    result("P128.rpr1", "P128", "2026-08-18T09:20:00Z", "2026-08-19T08:30:00Z", "RPR titer", "Reactive, 1:4", "P128.order1")
    note("P128.reject", "P128", "2026-08-22T11:00:00Z", "laboratory", "Laboratory communication", "Clinic laboratory",
         "The specimen collected 8/18 was hemolyzed. The RPR result reported 8/19 is invalid and has been rejected. Recollection requested.")
    service("P128.order2", "P128", "2026-09-02T09:00:00Z", "order", "completed", "RPR titer", "Jordan Blake")
    result("P128.rpr2", "P128", "2026-09-02T09:15:00Z", "2026-09-03T08:10:00Z", "RPR titer", "Reactive, 1:4", "P128.order2")
    note("P128.corr", "P128", "2026-09-04T10:30:00Z", "laboratory", "Laboratory communication", "Clinic laboratory",
         "Corrected report for the RPR collected 9/2: titer is 1:2. The original report contained a transcription error.")

    # P129 Amara Nwosu: doxycycline held then resumed, while a penicillin series also started.
    note("P129.reg", "P129", "2026-08-31T13:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Preferred pharmacy recorded.")
    rpr("P129.rpr0", "P129", "2026-08-31T13:20:00Z", "2026-08-31T19:40:00Z", "1:8")
    note("P129.noteA", "P129", "2026-09-01T10:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Late latent syphilis: RPR 1:8, reactive treponemal antibody, nonreactive testing in 2023. Reports a penicillin allergy (hives in 2015). Doxycycline 100 mg orally twice daily for 28 days.", True)
    med("P129.rxA", "P129", "2026-09-01T10:05:00Z", "active", "order", "Doxycycline",
        "Doxycycline 100 mg orally twice daily for 28 days.", ["P129.noteA"], "Luis Ortega")
    note("P129.nurse", "P129", "2026-09-05T09:30:00Z", "nurse", "Nursing note", "Riley Chen",
         "Patient reports nausea and stomach upset on doxycycline. Treating clinician notified.")
    note("P129.hold", "P129", "2026-09-05T13:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Hold doxycycline for 3 days. Resume on 9/9 if the nausea has resolved, taken with food.", True)
    note("P129.tel", "P129", "2026-09-09T12:20:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient reports the nausea has resolved and restarted doxycycline today with food as instructed.")
    note("P129.noteB", "P129", "2026-09-12T10:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Allergy clinic: oral amoxicillin challenge tolerated; penicillin allergy label removed. Plan: benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today.", True)
    med("P129.rxB", "P129", "2026-09-12T10:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P129.noteB"], "Priya Raman")
    dose("P129.d1", "P129", "2026-09-12T10:30:00Z", bpg, bpg_dose, "P129.rxB", "Pat Quinn")
    dose("P129.d2", "P129", "2026-09-19T10:25:00Z", bpg, bpg_dose, "P129.rxB", "Pat Quinn")

    # P130 Pieter de Vries: the note that resolved the existing item was retracted; reopen it.
    note("P130.reg", "P130", "2026-08-02T12:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance information recorded.")
    rpr("P130.rpr0", "P130", "2026-08-02T12:30:00Z", "2026-08-02T18:00:00Z", "1:16")
    note("P130.noteA", "P130", "2026-08-03T10:00:00Z", "treating-clinician", "Progress note", "Casey Nguyen",
         "Latent syphilis of unknown duration: RPR 1:16. Patient takes warfarin. Benzathine penicillin G 2.4 million units IM weekly for three doses; defer the first injection until the INR has been reviewed.", True)
    med("P130.rx", "P130", "2026-08-03T10:05:00Z", "active", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P130.noteA"], "Casey Nguyen")
    note("P130.nurse", "P130", "2026-08-08T11:00:00Z", "nurse", "Nursing note", "Sam Ortiz",
         "INR 3.4 today. First IM injection not given; treating clinician asked to review before scheduling.")
    note("P130.clear", "P130", "2026-08-20T09:30:00Z", "treating-clinician", "Progress note", "Alex Moreno",
         "INR 2.4 today, within range. IM benzathine penicillin G injections may proceed.", True)
    note("P130.retract", "P130", "2026-09-05T15:00:00Z", "treating-clinician", "Addendum", "Alex Moreno",
         "The 8/20 progress note was written for a different patient and is retracted from this chart.", True)
    note("P130.msg", "P130", "2026-09-09T20:05:00Z", "telephone-staff", "Patient portal message", "Taylor Brooks",
         "Patient asked for directions to the clinic. Directions sent.")

    # P131 Rosa Delgado: a nurse's protocol revision cannot change the clinician's 12-month plan.
    note("P131.reg", "P131", "2026-02-09T11:00:00Z", "front-desk", "Registration", "Avery Hughes",
         "New patient registration completed. Contact details confirmed.")
    rpr("P131.rpr0", "P131", "2026-02-09T11:20:00Z", "2026-02-09T18:30:00Z", "1:64")
    note("P131.noteA", "P131", "2026-02-10T09:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Secondary syphilis: rash on palms and soles, RPR 1:64. Benzathine penicillin G 2.4 million units IM once, given today. Repeat RPR titer 6 months after treatment.", True)
    med("P131.rx", "P131", "2026-02-10T09:05:00Z", "completed", "order", bpg, once, ["P131.noteA"], "Priya Raman")
    service("P131.planA", "P131", "2026-02-10T09:10:00Z", "plan", "active", "RPR titer", "Priya Raman",
            "Repeat RPR titer 6 months after treatment.", ["P131.noteA"])
    dose("P131.dose", "P131", "2026-02-10T09:25:00Z", bpg, bpg_dose, "P131.rx", "Sam Ortiz")
    note("P131.noteB", "P131", "2026-05-12T15:00:00Z", "treating-clinician", "Progress note", "Priya Raman",
         "Patient will be abroad from June to December. Revised follow-up plan: repeat RPR titer 12 months after treatment, on return. This replaces the 6-month plan.", True)
    service("P131.planB", "P131", "2026-05-12T15:10:00Z", "plan", "active", "RPR titer", "Priya Raman",
            "Repeat RPR titer 12 months after treatment.", ["P131.noteB"])
    note("P131.nurse", "P131", "2026-07-20T10:00:00Z", "nurse", "Nursing note", "Dana Kim",
         "Per clinic protocol, follow-up revised to a repeat RPR titer due by 2026-08-15; this replaces the 12-month plan.")
    service("P131.nplan", "P131", "2026-07-20T10:05:00Z", "plan", "active", "RPR titer", "Dana Kim",
            "Repeat RPR titer due by 2026-08-15.", ["P131.nurse"], role="nurse")
    note("P131.cnote", "P131", "2026-03-18T14:00:00Z", "treating-clinician", "Progress note", "Luis Ortega",
         "Travel consultation. Hepatitis A and typhoid vaccines given. Traveler's diarrhea precautions reviewed.", True)
    note("P131.tel", "P131", "2026-05-20T11:00:00Z", "telephone-staff", "Telephone encounter", "Taylor Brooks",
         "Patient called to confirm travel dates and asked for a copy of her vaccination record. Sent.")
    note("P131.lab", "P131", "2026-02-11T08:00:00Z", "laboratory", "Laboratory communication", "Clinic laboratory",
         "HIV-1/2 antigen/antibody specimen received; results to follow.")

    # P132 Tomasz Nowak: an erroneous series restart was corrected; treatment completed on Mar 15.
    note("P132.reg", "P132", "2026-02-22T13:00:00Z", "front-desk", "Registration", "Chris Lowe",
         "New patient registration completed. Insurance card scanned.")
    rpr("P132.rpr0", "P132", "2026-02-22T13:20:00Z", "2026-02-22T19:10:00Z", "1:16")
    note("P132.note", "P132", "2026-02-23T09:00:00Z", "treating-clinician", "Progress note", "Hana Sato",
         "Latent syphilis of unknown duration: RPR 1:16 with reactive treponemal antibody, no signs or symptoms. Benzathine penicillin G 2.4 million units IM weekly for three doses, first dose today. Repeat RPR titer 6 months after completing treatment.", True)
    med("P132.rx", "P132", "2026-02-23T09:05:00Z", "completed", "order", bpg,
        "Benzathine penicillin G 2.4 million units IM weekly for three doses.", ["P132.note"], "Hana Sato")
    service("P132.plan", "P132", "2026-02-23T09:10:00Z", "plan", "active", "RPR titer", "Hana Sato",
            "Repeat RPR titer 6 months after completing treatment.", ["P132.note"])
    dose("P132.d1", "P132", "2026-02-23T09:30:00Z", bpg, bpg_dose, "P132.rx", "Dana Kim")
    dose("P132.d2", "P132", "2026-03-02T09:25:00Z", bpg, bpg_dose, "P132.rx", "Dana Kim")
    note("P132.restart", "P132", "2026-03-15T09:00:00Z", "treating-clinician", "Progress note", "Jordan Blake",
         "More than 14 days since the second dose; restarting the three-dose series today.", True)
    dose("P132.d3", "P132", "2026-03-15T09:20:00Z", bpg, bpg_dose, "P132.rx", "Riley Chen")
    dose("P132.r2", "P132", "2026-03-22T09:30:00Z", bpg, bpg_dose, "P132.rx", "Riley Chen")
    dose("P132.r3", "P132", "2026-03-29T09:15:00Z", bpg, bpg_dose, "P132.rx", "Dana Kim")
    note("P132.corr", "P132", "2026-04-02T16:00:00Z", "treating-clinician", "Addendum", "Jordan Blake",
         "Correction to the 3/15 note: the interval since the second dose was 13 days, within the 14-day window, so the original series was completed on 3/15 and no restart was needed. The 3/22 and 3/29 injections were extra doses.", True)

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
        review("Q2119", "P113", "E113", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P113.plan")],
               "Repeat RPR titer was due by 2026-08-15; no result is on file.", by_id, created="2026-08-20T08:00:00Z"),
        review("Q2104", "P130", "E130", "treatment_review", "UNRESOLVED_TREATMENT_CONCERN", "resolved",
               [rid("P130.nurse"), rid("P130.clear")],
               "INR reviewed on 8/20 and IM injections cleared to proceed.", by_id, created="2026-08-10T08:00:00Z"),
        review("Q2131", "P128", "E128", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P128.plan")],
               "Repeat RPR titer was due by 2026-08-20; the 8/18 specimen was rejected and no valid result is on file.",
               by_id, created="2026-08-25T08:00:00Z"),
        review("Q2146", "P102", "E102", "treatment_review", "UNRESOLVED_TREATMENT_CONCERN", "open", [rid("D01"), rid("D02")],
               "Penicillin order requires prescriber review in light of the reported reaction; medication has not been administered.",
               by_id, created="2026-08-31T09:30:00Z"),
        review("Q2187", "P116", "E116", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P116.plan")],
               "Repeat RPR titer was due by 2026-09-02; no result is on file.", by_id, created="2026-09-04T08:30:00Z"),
        review("Q2203", "P105", "E105", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P105.plan"), rid("P105.dose")],
               "Repeat RPR titer was due 6 months after the March 1 treatment; no result is on file.", by_id,
               created="2026-09-05T09:00:00Z"),
        review("Q2209", "P119", "E119", "treatment_review", "UNRESOLVED_TREATMENT_CONCERN", "open",
               [rid("P119.tel"), rid("P119.rx")],
               "Pharmacy is holding doxycycline because of an isotretinoin interaction; prescriber review requested.",
               by_id, created="2026-09-08T08:00:00Z"),
        review("Q2217", "P108", "E108", "follow_up", "OVERDUE_FOLLOW_UP", "open", [rid("P108.plan6")],
               "Repeat RPR titer was due by 2026-09-01; no result is on file.", by_id, created="2026-09-12T08:00:00Z"),
    ]
    sources = [r for r in sources if r["resourceType"] == "Organization"
               or r.get("subject", r.get("patient", {"reference": "Patient/" + r["id"]}))["reference"][8:] in COHORT]
    queue = [q for q in queue if q["for"]["reference"][8:] in COHORT]
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
