# Clinic interface

`clinic patients` returns all patients, their `target_episodes`, `checkpoints` and episode records. `clinic records PATIENT_ID` returns the whole patient chart with `complete: true`, in original event-time order, including amendments. No pagination. `clinic determinations [--patient PATIENT_ID]` returns saved rows.

The following are templates. Substitute discovered IDs and conclusions; placeholders do not identify real records:

```sh
clinic determine --json '{"patient":"PATIENT_ID","episode":"EPISODE_ID","checkpoint":"first","status":"STATUS","plan":"PLAN_ID","course":"COURSE_ID","branch":"routine","doses":["ADMINISTRATION_ID"],"completion_date":"YYYY-MM-DD","due_date":"YYYY-MM-DD","paused_days":0,"result":null,"explanation":"EXPLANATION_TEXT"}'
clinic redetermine DETERMINATION_ID --json '{"status":"completed","result":"OBSERVATION_ID"}'
```

Create requires exactly those thirteen fields. Update accepts any nonempty subset except immutable patient, episode and checkpoint. Omitted fields are retained. Writes return the saved FHIR Task. IDs are service-assigned. Duplicate rows are operationally permitted but do not satisfy the assignment. Inspect saved rows after a lost response; writes are never automatically retried. Sources are immutable; there are no admin, reset, export, delete, history, or grading routes.

- `checkpoint`: `first` or `second`.
- `status`: `no_requirement`, `unclear`, `not_due`, `overdue`, `blocked`, `completed`; see policy.
- `plan`, `course`, `result`: a record ID or null. Typed references such as `Observation/RECORD_ID` are accepted. These respectively reference ServiceRequest, MedicationRequest, Observation.
- `branch`: `routine`, `accelerated`, or null.
- `doses`: up to 40 MedicationAdministration IDs. List order is not graded; duplicates do not satisfy the required sequence.
- Dates: ISO YYYY-MM-DD or null. `paused_days`: nonnegative integer or null.
- `explanation`: nonempty text up to 4,000 characters. R4 permits space, tab, CR, LF, but not arbitrary Unicode whitespace.

References must be in the patient's chart, including its other episodes. The backend checks operational validity, not clinical conclusions. Each request is limited to 16 KiB. Exit 0 means success, 2 invalid arguments/operational validation, and 3 transport/service failure.

# Limited FHIR R4 mapping

All resources use the pinned R4 4.0.1 structural schema. This is not a full FHIR REST server, profile, terminology validator, or conformance claim. Local extensions use `https://chartr.example/fhir/StructureDefinition/`.

- Patient and EpisodeOfCare identify subjects and episode scope.
- MedicationRequest identifies a course; its `episode` extension fixes its EpisodeOfCare.
- MedicationAdministration: `request` is course, `effectiveDateTime` date, `status` original administration status.
- Basic with code `Review-clock pause` (a structured review hold; holds can also be ordered in clinician notes): `pause-period` has start/end, `pause-status` is active/revoked, repeated `course` extensions supply associations. These are local concepts, not new standard FHIR statuses.
- ServiceRequest with intent plan: `supportingInfo` gives course associations; `note` is the clinician's free-text schedule (designated baseline and comparison RPRs, month pairs, separation). `replaces` is a local reference extension.
- Specimen: `collection.collectedDateTime` is collection time, `status` availability, repeated `course` extensions indicate which courses the specimen can support.
- Observation: `specimen` identifies the physical collection; `valueInteger` is reciprocal titer (e.g. 16 means 1:16), `code` the test, `status` and `issued` govern report availability. Multiple reports may share one specimen.
- DocumentReference: free-text clinical note in `description`, with identical text in the base64 attachment; `date` is documentation time, `docStatus` signed/final status, `authenticator` the signer, and `author-role` authority.
- Task: `for` patient, `focus` episode, `checkpoint` extension first/second, `businessStatus` determination status. Typed inputs hold plan/course/dose/result references. Extensions hold completion-date, due-date, schedule-branch and paused-days. Standard Task.status remains `completed` because a determination was recorded, even when its businessStatus is blocked or overdue.

The `event-time` extension and Observation effectiveDateTime describe original entries; the policy defines how authoritative amendments affect their interpretation.
