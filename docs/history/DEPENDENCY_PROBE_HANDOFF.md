# Dependent-history probe — September 27, 2026

Private design and evaluation notes. Keep outside all evaluated images.

## Scope and fixes

The requested next experiment is `chartr_probe` v0.1.0, separate from the historical main
task and induction prototype. It tests dependent determinations and episode-specific
evidence with an explicit protocol. Twelve new patients have two episodes each and 289
FHIR R4 resources in total. Original records and later scoped amendments must be combined
before calculating plan selection, dose membership, completion, follow-up due date, and
whether a result qualifies. Retractions can target a single clause or another retraction.
Other clauses survive. Some corrections change an intermediate answer without changing
the final disposition. Nurse proposals and unrelated-episode revisions are controls.

There is no historical demonstration bank to copy. Public IDs are opaque and no final
note states the reconstructed completion, due date, or disposition. The new probe uses
fresh combinations rather than transplanting P302/H215. The legacy induction fixture is
retained with its known near-copy explicitly documented; its previous pilots remain useful
historical evidence, not evidence about the new probe.

The prototype patient-input defect is fixed in v0.1.1: lists, objects, null, numbers, and
booleans return an ordinary 400 and do not increment service faults. The new service has
the same check. Main task v0.5.2 replaces P132's answer-bearing addendum with the actual
second-dose date and explicit restart retraction. Clinical answers and accepted evidence
sets for both legacy tasks are unchanged. Fixtures, note attachments, versions, and
private integrity baselines were regenerated through their existing builders.

## Independent checks and limitations

`qa/probe_cases.py` manually specifies expected fields; `qa/build_probe.py` renders them
and the clinical fixture. `chartr_probe/solution/reference.py` independently reconstructs
the public chart and submits through the same clinic CLI. It imports no private answers,
case sheet, or generator. Agreement on all twelve patients is useful independent
implementation evidence, but is not a blinded external clinical review.

Known shortcut controls, number of patients wrong out of twelve:

| Wrong algorithm | Patients wrong |
|---|---:|
| Original structured fields only | 11 |
| Latest amendment only | 11 |
| Ignore retractions | 8 |
| Retract an entire note instead of one clause | 7 |
| Latest plan silently wins | 1 |
| Keep pre-correction dose-sequence membership | 6 |
| Count first three doses despite gaps | 4 |
| Use latest administration as completion | 5 |
| Accept another episode's result | 4 |
| Ignore result-window opening | 3 |

All ten fail the overall task. These are deliberate wrong implementations, not empirical
proof against all possible shortcuts. Opaque ID renaming and reversed record presentation
preserve reference answers. Model robustness to those variants has not been measured.
Regular amendment text permits a programmatic solver; correct tool-assisted reasoning is
allowed. This prototype has limited clinical realism and does not yet include cross-patient
identity merges or a held-out generated family.

Intermediate outputs are checked exactly where policy determines one answer. Dose-list
order is ignored, any qualifying completion result is accepted, and explanations need only
be nonempty. Narrative quality is not judged. Backend validation is operational and does
not reveal correctness. The existing controller stops the agent, collects/freeze service
state, and supplies it to a separate private verifier. No isolation architecture or
dependencies were changed.

## Verification and artifacts

Evidence root: `jobs/chartr/dependency-probe-20260927-1790527316201/`.

- Full offline suite: 52/52 passed; the subsequently added executable-entrypoint test also passed.
- New probe: Docker `oracle-fixed` reward 1; `nop` reward 0.
- `boundary`: exit 0, no private files/admin routes/socket/credentials, forged agent-side
  snapshots ignored. Clinical reward 0 is expected because the probe submits no decisions.
- Main 0.5.2 and prototype 0.1.1: each fresh Docker oracle 1 and no-op 0.
- `shortcut-results.json` records wrong-patient sets for all ten controls.
- The original `oracle` run returned 0 because `/solution/solve.sh` was not executable.
  It never reached the clinic and is a setup failure, not an oracle clinical miss. Permissions
  were fixed and regression-tested before any paid pilot. Its artifacts are retained.
- Bare `-a anthropic_agent` was rejected by installed Harbor 0.23.0 before creating a job
  or calling Anthropic. The working syntax is `-a anthropic_agent:AnthropicAgent`.

## Paid pilot configuration

The user explicitly approved five paid pilots after free checks. Exactly five trials are
requested in `opus-pilot`, using `claude-opus-5`, adapter 0.3.1, Harbor 0.23.0, and the
existing organization's API configuration loaded from `.env`. The request shape remains
model/max_tokens/tools/messages, with no additional API features. Limits: 150 turns,
16,000 output tokens, 3,500 seconds, 100,000 tool-output characters. No Harbor job retries.
The adapter can retry the identical request after transient API failures and logs each one.
Every trial records task/adapter hashes, trajectory, usage, termination, trusted snapshot,
and private diagnostics. Do not pool this configuration as identical to earlier adapter
0.3.0 cached/thinking-enabled main-task pilots.

## Results and interpretation

**5/5 pass**, all valid `end_turn`. All 60 patient determinations passed every graded field.

| Trial suffix | Turns | Seconds | Reward |
|---|---:|---:|---:|
| BbWQHYL | 24 | 335 | 1 |
| FW7SfQR | 15 | 333 | 1 |
| Ue6WZHV | 16 | 378 | 1 |
| xUux64n | 14 | 375 | 1 |
| xWbDs5N | 25 | 315 | 1 |

Every run read all twelve charts and saved twelve determinations. Zero API retries,
nonzero tool exits, tool truncations, or service faults. All task hashes matched the
frozen files in all five manifests; all snapshots were frozen. No private-path command
matches or unredacted Anthropic-key-pattern matches were found in these new pilot
artifacts (a bounded check, not an exhaustive security claim). Aggregate usage:
3,128,459 input and 118,763 output tokens, with no cache usage. Dollar cost is not
estimated from an assumed price. See `pilot-summary.json` for the complete per-run data.

Recorded actions show chart-summary scripts followed by explicit determinations, sometimes
batched into scripts. The model handled partial retractions, a retracted retraction,
sequence changes, and course reassignment correctly. The reviewed saved explanations also
identify those dependencies. Explanations are supporting observations, not independently
graded proof of an internal reasoning process. There are no clinical misses to triage.

**The desired failure rate is still not achieved.** Removing known shortcuts improved
validity without inducing errors in this batch. The remaining tractability is visible:
each case still reduces to a small local ledger, each amendment names an exact entry and
field, and the protocol composes cleanly. The second episode mainly tests evidence
exclusion; it does not create a large shared dependency graph. All cases use the same
nurse proposal and late old-plan revision as controls, so their repeated shape becomes
easy to recognize, though it does not supply the patient-specific answer. This is not
evidence of a hidden answer leak, and correct use of a script is legitimate success.

For a materially different next probe, prioritize three changes together:

1. Several live courses and requirements in one chart, where a correction changes which
   requirement a genuine result satisfies; one correction should alter multiple outputs
   differently, with controls where it changes none. Define reuse/episode rules explicitly.
2. Decisions that depend on reconstructing overlapping intervals and conditional protocol
   branches, rather than only a three-event count followed by one month addition. Keep
   record references discoverable and retain independent reconstruction and boundary tests.
3. Held-out combinations and varied presentations authored before inspecting pilot misses.
   Vary record counts, timing, authority, and correction forms independently of outcome;
   avoid giving every chart the same obviously ignorable late-note pattern. Require
   equivalent clinical meaning across variants rather than hiding facts or using ambiguous
   prose. Measure those variants instead of merely selecting one lucky failed case.

These are design suggestions, not implemented or measured improvements. More routine
patients or longer terminal summaries would repeat already-solved work. Do not launch
more paid runs without authorization, edit these frozen task files to reinterpret the
five results, tighten budgets, or hide rules to manufacture failures.

## Resume map

- Start with this document and `PROGRESS.md`; existing old handoffs describe earlier versions.
- New task, service, CLI, policy, private solver and grader: `chartr_probe/`.
- Canonical cases/renderer: `qa/probe_cases.py`, `qa/build_probe.py`.
- New tests: `qa/test_probe.py`; malformed-patient regression: `qa/test_proto.py`.
- Main shortcut correction: `qa/build_fixture.py` P132 addendum, regenerated main fixture/baseline.
- Prototype bug fix: `chartr_proto/environment/service/store.py`, regenerated v0.1.1 artifacts.
- All previous artifacts and pre-existing uncommitted work were preserved. No commit made,
  dependency upgraded, subagent used, or further paid trial authorized.
