# Clinic CLI

```sh
clinic patients [--page N]
clinic search TYPE [--patient ID] [--since YYYY-MM-DD] [--until YYYY-MM-DD] [--code CODE] [--page N | --all] [--out FILE]
clinic documents [--out FILE]
clinic ecg list [--patient ID]
clinic ecg fetch ECG_ID --dir DIR
clinic items [--patient ID]            clinic item add --json '{…}'       clinic item update ITEM_ID --json '{…}'
clinic interpretations [--patient ID]  clinic interpretation add --json '{…}'  clinic interpretation update INTERPRETATION_ID --json '{…}'
```

`clinic search` returns FHIR R4 resources of one type (for example Encounter, Condition, Observation, MedicationRequest, MedicationAdministration, MedicationDispense, Procedure, Specimen, DocumentReference, Medication), 1,000 per page in time order. `--all` fetches every page. With `--out`, resources are written to FILE as NDJSON and a summary is printed. `clinic documents` returns clinic-wide documents. Note text is in `content[0].attachment.data` (base64). `clinic ecg fetch` writes a 12-lead, 10-second WFDB record (`.hea`, `.dat`, 500 Hz) to DIR. Records follow the MIMIC-IV FHIR profiles; local extensions: `author-role`, `clinic-document`.

Items: `patient`, `category`, `reason` (see policy; immutable after creation) and `explanation`, plus the fields for the reason:

| Reason | Fields |
|---|---|
| UNTREATED_AF | `af_evidence` (records establishing AF), `risk_score`, `risk_factors` (CHA2DS2-VASc components: CHF, HYPERTENSION, AGE_65_74, AGE_75_PLUS, DIABETES, STROKE_TIA, VASCULAR, FEMALE) |
| ANTICOAGULANT_WITH_CONTRAINDICATION | `anticoagulant` (current order), `contraindication` (record) |
| DUAL_ANTICOAGULATION, RHYTHM_DOCUMENTATION_CONFLICT | `records` (the conflicting records) |
| PROLONGED_QTC_ON_WATCH_LIST_DRUG | `ecg`, `qtc_ms`, `heart_rate`, `qt_drug` (current order), `potassium`, `magnesium` (most recent results) |
| ECG_AFTER_WATCH_LIST_START, INR_AFTER_WARFARIN_DOSE_CHANGE | `status`, `trigger` (the order or note that created the requirement), `requirement` (clinic document), `due_date`, `completion_record` |

ECG interpretations (one per patient, for that patient's most recent ECG):

| Field | Value |
|---|---|
| `ecg` | ECG ID (immutable) |
| `rhythm` | `SINUS`, `AF`, `ATRIAL_FLUTTER`, `PACED` or `OTHER` |
| `ventricular_rate` | bpm |
| `pr_ms`, `qrs_ms`, `qtc_ms` | ms; `qtc_ms` is Bazett-corrected; `pr_ms` is null when there is no measurable PR interval |
| `axis` | frontal QRS axis: `NORMAL` (-30 to +90), `LEFT` (-30 to -90), `RIGHT` (+90 to +180), `EXTREME` (-90 to -180) |
| `conduction` | list from `RBBB`, `LBBB`, `FIRST_DEGREE_AV_BLOCK` (empty if none) |
| `prior_ecg` | the patient's previous ECG, or null if there is none |
| `changes` | versus `prior_ecg`, list from `NEW_AF`, `RESOLVED_AF`, `NEW_ATRIAL_FLUTTER`, `RESOLVED_ATRIAL_FLUTTER`, `NEW_PACED_RHYTHM`, `RESOLVED_PACED_RHYTHM`, `NEW_BUNDLE_BRANCH_BLOCK`, `RESOLVED_BUNDLE_BRANCH_BLOCK`, `QTC_INCREASE_60`, `QTC_DECREASE_60` (QTc changed by 60 ms or more); empty if none |
| `explanation` | free text |

Record fields take IDs (bare or typed, e.g. `Observation/ID`); ECG IDs come from `clinic ecg list`. Unused fields are null or empty lists. One item per issue and one interpretation per patient; duplicates fail. Writes are never retried; list saved records after a lost response. Requests are limited to 16 KiB. Exit codes: 0 ok, 2 invalid request, 3 transport or service failure.
