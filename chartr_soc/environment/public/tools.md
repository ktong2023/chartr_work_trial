# Clinic CLI

```sh
clinic patients
clinic records PATIENT_ID
clinic documents
clinic determinations [--patient PATIENT_ID]
clinic determine --json '{"patient":"…","episode":"…","checkpoint":"first","status":"…","plan":null,"course":null,"branch":null,"doses":[],"completion_date":null,"due_date":null,"paused_days":null,"result":null,"explanation":"…"}'
clinic redetermine DETERMINATION_ID --json '{…subset…}'
```

`clinic patients` lists patients and their target episodes; `clinic records` returns a patient's complete chart; `clinic documents` returns clinic-wide documents. Nothing is paginated.

Create requires exactly these thirteen fields; update accepts any subset except patient, episode and checkpoint. One row per episode and checkpoint; duplicates fail. Writes are never retried; list saved rows after a lost response.

- `checkpoint`: `first` or `second`, in the order the follow-up plan gives them.
- `status`: see policy.
- `plan` / `course` / `result`: the governing ServiceRequest, the treatment MedicationRequest, the completing RPR Observation; IDs or null.
- `branch`: `routine` (the plan's default schedule) or `accelerated` (its alternative schedule) when the plan has a conditional schedule; otherwise null.
- `doses`: MedicationAdministration IDs that count toward completing treatment.
- `completion_date`, `due_date`: YYYY-MM-DD or null. `paused_days`: held days added to the due date (0 if none).
- For `unclear` and `no_requirement`, plan, course, branch, dates, paused_days and result are null and doses is empty. When treatment is not complete, completion_date and due_date are null and paused_days is 0.
- `explanation`: nonempty text, at most 4,000 characters.

Requests are limited to 16 KiB. Exit codes: 0 ok, 2 invalid request, 3 transport or service failure.

Records are FHIR R4 4.0.1 JSON; this is not a full FHIR server. Local extensions under `https://chartr.example/fhir/StructureDefinition/`: `episode`, `event-time`, `author-role`, `clinic-memo`, `checkpoint`, `completion-date`, `due-date`, `schedule-branch`, `paused-days`.
