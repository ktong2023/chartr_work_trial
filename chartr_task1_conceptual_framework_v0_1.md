**ChartR Task 1: Treatment-review queue reconciliation**

Conceptual implementation framework • Draft 0.1 • Prepared September 25, 2026

This is a comparison draft for Kyle's first task. It contains no implementation code, executable commands, or configuration syntax. It incorporates the three fictional patients already developed in our discussion. Technical choices described as proposals remain open to revision before implementation.

**This complete document is for the task designer. It contains expected answers and must never be placed in the evaluated agent's environment. Only the explicitly agent-visible portions should be extracted into its instructions and documentation.**

**1. The task and its boundary**

The agent reviews a fixed cohort of patients already under syphilis care and reconciles a treatment-review queue. It must identify an explicitly documented unresolved treatment concern, recognize when a historical concern has been resolved, and identify incompatible active treatment instructions that require clarification.

The evaluation measures evidence retrieval, interpretation of dates and record relationships, recognition of resolution, and correct changes to persistent workflow state. It does not ask the agent to independently diagnose syphilis, select a treatment regimen, or administer care.

| Item | Version 0.1 specification |
| --- | --- |
| Task identifier | syphilis-treatment-review-v0.1 |
| Task count | One task containing three patient cases; the cases are not three separate Harbor tasks |
| Cohort | Samantha Lee / P101; Darrow Jones / P102; Morgan Patel / P103 |
| Treatment episodes | E101, E102, E103 respectively |
| Simulated evaluation time | September 24, 2026, 12:00 UTC |
| Rules in scope | Unresolved treatment concern; conflicting active treatment plans |
| Queue destination | clinical_review |
| Source records | Read-only clinical records and order information |
| Permitted persistent changes | Create or update treatment-review items |
| Completion | Correct saved queue state; a final chat response alone does not complete the task |
| Scoring | Deterministic binary pass, with separate diagnostic checks |
| Initial purpose | Prove the environment, reference solution, and grader work together |

The three cases may be easy for Opus. Their first purpose is integration validation. Difficulty calibration comes after the basic system works. Care-access flags, follow-up-gap flags, HAPI FHIR, MCP, live notifications, and a human-facing application are deferred.

**2. Proposed agent-visible instruction**

You are assisting a clinic with treatment-review queue reconciliation. Review every patient in the supplied cohort as of September 24, 2026, at 12:00 UTC. Apply the supplied treatment-review policy to the available records.

Create a review item when a current treatment concern remains unresolved or active treatment instructions conflict without documented reconciliation. Update an existing item for the same issue rather than creating a duplicate. Resolve an existing item when the available documentation explicitly establishes that its concern has been addressed.

For each item you create or update, record the patient, treatment episode, applicable reason, destination, status, supporting record references, and a short factual explanation. Use the documented clinic tools. Clinical records, treatment orders, and allergy information are not writable. Treatment decisions remain with the clinical team.

Use the fixed evaluation time rather than the computer's clock. Distinguish a historical concern from a current concern. Do not assume that an ordered assessment has been completed or that a more recent note automatically replaces an earlier active instruction. Where the policy requires clarification, represent that uncertainty instead of inventing a resolution.

Before finishing, inspect the persisted queue to check that all in-scope episodes are accounted for, existing items have been reconciled, and no duplicate or unsupported items were added. A brief completion message may summarize the work, but grading uses the saved state.

**3. Agent-visible workflow policy**

| Rule | Trigger | Evidence that resolves or prevents the flag | Result |
| --- | --- | --- | --- |
| TR1: unresolved treatment concern | A clinical record explicitly identifies a concern about the current treatment plan that requires review, and available evidence does not establish resolution | An authorized clinician explicitly addresses the same concern and records its disposition; or clear documentation establishes that the concern applies only to a superseded plan | Reason UNRESOLVED_TREATMENT_CONCERN; destination clinical_review; status open |
| TR2: conflicting active plans | Two currently applicable instructions for the same episode disagree on the same treatment decision, with no documented cancellation, supersession, or authoritative reconciliation | An explicit correction, replacement, cancellation, or authorized clarification resolves the disagreement | Reason CONFLICTING_ACTIVE_PLANS; destination clinical_review; status needs_clarification |

Policy details:

- An assessment request, laboratory order, referral, or message to a clinician is not proof of completion or resolution.
- Compare instructions addressing the same episode, decision, and period. Different stages of an explicitly sequential plan are not automatically contradictions.
- Use event/effective dates to establish applicability. Use authorship time to understand documentation order. Upload time alone does not establish clinical precedence.
- An explicit replacement relationship takes precedence over simple recency. A later independent plan does not automatically cancel another active order.
- Signed treating-clinician documentation can establish a treatment decision or resolution. Nursing and administrative notes can document concerns and operational facts but do not independently override a signed plan.
- In Morgan's case, both authors have equal authority. Neither has a special precedence rule.
- A medication list changing without documentation addressing the original concern is not sufficient resolution for this task.
- Missing information warrants a flag only when it leaves a documented in-scope treatment concern unresolved. Do not flag every absent chart field.
- A draft plan that is explicitly awaiting review is not automatically a conflicting active plan.
- If TR1 and TR2 describe the same underlying conflict, create one item and use CONFLICTING_ACTIVE_PLANS as its primary reason. Do not duplicate the issue.
- Resolving a review item closes that documented concern only. It does not mean an allergy disappeared, treatment was successful, or all future follow-up is complete.
- Evidence references should identify the concern or conflicting instructions and the current order/status or resolution records needed to support the chosen disposition. Additional relevant references are permitted; indiscriminately attaching the entire chart is not the intended evidence behavior.

For version 0.1, each episode contains at most one treatment-review issue. Maintain one item for that issue, including after it becomes resolved. This is a simplifying fixture assumption, not a general rule that a patient can have only one clinical concern.

| Status | Meaning in this task |
| --- | --- |
| open | An explicit concern remains unresolved and needs clinical review |
| needs_clarification | Incompatible current instructions require clinician reconciliation |
| resolved | Documentation establishes that the item's specific concern was addressed |

Reopening an existing resolved item would be permitted if new in-scope evidence warranted it. The initial fixture does not require that transition. Resolved items are retained; deletion is unavailable.

**4. The fictional starting records**

All dates below are in 2026 and all times are UTC. Unless separately stated, the event time and documentation time are the displayed time. Every record is available by the evaluation time. No outside records, future events, or additional unlisted patient history should be assumed.

These are authored simulation records. They illustrate documentation reconciliation. The original doxycycline-injection and five-/ten-week examples were replaced with clinically grounded descriptions. General treatment background is provided by the linked CDC sources at the end; those sources do not define the benchmark's custom queue policy.

**Patient P101: Samantha Lee, episode E101**

| ID | Date/time | Type | Agent-visible content |
| --- | --- | --- | --- |
| S01 | Sept. 23, 09:00 | Signed clinician assessment | Primary syphilis documented. Patient reports a penicillin allergy. Oral doxycycline is being considered as an alternative. Pregnancy status has not been established; treatment selection requires clinician review after assessment. |
| S02 | Sept. 23, 09:15 | Proposed treatment plan | Proposed oral doxycycline course. Status: draft, not released. Final selection pending the assessment requested in S01. |
| S03 | Sept. 23, 10:00 | Nursing note | Patient reports a late menstrual period. Pregnancy testing requested by clinician; specimen not collected during this visit. Clinician informed. |
| S04 | Sept. 24, 08:00 | Laboratory order status | Pregnancy test ordered; specimen not collected; no result available. |
| S05 | Sept. 24, 09:00 | Telephone note | Patient plans to attend today. Message sent to treating clinician for review. No treatment decision documented in this encounter. |

Initial queue: no item for E101.

The public records establish an outstanding concern, not a pregnancy diagnosis. The model does not need to infer a universal pregnancy-testing rule or independently determine medication safety.

**Patient P102: Darrow Jones, episode E102**

| ID | Date/time | Type | Agent-visible content |
| --- | --- | --- | --- |
| D01 | Aug. 31, 09:00 | Initial treatment order | Primary syphilis. Benzathine penicillin G 2.4 million units IM once. Current order status at the evaluation time: canceled on Sept. 1 at 08:00 by D03; replacement order D04. |
| D02 | Aug. 31, 09:20 | Nursing note | Patient reports prior immediate hives and breathing difficulty after penicillin. Medication not administered. Prescriber contacted to reconcile the plan. |
| D03 | Sept. 1, 08:00 | Signed treating-clinician addendum | Reviewed the reported penicillin reaction. Cancel D01. For this adult patient, for whom pregnancy is not applicable and with no documented neurologic, ocular, or auditory symptoms, use oral doxycycline 100 mg twice daily for 14 days. Follow-up arranged. This replaces the Aug. 31 plan and addresses the medication concern in D02. |
| D04 | Sept. 1, 08:10 | Replacement medication order | Doxycycline 100 mg orally twice daily for 14 days, linked to D03 and replacing D01. Order history preserves the replacement relationship. |
| D05 | Sept. 15, 16:00 | Signed clinician follow-up | Patient reports completing the prescribed course. No new treatment concern identified. Planned serologic follow-up remains in place. |

D01's original authorship time and later cancellation time are separate facts. The fixture must represent both rather than presenting the old order as currently active.

Initial queue item:

| Field | Initial value |
| --- | --- |
| Item ID | Q102 |
| Patient / episode | P102 / E102 |
| Category / reason | treatment_review / UNRESOLVED_TREATMENT_CONCERN |
| Destination / status | clinical_review / open |
| Created | Aug. 31, 09:30 |
| Evidence references | D01 and D02 |
| Explanation | Penicillin order requires prescriber review in light of the reported reaction; medication has not been administered. |

The review item is deliberately stale. The allergy remains part of the clinical record even after the plan-related concern is resolved.

**Patient P103: Morgan Patel, episode E103**

| ID | Date/time | Type | Agent-visible content |
| --- | --- | --- | --- |
| M01 | Sept. 23, 09:00 | Signed clinician assessment A | Latent syphilis; duration cannot be established from the available history. Plan for benzathine penicillin G 2.4 million units IM weekly for three doses. |
| M02 | Sept. 23, 09:10 | Treatment order A | Three weekly doses. Status: active. Linked to M01. No cancellation or replacement relationship. |
| M03 | Sept. 23, 15:00 | Signed clinician assessment B | Assessment: early latent syphilis. Plan for benzathine penicillin G 2.4 million units IM once. No statement addressing M01 or replacing its plan. |
| M04 | Sept. 23, 15:10 | Treatment order B | Single dose. Status: active. Linked to M03. No cancellation or replacement relationship. |
| M05 | Sept. 24, 09:00 | Scheduling record | First treatment appointment booked for Sept. 24 at 14:00. No medication administration recorded for this episode. |

Initial queue: no item for E103.

The agent reports the disagreement. It is not asked to independently stage the disease or select between the regimens. M03 being later is insufficient to supersede M01 under the supplied policy.

**5. State and data contract**

The starting dataset, often called a fixture, is a fixed collection of records and queue items loaded for every trial. It is separate from the private expected-answer data.

| Entity | Required information | Mutable by the agent? |
| --- | --- | --- |
| Patient | Stable patient ID and display name | No |
| Treatment episode | Stable episode ID and patient link | No |
| Clinical record | Stable record ID, patient/episode links, record type, author role, documentation time, applicable event/effective time, content, and explicit source/replacement relationships where present | No |
| Review item | Item ID, patient/episode links, category, reason code, destination, status, evidence IDs, explanation, creation/update metadata | Selected workflow fields only |
| Trial context | Task/fixture version, fixed evaluation time, permitted cohort, public policy | No |
| Audit event | Operation, arguments, result/error, sequence, and before/after queue changes | No |

Each record's text and structured metadata must agree. When they are intentionally inconsistent, that inconsistency must be part of an explicitly designed case; accidental mismatches are fixture defects.

New queue IDs are service-generated. The grader does not require specific new IDs. Existing Q102 must retain its identity, patient, episode, original creation metadata, and reason. Updates may change status, evidence, and explanation. Audit history preserves earlier values.

For the prototype, the destination and category have one allowed value each. New and existing items use the same visible reason/status vocabulary. Correctness is about which patient/episode is flagged and why, rather than guessing field names.

Source record times and the simulated evaluation time are fixed. Newly written workflow records can use the fixed simulated time plus a monotonic event sequence. Operational logs may also record real elapsed time, clearly distinguished from clinical time.

**6. Agent tool contract**

The agent uses a clinic command-line client from its shell. The client calls the clinic service, which owns the state. These are conceptual operations, not finalized command syntax.

| Operation | Input | Output and behavior |
| --- | --- | --- |
| List patients | No patient-specific argument | All in-scope patient IDs, names, episode IDs; deterministic ordering |
| Get records | Patient ID | All available records for that patient, with IDs, dates, types, links, and full content; explicit indication that the response is complete |
| List review items | Optional patient ID | Current queue items including resolved ones; an empty result is different from a retrieval error |
| Create review item | Patient/episode, reason, destination, status, evidence IDs, explanation | Persisted item with generated ID and all saved fields |
| Update review item | Existing item ID and allowed changed fields | Persisted updated item; omitted fields retained; identity cannot be reassigned |

Version 0.1 has no pagination or search ranking. Reads are complete and use a fixed order. Later retrieval difficulty should be introduced as an explicit version change.

Service behavior:

- Validate argument types, existing patient/episode links, allowed fields and enums, and evidence IDs belonging to the named patient and episode.
- Return useful operational errors for malformed requests or unavailable records. Do not include expected answers or grading feedback.
- Do not automatically infer concerns, select reasons, resolve items, or reject a structurally valid concern merely because it is semantically wrong.
- Proposed duplicate behavior: structurally valid duplicate creations are allowed and receive distinct IDs; the public policy prohibits duplicates and the grader detects them. This preserves duplicate avoidance as agent work. Request-replay protection may be added separately if transport retries require it.
- Writes are atomic and immediately visible to later reads. No dynamic patient events or background clinical changes occur during a trial.
- If a write response is lost, the client must not silently repeat a possibly committed mutation. The agent can inspect the queue before retrying. Unexpected transport failures are logged for attribution.
- There is no agent operation for reset, grading, reference execution, raw database access, export to the grader, or deleting records.

The public tool documentation must include exact argument names, enum values, return shapes, and examples before implementation is considered ready for a model pilot. Those syntax decisions are intentionally not supplied as code in this framework.

**7. Proposed Harbor runtime and access boundaries**

A model produces decisions. An agent driver turns its responses into tool actions. Harbor starts and supervises the trial, invokes verification, and collects results. The clinic service implements this task's state and operations. The grader determines correctness. These are separate responsibilities.

| Component | Contents and role | Access boundary |
| --- | --- | --- |
| Harbor controller | Trial settings, startup/reset, agent driver selection, stopping, trusted evidence collection, result storage | Private orchestration; not an agent tool |
| Agent container | Shell, clinic client, public instruction/policy/tool documentation, scratch work area | No database files, private tests, reference solution, private expected answers, host mounts, or Docker socket |
| Clinic service container | Fixed source records, fresh queue database, operational validation, audit log | Agent reaches only the documented service API; cannot modify service code or files |
| Separate verifier environment | Grader, private rubric/expected answers, trusted final snapshot and audit evidence | Started for verification after agent actions stop; its outputs are never fed back to the evaluated agent |
| Result storage | Trajectory, configuration, snapshots, logs, score and diagnostics | Accessible to Kyle/reviewers; unavailable as a cross-trial memory source to the agent |

The proposed backend is Python plus SQLite. It is a mock clinical system, not a conformant FHIR server. Harbor supports Docker Compose sidecar services, with main reserved for the agent container. A separate verifier is an explicit option; it is not the default. [H1-H3]

The agent driver remains a compatibility decision. Prefer an existing compatible Harbor driver if a small smoke test works. A custom Anthropic adapter is a fallback when required by the supplied API access. Do not build two drivers. Harbor, the driver, and the exact model/configuration must all be recorded in the run metadata.

The private reference solution is made available only during a dedicated oracle run. It must never be copied into the agent image or clinical service image, even in an earlier image layer. Likewise, do not copy this entire document, the repository history, or a directory containing private tests into the agent's filesystem.

**8. Trial lifecycle, reset, and evidence capture**

1. Select the task, fixture, policy, grader, driver, model, and run-budget versions.
2. Create a fresh per-trial clinic database and load the fixed fixture. Reset source records, Q102, ID counters, logical clock, and audit history. Use no shared mutable database across trials.
3. Verify service readiness and the expected initial-state digest before allowing the agent to act. A digest is a reproducible fingerprint of the canonical starting data, excluding trial-specific log timestamps.
4. Start a fresh agent workspace and conversation, supply the public instruction, and make public documentation available. Do not carry over previous trial messages, files, or grades.
5. Run the agent. Persist its observable messages and tool results and the service's independent audit trail. Capture API request metadata and usage when supplied; do not assume private model reasoning is available.
6. On completion or a declared limit, stop the agent and all its child processes, revoke further writes, and settle any in-flight operation deterministically before collecting state.
7. Collect the authoritative queue/source snapshot and audit log directly from the service through a controller-only mechanism. The agent must not author, overwrite, or choose the snapshot used for grading.
8. Give that evidence to the separate verifier and run the private grader. A separate verifier does not automatically inherit the agent or service state; evidence transfer must be wired explicitly. [H2]
9. Save the score, diagnostics, validity classification, termination reason, and artifacts; then discard the per-trial runtime state.

Before coding the full task, prove that the chosen Harbor version/provider can collect sidecar evidence and deliver it to the separate verifier. If it cannot do so directly, implement one small trusted controller-side collection step. Do not silently replace authoritative evidence with an agent-written file or expose an export/admin endpoint to the agent.

Proposed pilot limits: 10 minutes of agent wall time and 60 model turns, if the selected driver supports a turn limit. Record any token/output limits and reasoning settings the model requires. These are provisional operational budgets, not difficulty targets. Inspect healthy reference/pilot runs before finalizing them. Reserve a separate startup timeout and verifier timeout; failures there are not model time-budget exhaustion.

Pin dependencies, container images, and driver versions for the final evaluation. Install dependencies when building images rather than depending on package downloads during grading.

**9. Private expected results and evidence acceptance**

| Patient | Expected action | Reason | Final status | Identity requirement |
| --- | --- | --- | --- | --- |
| P101 / E101 | Create one treatment-review item | UNRESOLVED_TREATMENT_CONCERN | open | New generated ID accepted |
| P102 / E102 | Resolve the existing item | Preserve UNRESOLVED_TREATMENT_CONCERN | resolved | Retain Q102; no replacement item |
| P103 / E103 | Create one treatment-review item | CONFLICTING_ACTIVE_PLANS | needs_clarification | New generated ID accepted |

All three items retain category treatment_review and destination clinical_review. The final queue contains three items total: two requiring action and one resolved. This count is a private consequence of this fixture, not an instruction telling the agent how many patients to flag.

Evidence should be evaluated by role rather than by exact prose or one arbitrary full citation list. Proposed accepted groups for the initial fixture:

| Finding | Minimum supporting evidence | Additional relevant evidence |
| --- | --- | --- |
| Samantha's concern remains open | S02 for the pending plan; at least one of S01/S03 for the explicit concern; S04 for the outstanding assessment | The other concern record and S05 |
| Darrow's concern is resolved | D03 for explicit reconciliation, plus D04 or D01's current cancellation metadata confirming order reconciliation | D02 and D05 |
| Morgan's active plans conflict | M02 and M04, whose returned content includes incompatible instructions, current active statuses, and links to the signed assessments | M01, M03, M05 |

These evidence alternatives slightly relax the earlier shorthand that listed all four Morgan records and one fixed Darrow pair. That change avoids failing equivalent, sufficient evidence. If implementation separates an order's content from its linked assessment, revisit these alternatives before freezing; the grader must follow what each tool actually exposes.

Evidence lists are treated as sets. Ordering is irrelevant. All cited records must belong to the correct patient and episode, and every additional reference must come from the relevant supporting set. This blocks simply attaching the whole dataset. A reviewer should challenge the allowed sets with valid alternatives before finalization.

**10. Scoring and what it establishes**

For each case, report separate checks for disposition, correct patient/episode, item identity/count, reason/status/destination, and sufficient evidence. Overall pass is 1 only when all required case checks and global invariants pass; otherwise it is 0. Diagnostic results are for the experimenter and are never visible during the model run. Harbor's verifier reports its reward in the required result format. [H1]

Global invariants:

- No source clinical record, order, allergy documentation, patient identity, or episode link has changed.
- Q102 is preserved and resolved, not deleted or replaced.
- No extra, duplicate, or unsupported review item exists, including unnecessary resolved items created during the run.
- Snapshot identity matches the trial and fixture; grading is based on authoritative state.

Exact explanation wording, generated new item IDs, field ordering, read order, and a particular valid action sequence are not graded. The explanation must be nonempty and is inspected during human QA. Its medical/factual prose is not fully verified by the deterministic score in version 0.1; report that limitation. Structured findings and evidence references are the graded answer. Do not claim that this grader validates arbitrary clinical narratives.

The primary score measures final queue correctness. Intermediate corrected queue mistakes remain in the audit log for analysis but do not automatically fail a run. Source-record integrity is a process constraint as well as a final-state constraint. Attempted operations rejected by the documented interface may be recoverable; an ordinary validation error is not automatically a model failure.

A broken verifier, absent trusted snapshot, incorrect fixture, or unrecoverable service/API fault is not equivalent to a valid score of zero. Record evaluation validity separately from task success.

**11. Deterministic reference solution and grader QA**

The reference is an ordinary program with no LLM calls. It may use the known case IDs for this fixed fixture, but must read and write through the same permitted clinic interface and limits of authority as the model. It must not edit SQLite directly, install hidden state, or supply fabricated evidence to the grader.

Reference walkthrough:

1. Enumerate the cohort and read each patient's records and current review items.
2. Create Samantha's open review item with sufficient evidence for the outstanding concern.
3. Update Q102 to resolved, preserving its identity and adding the resolution evidence and explanation.
4. Create Morgan's clarification item with evidence from both active plans.
5. Read the queue again and confirm the expected persisted records.

This is one valid path, not a required model trajectory. The reference establishes solvability, while independent expected-state assertions establish acceptance.

| QA case | Required result |
| --- | --- |
| Reference on repeated fresh resets | Full pass; same clinically meaningful final state |
| No-op agent | Fail because the starting queue is incorrect/incomplete |
| Different order of correct writes | Pass |
| Equivalent accepted evidence set or paraphrased explanation | Pass |
| Samantha incorrectly resolved or omitted | Fail on Samantha |
| Darrow left open or replaced by a new item | Fail on Darrow |
| Morgan resolved by choosing a regimen without reconciliation | Fail on Morgan |
| Correct items plus an extra flag or duplicate | Fail |
| Structurally valid concern attached to the wrong episode/patient | Fail when semantic expectations do not match; invalid patient/episode combinations are rejected by the service |
| Regrading the same trusted snapshot | Identical deterministic result |
| Service or verifier unavailable | Evaluation error, not a fabricated task-failure score |
| Private file or admin route probe from the agent boundary | No access to private rubric, grader, solution, reset, or trusted evidence collector |

These are meaningful checks of the evaluation's trustworthiness. Broad production testing and exhaustive FHIR validation are outside the current milestone.

**12. Failure attribution and saved results**

| Classification | Example | Reporting treatment |
| --- | --- | --- |
| Valid success | Correct queue and evidence | Count as pass |
| Valid model failure | Stops without resolving Q102 despite working access | Count as fail; describe observed mistake |
| Valid agent budget exhaustion | Uses the allowed budget without completing the work | Grade resulting state; record budget exhaustion separately |
| Infrastructure/API failure | Service crash, unhandled provider outage, missing valid credentials | Mark invalid; retain attempt and apply a declared retry rule |
| Grader defect | Equivalent valid evidence wrongly rejected | Fix/version the grader; regrade complete saved evidence where sound, otherwise rerun |
| Fixture or policy defect | Required source precedence was never disclosed | Revise/version the task and rerun affected trials |

A timeout while the service is unhealthy must not be presented as a clean reasoning failure. An invalid tool argument followed by a proper service error is normal recoverable feedback. Describe observed behavior rather than claiming access to the model's internal cause.

Each attempt saves: task and fixture versions; starting digest; public prompt/policy/tool versions; Harbor and driver versions; exact model identifier and settings; declared budgets; observable trajectory; service action log; authoritative final snapshot; termination reason; score and per-check diagnostics; validity classification; and available usage/runtime metadata. Exclude API credentials from logs and artifacts.

Pilots are separate from the final evaluation. After calibration, freeze the complete task and run ten fresh valid trials for its final version. Report all attempted runs and exclusions, not only successful or preferred runs. The eventual assignment seeks an observed 2-7 passes out of ten; that is not a reason to change rules during a final batch or discard valid outcomes.

**13. How the conceptual documents map to a Harbor task**

These filenames identify responsibilities for later implementation; no files in the table are executable deliverables in this draft.

| Future material | Contents | Agent-visible? |
| --- | --- | --- |
| instruction.md | Section 2, scoped task objective and completion requirements | Yes |
| policy.md | Section 3 and relevant public evidence/status requirements | Yes |
| tools.md | Final exact interface contract derived from Section 6 | Yes |
| Fixture data | Section 4 records and initial queue, without case labels or intended-answer commentary | Via clinic tools only |
| design.md | Runtime, schemas, reset, trust boundaries, collection decisions | No |
| grading.md and expected-answer data | Sections 9-11, accepted alternatives and QA cases | No |
| task.toml | Harbor metadata, timeouts, environment, verifier and artifact settings | No need to expose |
| environment definition | Agent image, clinic service, healthchecks, data seeding | Only public runtime contents become accessible |
| solution/solve.sh and supporting implementation | Deterministic reference using the public clinic interface | Oracle run only |
| tests/test.sh and supporting implementation | Private deterministic verifier | Verification only |
| README.md | Reproduction steps, versions, reference/model runs, evidence locations, limitations | Designer/reviewer documentation |

Use explicit inclusion of public files when constructing the agent image. Do not rely on an innocently named folder being secret if it exists in an agent-accessible filesystem. Source fixtures belong to the service; private expected results and QA descriptions do not.

**14. Implementation milestones and comparison decisions**

| Milestone | Completion evidence |
| --- | --- |
| A. Reconcile this conceptual draft with Kyle's | One agreed instruction, policy, fixture, evidence contract, and private expected state |
| B. Harbor smoke test | A tiny unrelated tutorial task runs through environment startup and oracle verification |
| C. Minimal clinical service | One patient can be read and one queue item persisted through the intended client |
| D. Complete fixture and reference | All three cases load consistently; the reference makes the correct changes |
| E. Separate verification and trusted capture | Oracle passes and no-op fails using a service-sourced snapshot; reset and privacy boundaries checked |
| F. First Opus pilot | One complete real trajectory, trusted final state, and attributable result |
| G. Calibration | Add complexity or categories only in response to observed behavior, then freeze for final trials |

The next coding milestone ends at a working small evaluation. It does not require a second clinical task or the full care-access/follow-up feature set. Preserve shared patient, episode, record, queue, and tool concepts so Task 2 can reuse the service with its own fixed starting state and grader.

Proposed choices to compare explicitly:

| Choice | Recommendation for this draft | Why it matters |
| --- | --- | --- |
| Model interface | Harbor-compatible shell agent using the clinic client; reuse a compatible driver | Avoid maintaining a second orchestration loop |
| Storage | Python service plus SQLite, isolated from agent shell | Small resettable state with an enforceable tool boundary |
| Verification | Separate verifier with controller-collected service evidence | Prevents private grading access and fabricated final snapshots |
| Duplicate handling | Let semantically duplicate creates occur and fail grading; keep normal request validation | Makes duplicate avoidance observable agent work |
| Score | Binary all-required-checks pass plus diagnostic details | Defines the assignment's pass rate without hiding failures in averages |
| Narrative grading | Human QA of explanations; deterministic grading of structured findings | Keeps the first verifier reproducible while stating its limitation |
| Evidence | Accept sufficient alternatives, not one exact citation sequence | Avoids enforcing the reference solution's incidental choices |
| Trial limits | Provisional generous pilot limits, finalized after healthy runs | Prevents using resource starvation as artificial difficulty |

Still to verify before the first model pilot: the exact ChartR-provided model identifier and allowed settings; driver/API compatibility; supported sidecar evidence transfer in the pinned Harbor version; actual CLI schemas; dependency/image versions; and the final retry/timeout settings. No real evaluation result is claimed in this document.

**15. Source notes**

Assignment requirements are grounded in the supplied ChartR work-trial PDF, page 2, and the interview notes provided in this conversation. The queue policy, fixture cases, acceptance conditions, limits, and architecture recommendations are design proposals, not statements from ChartR or CDC.

- [H1] [Harbor task overview](https://docs.harborframework.com/core-concepts/tasks/overview): task packaging and verifier reward output.
- [H2] [Harbor separate verifier](https://docs.harborframework.com/core-concepts/tasks/separate-verifier): verification isolation and explicit artifact transfer.
- [H3] [Harbor multi-container tasks](https://docs.harborframework.com/core-concepts/tasks/multi-container): agent service and supporting services.
- [H4] [Harbor create-a-task tutorial](https://docs.harborframework.com/tutorials/create-a-task): reference/oracle and initial task workflow.
- [C1] [CDC primary and secondary syphilis guidance](https://www.cdc.gov/std/treatment-guidelines/p-and-s-syphilis.htm): background for the oral doxycycline alternative in appropriately selected nonpregnant patients with penicillin allergy.
- [C2] [CDC latent syphilis guidance](https://www.cdc.gov/std/treatment-guidelines/latent-syphilis.htm): background for the one-dose versus three-weekly-dose plans in the deliberately unresolved documentation conflict.
- [C3] [CDC syphilis during pregnancy guidance](https://www.cdc.gov/std/treatment-guidelines/syphilis-pregnancy.htm): background for making pregnancy-related treatment selection a clinician-review concern.

Clinical examples are synthetic and intentionally limited to documentation reconciliation. A passing score does not establish prescribing competence, clinical safety, or performance across real EHR systems.
