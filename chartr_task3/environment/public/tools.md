# Clinic interface

- `clinic patients` returns every cohort patient with their episodes (`complete: true`).
- `clinic records PATIENT_ID` returns every record whose subject is that patient, in event-time order.
- `clinic export [--dir DIR]` writes every record in the clinic, including records with no patient subject, to `DIR/<ResourceType>.ndjson` (one JSON resource per line) with `DIR/manifest.json` (`complete`, `evaluation_time`, per-type counts). The default directory is `./export`.
- `clinic requests` returns every open review request.
- `clinic items [--patient PATIENT_ID]` returns saved items.

The following are templates; substitute discovered IDs and your decisions:

```sh
clinic item --json '{"patient":"PATIENT_ID","episode":"EPISODE_ID","issue":"ISSUE","disposition":"DISPOSITION","missing_evidence":null,"evidence":["RECORD_ID"],"explanation":"EXPLANATION_TEXT"}'
clinic update-item ITEM_ID --json '{"disposition":"DISPOSITION","missing_evidence":"CODE"}'
```

`item` requires exactly those seven fields; one item is allowed per episode and issue. `update-item` accepts any nonempty subset of `disposition`, `missing_evidence`, `evidence` and `explanation`; omitted fields are retained.

- `issue`: `INADEQUATE_TREATMENT`, `FOLLOW_UP_OVERDUE`, `MISFILED_RESULT`, `PREGNANCY_TREATMENT_INADEQUATE`.
- `disposition`: `confirmed`, `not_an_issue`, `cannot_determine`.
- `missing_evidence`: `RESULT_PENDING`, `OUTSIDE_RECORD_NOT_RECEIVED` or `UNRESOLVED_SOURCE_CONFLICT` for `cannot_determine`, otherwise null.
- `evidence`: 1 to 30 record IDs from any chart or clinic-level record, bare (`RECORD_ID`) or typed (`Observation/RECORD_ID`).
- `explanation`: nonempty text up to 4,000 characters; R4 permits space, tab, CR and LF but not other Unicode whitespace.

Writes return the saved FHIR Task, with a service-assigned ID, and are never retried automatically; inspect saved items after a lost response. The backend checks operational validity, not clinical conclusions. Requests are limited to 16 KiB. Sources are immutable; there are no admin, reset, delete or grading routes. Exit 0 means success, 2 invalid arguments or operational validation, 3 transport or service failure.

# Limited FHIR R4 records

All resources use the pinned R4 4.0.1 structural schema; this is not a full FHIR server or conformance claim. Local extensions use `https://chartr.example/fhir/StructureDefinition/`. Every clinical record has an `event-time` extension.

- Patient: `identifier` holds the medical record number; `birthDate`, `name`, `gender`. EpisodeOfCare: `period.start` is the diagnosis date.
- Condition: an entry on the diagnosis list; `recordedDate`, `recorder`.
- AllergyIntolerance: `code` substance, `reaction`.
- Observation: laboratory result. `effectiveDateTime` is collection time, `issued` result time, `valueString` the result, `status` `final`, `registered` (no result yet) or `cancelled` (not performed); `note` holds laboratory comments; `specimen` references the specimen's collection record; `identifier` holds the accession number.
- Specimen: collection record. `accessionIdentifier`, `collection` (time, collector); `label-name`, `label-mrn` and `label-dob` extensions hold the identifiers printed on the specimen label.
- Basic with code text `Laboratory accessioning`: the laboratory's accessioning entry, with no patient subject; `author` entered it. Extensions `accession`, `patient-name`, `patient-mrn`, `patient-dob`, `received`.
- MedicationAdministration: a dose given in clinic; `status` `completed` or `not-done`, `effectiveDateTime`, `dosage.text`, `performer`, `note`.
- MedicationDispense: medication dispensed to the patient; `quantity`, `daysSupply`, `whenHandedOver`, `dosageInstruction`, `note`.
- DocumentReference: a note, letter or scanned outside record. `description` is the full text (identical to the base64 attachment), `type` the document type, `date` documentation time, `author`, `author-role` extension.
- Task: a review request (`status: requested`; `code` the issue, `for` the patient, `focus` the episode, `description` the request) or a saved item (`status: completed`; `businessStatus` the disposition, `missing-evidence` extension, `input` the evidence).
