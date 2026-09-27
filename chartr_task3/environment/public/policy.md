# Cohort audit conventions

## Candidates and dispositions

A candidate is one episode and one issue type. Each candidate has one disposition:

| Disposition | Meaning |
|---|---|
| `confirmed` | The records establish that the issue exists. |
| `not_an_issue` | The records establish that the issue does not exist. |
| `cannot_determine` | Whether the issue exists depends on a fact the records do not establish. |

Save one item for each `confirmed` or `cannot_determine` candidate, and one item for each candidate named in a review request. A candidate without an item is `not_an_issue`.

A `cannot_determine` item names the missing-evidence code of the fact it depends on:

| Code | The fact is |
|---|---|
| `RESULT_PENDING` | the result of a test collected by the evaluation time that has no final result |
| `OUTSIDE_RECORD_NOT_RECEIVED` | care at another facility that the chart indicates, from any source, and whose record the clinic has not received |
| `UNRESOLVED_SOURCE_CONFLICT` | a fact on which records conflict, where the conflict is not settled by the authority conventions below |

## Issue types

| Issue | Exists when |
|---|---|
| `INADEQUATE_TREATMENT` | An episode diagnosed at least 30 days before the evaluation time has not received treatment adequate for its infection, given the patient's pregnancy status. |
| `FOLLOW_UP_OVERDUE` | A post-treatment nontreponemal test recommended at a stated number of months after treatment was not collected within its window, and the window closed before the evaluation time. |
| `MISFILED_RESULT` | A laboratory result filed in the episode's chart belongs to a different patient. |
| `PREGNANCY_TREATMENT_INADEQUATE` | The patient was pregnant at any time from the episode's diagnosis to the evaluation time and has not received treatment adequate for syphilis in pregnancy; once delivery has occurred, that treatment must have begun at least 30 days before it. |

## Local conventions

- Follow-up months count from the date of the first treatment dose; an untreated episode has no follow-up test due. A test's window runs from 30 days before to 30 days after its due date, and a test is collected within the window when a specimen from the patient was collected then and not rejected by the laboratory.
- A specimen and its laboratory result belong to the patient identified by medical record number and date of birth on the specimen's collection record and on the laboratory's accessioning entry. When these identify different patients, the specimen's patient is unresolved.
- A later signed correction by a record's author governs that record.
- Care at another facility is established only by a record from that facility received by the clinic.
- Other conflicts between records are unresolved.
