# Task 3 final confirmation — v0.3.1

**Result: 5 passes / 10 valid attempts.** This is the first and only confirmation batch under the committed protocol, not pooled with earlier pilots. The observed result is inside the declared 2–7/10 target. A ten-run result is a small-sample measurement, not a guarantee of the underlying pass probability.

## Freeze and execution

- Evaluated code: `19edc3b`; dispatch checkout: `63a05e4b838f6ceb99aa519a2448521d7cb782c2` (protocol documentation additions only).
- Model `claude-opus-5`, direct Anthropic adapter 0.4.0, Harbor 0.23.0, anthropic 1.8.0.
- Ten concurrent trials; 250 turns, 64,000 output tokens per response, 1,800 s API timeout, 7,000 s wall timeout, default 60 s tool timeout, prompt caching enabled.
- Fresh isolated services and controller-collected final snapshots. Task 4 started only after this job exited and Docker was idle.
- `DISPATCH.txt`, `FREEZE.json`, `PROVENANCE_START.json`, `SCORE.txt`, `RESULTS.json`, and every original trial artifact are preserved here.
- All ten provenance checks passed against the frozen task/provider/adapter/model/budgets. All ten attempts ended `end_turn`, with valid grading evidence. No invalid attempts, replacements, API retries, or budget failures.
- Agent runtimes: 1,210–1,774 seconds (20.2–29.6 minutes); 40–63 turns.
- No task/key changes or retrospective rescoring were performed.

## Per-attempt outcomes

| Trial suffix | Result | Category | Findings |
|---|---|---|---|
| Xw6Xdrd | Fail | Model | Three cross-chart follow-up overclaims: g017, g019, g021. |
| 2LCiX4L | Fail | Model | Two missing 24-month follow-ups: g024, g040. |
| reSK6L9 | Pass | — | All graded requirements satisfied. |
| uBiC29g | Pass | — | All graded requirements satisfied. |
| bdK7sjH | Fail | Model | Same two missing 24-month follow-ups: g024, g040. |
| xMreuhf | Fail | Model | Same three cross-chart follow-up overclaims: g017, g019, g021. |
| 6XqsLvn | Pass | — | All graded requirements satisfied. |
| TSGnJbn | Pass | — | All graded requirements satisfied. |
| SXq9ZER | Fail | Model | Five missed/overclaimed candidates, plus an inadmissible evidence reference. |
| Ng8WpkK | Pass | — | All graded requirements satisfied. |

Trial order above follows the recorded start order used by `qa/confirm_summary.py`. Every attempt counts.

## Failure review against the records and public contract

### Cross-chart specimen identity must affect follow-up (Xw6Xdrd, xMreuhf)

For g017 (`P5fb1a55`), g019 (`P0a02a70`), and g021 (`P7f26af5`), the agents submitted `confirmed` follow-up overdue. The frozen answer is `cannot_determine / UNRESOLVED_SOURCE_CONFLICT`: a specimen in another chart has conflicting collection and accessioning identities, one identifying this patient, and falls within the follow-up window. Its unresolved ownership makes completion unresolved, rather than definitely absent.

For example, g017 was treated 2025-07-17; the 12-month window is 2026-06-17 through 2026-08-16. RPR accession `A2607-5274` was collected 2026-07-19. Its collection record `R829ba91362de` identifies Omar Dubois (MRN 15327248), whereas accessioning record `R7d5a968bb94b` identifies Carmen Grimes, g017 (MRN 62383973, DOB 2002-10-06). The public policy explicitly makes conflicting identities unresolved. The saved explanations instead say there was no qualifying specimen from this patient. This is a failure to carry an unresolved cross-chart identity into the dependent decision, not a citation-wording defect. Xw6Xdrd's tool trace includes its follow-up computation at turns 41–44 and final item construction at turn 52; xMreuhf's decision/item construction is at turns 37–43.

### Recognized misfiling, but missed the dependent 24-month follow-up (2LCiX4L, bdK7sjH)

Both trials correctly saved confirmed misfiled-result items for g024 (`Pf1afd77`) and g040 (`P89617e6`), but omitted their overdue follow-up items. Absence means `not_an_issue` under the public contract.

- g024: early latent syphilis treated 2024-01-09. The 24-month RPR on 2026-01-09 (`Rf8bc98b634e8`) belongs to Tomas Tran, as both collection `Rdbdb4ba126da` and accessioning `R672a379bef39` agree. The chart therefore lacks a qualifying 24-month specimen from g024.
- g040: early latent syphilis treated 2024-02-13. The purported 24-month RPR on 2026-02-18 (`R403fc5a6f8aa`) belongs to Bruno Ibarra, as collection `Rcd049fac5e54` and accessioning `Rbbeb3d7e59e0` agree. Its own 24-month follow-up is likewise missing.

Both windows were closed by 2026-09-24. The cases use the latent-syphilis follow-up schedule, including 24 months. The saved misfiling explanations explicitly identify the different patients, yet the agents did not save the dependent follow-up issues. Relevant submission construction is in 2LCiX4L turns 32–34 and bdK7sjH turn 42.

### Missed identity and authority dependencies, plus a citation error (SXq9ZER)

- g030 (`P3db8d7e`): omitted a confirmed misfiled result. Observation `Rc31e0c8abea0` is in this chart, but its specimen `R90e3c049705b` and accessioning `Rd27056c57066` identify Pablo Navarro (`P4b6a686`), MRN 25725401, DOB 1965-08-01. This is a definite identity mismatch.
- g062 (`P831ad43`): omitted three required abstentions: inadequate treatment, misfiled result, and pregnancy-treatment inadequacy. Positive hCG `R72de81cb596a` has collection `R61607a56f396` identifying Quinn Alvarado, but accessioning `Reb9d408459aa` identifies Leah Orozco. A completed 14-day doxycycline dispense (`R439ac6413db1`) is recorded; whether that treatment is adequate depends on pregnancy status. Unresolved hCG identity must propagate into all three decisions.
- g103 (`P77cc283`): omitted pregnancy-treatment inadequacy. The received Mercy General discharge summary `R4ce2b8c230c0` establishes delivery on 2024-11-29, 29 days after the 2024-10-31 dose (`R560d6a7f4cbc`). The later clinic note says 2024-12-03, but the public convention says other records do not change care established by the received outside-facility record. The 30-day requirement is not met.
- An item for `Pbeb5a65` also fails the public evidence-admissibility rule. This is a model citation error in an otherwise valid submission; it is separate from snapshot integrity. The five incorrect dispositions already suffice for failure.

SXq9ZER's saved submission construction is at tool turns 38 and 40. The final trusted snapshot, rather than any intermediate proposed answer, determines the score.

## Interpretation and limits

All five failing runs have defensible model errors under the unchanged public rules; no task/grader defect was identified in this failure review. Across the ten runs, 15 of 8,000 candidate dispositions/codes were wrong (99.8125% candidate accuracy), and one run additionally failed evidence admissibility. The zero-tolerance task-level score remains **5/10**, not the candidate accuracy. These traces demonstrate failures of linked reasoning and completeness, rather than infrastructure or output-budget failures. This review is not an independent clinical specialist adjudication of every fixture.
