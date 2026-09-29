# ChartR difficulty audit — September 27, 2026

## Scope and conclusion

Reviewed the current `chartr_task` 0.5.1, `chartr_proto` 0.1.0, adapter 0.3.1, their public surfaces, generators, graders, reference solutions, tests, and saved pilot artifacts. The user-linked Downloads document is the earlier Task 2 design brief; the matching recent handoff is `TASK1_DIFFICULTY_HANDOFF.md` in this repository.

The implementation has materially improved isolation, operational reliability, and diagnostic value. I found no direct private-answer exposure through the reviewed public docs, image build inputs, or ordinary service interface. Fresh isolation probes passed. This is bounded evidence, not proof that every possible shortcut or vulnerability is absent.

The continued high pass rate is credible. The strongest remaining shortcuts concern recognizable case construction and histories whose final notes already supply the derived conclusion. The prototype tests rule transfer, but much of that transfer is near-example matching plus familiar conventions. Correct structured outputs are stronger evidence than a correct flag alone, but do not prove which reasoning process produced them.

No task, adapter, generator, grader, or existing run artifact was edited. This report and fresh no-cost audit runs are the only intended additions. No model API calls were made; no credentials were read.

## Findings, ranked by practical priority

### 1. Prototype malformed input can invalidate an entire evaluation — confirmed defect

At `chartr_proto/environment/service/store.py:164–168`, `patient` is used in set membership before its type is checked. Submitting an otherwise well-formed determination with `patient: []` or `patient: {}` returns HTTP 500, increments the service fault counter, and makes the snapshot invalid for grading. Both were reproduced against fresh temporary databases. The main task returns 400 with zero faults for the same patient-type mistakes.

This is not an answer disclosure. It is an avoidable attribution problem: a malformed model argument can become an excluded infrastructure failure rather than recoverable tool feedback. An agent could also deliberately trigger it, although no such behavior was observed in the inspected pilots.

Recommendation: validate scalar types before lookups; add these cases to the existing service-contract tests. Preserve fail-closed grading for genuine service faults.

### 2. Recognizable examples still reduce the intended reconstruction/induction burden

- `qa/proto_cases.py:65` and `:112`: historical H215 and current P302 have identical regimen, dose history, plan dates, explicit replacement, and retraction. P302 adds an unrelated result and patient self-report, which are separately demonstrated distractors. I checked the underlying core facts for equality. Transferring this historical determination requires much less hypothesis search than the handoff's overall description suggests.
- A main-task 0.5.1 trajectory explicitly recognized a “deliberate contrast” between cases. It initially drew the wrong inference from that contrast and later corrected itself using the written rule. This establishes that the model uses construction clues; it does not establish that the clues caused the successful final answer.
- `qa/build_fixture.py:804`: P132's final correction explicitly says the original series completed on March 15 and identifies the later injections as extra. That is legitimate clinical documentation, but the agent can obtain the anchor directly instead of reconstructing the whole dose history.

Recommendation: retain legitimate evidence in existing cases. For new cases, vary decisive dates and combinations independently, avoid conspicuous twins in the same evaluated cohort, and use corrections to constituent facts when the intended skill is recomputation. Do not remove necessary clinical conclusions merely to make reading harder.

### 3. Oracle success is not independent semantic validation

`qa/build_proto.py:201–219` generates the public historical determinations, private expected answers, and oracle submissions from `qa/proto_rules.py`. `chartr_proto/solution/reference.py:14–21` reads the interface and then submits the generated answers; it does not derive them from the returned records.

This is a useful deterministic integration oracle and is not an isolation failure. However, a bug shared by the rule engine and renderer can survive reference/grader agreement. The current tests primarily establish internal consistency, transport behavior, and rejection of predefined wrong answers.

Recommendation: before substantially harder histories, independently reconstruct answers from exported public records and documented rules (or demonstrations). Compare that result with the private generator's facts. Keep the existing oracle for workflow verification.

### 4. Induction fairness is stronger within the modeled space than the tests prove, but remains bounded

The build checks each of 16 misconception toggles individually. I additionally enumerated all **65,536 combinations** of these toggles: exactly one combination matches every historical determination, and it yields the expected current answers. This is a positive result.

It does not prove uniqueness across all plausible clinic standards. The candidate hypothesis space is private and preselected. The prototype therefore should not be described as a general proof that no other defensible rule fits the examples. Stronger induction needs a stated bounded family of possible standards, or an explicit protocol, plus agreement of all surviving hypotheses on evaluated outputs.

A smaller wording issue also remains: public tools describe `unclear` as a due date that cannot be determined, while H208/P306 use `not_due` with a null due date when treatment is incomplete. The examples teach that exception and all five pilots recovered it, but the status definition could explicitly accommodate it without revealing a particular answer.

### 5. Anti-shortcut tests cover individual features, not combinations or generalization

`qa/test_clinic.py:289` checks opaque record IDs, lack of a simple numeric cutoff, and that citable types/roles/labels/authors also occur elsewhere. Those are valuable checks. They do not rule out predictive combinations, distinctive prose templates, ordering effects, or near-duplicate cases. The prototype does not have equivalent broad shortcut checks.

Recommendation: supplement static checks with label-independent ID/name changes, reordered patient/record presentation, equally complex negative controls, and held-out combinations of mechanisms. Test simple baselines such as latest-note-only, structured-status-only, and nearest precedent. A shortcut baseline passing the entire task is stronger evidence of a problem than a suggestive correlation.

### 6. The handoff's difficulty arithmetic overstates what the evidence supports

The reported **50 paid attempts, 45 operationally valid, 38 passing** matches saved artifacts after excluding four mocked runs. The seven valid failures split as reported by diagnostics: four P117 follow-up failures on the ambiguous 0.3.0 fixture, two later P117 treatment-review misses, and one output-cap termination. Operational validity and task-defect attribution are different labels; preserve the raw outcomes rather than treating the defect regrade as fresh model successes.

The “one reasoning error in 700 decisions” estimate pools repeated cases, easy no-item decisions, categories, and dependent fields across changing versions. It is not an independent, identically distributed per-decision error probability. Accordingly, `(1-e)^n`, “500 decisions,” and the pooled 15/15 probability are illustrations under assumptions, not reliable workload or pass-rate forecasts.

Five trials per candidate give miss rates only in increments of 20%; zero misses in five does not establish a rate below 5%. Selecting whichever cases failed in a tiny probe also selects sampling noise. Use mechanism families and held-out variants before committing to a large calibration batch.

### 7. Keep adapter configurations separate in pilot reporting

All five main-task 0.5.1 pilots used adapter **0.3.0**, with explicit adaptive-thinking and caching parameters recorded in their start events. All five prototype pilots used the current **0.3.1**, whose hash matches the working file and whose requests omit those parameters.

Main-task manifests match current task files except the private README; prototype manifests match completely. The earlier main-task results remain useful historical calibration evidence, but “behavior unchanged” in `PROGRESS.md:36` is not established by these artifacts. Do not present the pooled results as identical harness settings. No fresh paid comparison was performed in this audit.

## What has improved

- Public examples use placeholders; no private engine/answer symbols were found in the reviewed prompt, public docs, or CLI source.
- Opaque record IDs and broader routine-record types address real earlier shortcuts.
- Explicit correction/authority rules make failures easier to attribute to application rather than missing conventions.
- The task now includes retentions, resolutions, reopening, conflicting plans, and event corrections instead of only simple create operations.
- The prototype's plan, due date, completion record, and status expose errors that status-only grading misses. These are structured conclusions, not a grade of private chain-of-thought.
- Typed references, recoverable whitespace validation, larger limits, and logged identical-request retries reduce unrelated friction. The current request shape preserves the organization's stated feature constraint.
- Private verifier separation, controller collection, fresh state, and audit continuity remain intact in the exercised paths.

## Recommended difficulty direction

### First: dependent determinations with fact-level corrections

Prefer a dependency graph over a longer list of notes. For example:

`corrected administration date → valid course/restart → completion anchor → governing follow-up interval → due date → whether a result satisfies that requirement`

Make a correction to an early fact require recomputing several downstream conclusions. Include similarly long histories where the correction has no downstream effect. Grade the governing records and derived dates, allowing equivalent sufficient evidence. A final note that states every downstream conclusion largely collapses this challenge.

### Second: multiple episodes and documented shared evidence

Examples include two episodes in one patient history, merged identities, or a shared laboratory correction that applies to several records. Require the agent to establish which episode and requirement a genuine result satisfies; a correct test in the wrong episode should not settle the current issue.

These require deliberate interface/schema changes. Current evidence validation restricts citations to the item's patient/episode, and the prototype fixes one episode per patient. A correction available only in another chart must be discoverable and legally citable under the public tool contract. Do not just insert a cross-chart case and silently retain the old restrictions.

### Third: conditional protocol composition, not arbitrary rule volume

Several clearly defined provisions can interact: validity of an event, replacement scope, anchor selection, a timing exception, and completion matching. Start with a compact protocol and histories that need several provisions together. Twenty-five provisions or clinically unusual rules do not inherently produce useful difficulty. Keep rules explicit and coherent with the synthetic workflow.

### Lower priority: harder induction and simple chain length

The prototype is a promising separate experiment, but withholding more conventions or reducing precedents risks ambiguity. If continuing induction, use bounded candidate standards and verify agreement of all consistent candidates on the current answers; randomize surface details and reserve new combinations for validation.

Long prose-only chains and references such as “my note from Tuesday” can become reference-resolution puzzles. Prefer unique, discoverable event references; make the difficulty come from the effect of a correction. A ten-event chain is not necessarily harder if the last event summarizes its result.

## Suggested next experiment

1. Fix the malformed-input classification gap and label results by exact adapter/task version.
2. Build a small set of fresh case families around dependent determinations and episode-specific evidence, with an independent public-record reconstruction.
3. Run shortcut baselines and representation-invariance checks before spending on model pilots.
4. Pilot only after authorization, distinguish semantic mistakes from task/transport defects, and evaluate held-out variants rather than merely choosing individual cases that happened to fail.
5. Freeze the final fixture and protocol before the final batch. Keep every run and its exclusion reason, and report a ceiling honestly if fair cases remain too easy.

Do not use tighter budgets, suppressed clinical evidence, guessed conventions, or arbitrary exact citation lists to force the requested pass band. The handoff's core conclusion—that more repetitions of already-solved decisions are unlikely to be an efficient next step—is reasonable even though its numerical forecast is not.

## Verification and evidence

- Existing offline suite: **42/42 passed** (`PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest discover -s qa -p 'test_*.py' -v`).
- Main generator and private baseline reproduced in memory with file writes intercepted; exact match.
- Prototype generator fixture and expected-answer output reproduced in memory; exact match.
- Readable/encoded note consistency: **136 main notes and 189 prototype notes**, all matching.
- Prototype hypothesis enumeration: **65,536 combinations; one consistent survivor**.
- Malformed patient checks: prototype lists/objects produce **500, faults=1**; main task produces **400, faults=0**. No live trial was altered by these temporary-database probes.
- Ten latest saved model trajectories inspected for summaries/commands; no private-path command matches or unredacted Anthropic-key-pattern matches in those event logs. This is not a comprehensive secret scan or an assertion about every historical artifact.
- Fresh Harbor main oracle **1**, main no-op **0**, prototype oracle **1**, prototype no-op **0**; all valid, no exceptions.
- Fresh main/prototype boundary probes: **exit 0**; private paths/admin routes/socket checks passed; planted agent-side snapshots were not used. Their clinical reward is correctly **0** because they do not solve the task.
- All six fresh snapshots were frozen, had zero recorded service faults, and contained trusted service state.

Fresh artifacts: `jobs/chartr/audit-difficulty-20260927-1790490347608/`, with separate `main-oracle`, `main-nop`, `main-boundary`, `proto-oracle`, `proto-nop`, and `proto-boundary` jobs. Original pilot artifacts were preserved.

No changes were made to address the findings, and no new difficulty variants were implemented or measured. Broader exploit resistance, all possible semantic shortcuts, and performance of proposed harder tasks remain unproven.
