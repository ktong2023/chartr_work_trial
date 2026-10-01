# Task 4: cardiology population review with raw ECGs (`chartr/cardiology-population-review` v0.4.2)

**Final result: 3/10** Claude Opus 5 attempts pass, inside the 2–7/10 target. This is the v0.4.2 confirmation batch, run under
the predeclared protocol below. The full triage is in
[`results/confirm-task4-0.4.2-20260929T050729Z/TRIAGE.md`](../results/confirm-task4-0.4.2-20260929T050729Z/TRIAGE.md).

## Contents

- [Overview](#overview)
- [Environment](#environment)
- [Tools given to the model](#tools-given-to-the-model)
- [Final confirmation batch: 10 trials](#final-confirmation-batch-10-trials)
- [Version history](#version-history)
- [Limits](#limits)
- [Licensing and citations](#licensing-and-citations)
- [Final confirmation protocol (v0.4.2)](#final-confirmation-protocol-v042-fixed-september-29-2026-before-any-v042-trial)

## Overview

The agent reviews a 100-patient cardiology clinic population (69 living) as of September 24, 2026, 12:00 America/New_York.
The population is built on **real de-identified hospital data and real 12-lead ECGs** from the MIMIC-IV demo datasets, with a
synthetic outpatient layer. Clinical determinations follow current ACC/AHA guidance, including the 2023 AF guideline.

**Two outputs.**
1. **Review items** for every issue that needs clinical review. There are 20 in the key, across 18 patients:

   | Category | Reasons | Count |
   |---|---|---|
   | Anticoagulation | untreated AF (CHA2DS2-VASc score and factors) | 4 |
   | | an anticoagulant despite a contraindication | 1 |
   | QT safety | prolonged QTc on a QT watch-list drug | 4 |
   | Follow-up | ECG after starting a watch-list drug | 7 |
   | | INR after a warfarin dose change | 2 |
   | Contradiction | dual anticoagulation | 1 |
   | | a note's rhythm contradicted by a same-day ECG | 1 |

2. **A structured interpretation of each living patient's most recent ECG** (37 ECGs), read from the raw waveform:
   - rhythm, rate, PR/QRS/QTc and axis;
   - conduction blocks;
   - changes from the patient's previous ECG.

**What makes it hard.**
- **Hidden evidence.**
  - Two untreated-AF patients have their AF documented outside the obvious places: for one, only in clinic-note history
    lines and inpatient rhythm charting (no diagnosis codes, no ECG).
  - Operational rules live in dated clinic memos inside the chart, not in the prompt: the QT watch list, the 500 ms
    threshold, which ECG-after-start window applies to which start date, and who may change warfarin doses.
- **Real ECG reading.** Nothing explains how to read an ECG. The agent gets raw WFDB files and analysis libraries, and must
  measure rate, intervals and QTc itself on real tracings, including artifact, LBBB and a transient RBBB.
- **Look-alikes** that must *not* be flagged:
  - a remote bleed;
  - a clean anticoagulant switch;
  - an older long-QT ECG followed by a normal one;
  - sinus rhythm documented in paroxysmal AF;
  - a watch-list start before any memo applied;
  - inpatient orders;
  - deceased patients.

**Scoring** is all-or-nothing across six components: identification, item fields, ECG interpretation, ECG comparison,
ECG linkage and chart rules.
- ECG fields are graded only where three automated readers agree; elsewhere any value is accepted.
- Explanations are not graded.

## Environment

**Containers.** Each trial runs two containers on an internal Docker network with no internet access:
- **`main`:** the agent's container. All Linux capabilities are dropped. It holds the `clinic` CLI, the public docs at
  `/app/`, and pinned Python analysis libraries: numpy, scipy, pandas, wfdb, neurokit2, PyWavelets, scikit-learn and
  matplotlib (`environment/agent-requirements.txt`).
- **`clinic`:** a read-only record service. It serves the MIMIC-IV FHIR resources plus the overlay, and the ECG files.

**How the database is built.** At image build time, the pinned PhysioNet files are fetched and checksum-verified (446
files). The database is then assembled deterministically, with a content digest pinned in `tests/baseline.json`:
- Each patient's whole record is re-dated to the evaluation year by whole weeks, which preserves weekday and season.
- A private build (`qa/build_task4.py`) adds 2,896 synthetic outpatient resources (visits, medication orders, labs, notes,
  calls, clinic memos), cloned from real record shapes.
- Every living patient gets the same kind of outpatient layer, so case patients do not stand out.
- 9 ECGs carry small edits (QT lengthening, artifact), stored as sample deltas against the originals.

**ECG answer key.** It comes from three automated readers plus designer review:
- the ECG cart's own measurements and statements (MIMIC-IV-ECG v1.0, never shown to the agent);
- neurokit2 delineation;
- an in-house 12-lead method.

The per-field agreement rules are in the build log. No blinded cardiologist adjudicated the labels.

## Tools given to the model

**Interfaces.** The agent gets a shell in the `main` container (the adapter's single `bash` tool), so it can write and
run analysis scripts. The clinic is reached through the `clinic` CLI:

| Command | What it does |
|---|---|
| `clinic patients [--page N]` | The population |
| `clinic search TYPE [--patient ID] [--since/--until DATE] [--code CODE] [--all] [--out FILE]` | FHIR R4 resources of one type (Encounter, Condition, Observation, MedicationRequest, MedicationAdministration, DocumentReference, …), optionally written as NDJSON |
| `clinic documents [--out FILE]` | Clinic-wide documents (the memos) |
| `clinic ecg list [--patient ID]` / `clinic ecg fetch ECG_ID --dir DIR` | List ECGs; download a 12-lead, 10 s, 500 Hz WFDB record (`.hea` + `.dat`) |
| `clinic item add/update`, `clinic items` | Save, update and list review items |
| `clinic interpretation add/update`, `clinic interpretations` | Save, update and list ECG interpretations |

**Prompt and documents.** The instruction is 81 words ([`instruction.md`](instruction.md)).
- [`environment/public/policy.md`](environment/public/policy.md) names the review categories, the guideline and the
  follow-up statuses.
- [`environment/public/tools.md`](environment/public/tools.md) defines the CLI and every field and vocabulary. For example,
  `qtc_ms` is Bazett-corrected and the axis categories are given in degrees.

## Final confirmation batch: 10 trials

**Batch.** It ran on September 29, 2026, with frozen commit `98a881a`, model `claude-opus-5` and adapter 0.4.0. The budgets
were 300 turns and 64K output tokens per response, with prompt caching on.
- All 10 attempts were valid, with no reruns and no budget failures.
- Each run took 38–51 min and 71–136 turns.

| Trial | Result | What it got wrong |
|---|---|---|
| FfbFpxA | **pass** | — |
| HckdLbS | **pass** | — |
| Uaz9uQt | **pass** | — |
| 46BXFi9 | fail | Read QTc 378 ms on 109218019, against an accepted range of 378.6–481.6 (a 0.6 ms miss). Its only error |
| bwXA5S6 | fail | Cited a progress note that doesn't mention AF as AF evidence for 10039997; the AF, score and factors were right. Its only error |
| jNaD9x7 | fail | Found the hidden AF for 10020306, but also cited an inpatient apixaban order as AF evidence. Its only error |
| o5seZqt | fail | Missed the untreated AF for 10020306, documented only in notes and inpatient charting. Its only error |
| KeH4CQX | fail | Missed the untreated AF for 10004235, and over-read QTc as 526 ms on 109952008 (accepted up to 499) |
| MS3GSSY | fail | Missed the untreated AF for 10020306, and over-counted the ventricular rate on two QT-edited tracings (76 vs 57–67; 71 vs 52.5–62.5), which also failed both QT items' heart rate |
| uRTwKAB | fail | Missed the untreated AF for 10020306, used a phone note about a *not yet received* outside ECG as a completion record, and under-read QTc as 354 ms on 109218019 |

**Pattern.** All failures are model errors; there are no task or grader defects. They fall into four kinds:
- hidden AF missed (4 runs);
- ECG measurement errors (4);
- a non-AF record cited as AF evidence (2);
- an unreceived ECG treated as done (1).

**Contested, but counted under the stated rules:**
- `tools.md` defines `af_evidence` as "records establishing AF". Under a lenient rule that ignores extra citations, the two
  over-citations would pass and the batch would be 5/10.
- The 0.6 ms QTc miss is outside a range that already includes a 40 ms inter-observer margin.

## Version history

| Version | Date | Change | Opus 5 result |
|---|---|---|---|
| 0.1.0, 0.1.1 | Sep 27 | Review items only (AF, QT, follow-up, contradictions) on the MIMIC-IV demo population. 0.1.1 fixed four answer-key defects | 0/5 raw (1/5 rescored), then 1/5. Nearly all misses were one hidden-AF patient |
| 0.2.0 | Sep 27 | Three new cases: AF only in inpatient rhythm charting, a QT "acceptable" note contradicted by the ECG, a date-dependent memo window | 0/5 |
| 0.3.0, 0.3.1 | Sep 27 | Full ECG interpretation with serial comparison and harder tracings; three-reader answer key | 0/5 |
| 0.3.2–0.3.6 | Sep 27–28 | Calibration: AF added to note history lines, interpretations required only for living patients, multi-reading rhythms, axis and PR margins | 0/5, then 1/5; 1/10 raw (4/10 rescored) |
| 0.4.0 | Sep 28 | Response to an independent audit: QT decision margins, consistent serial QTc rules, service concurrency, leakage fixes | Pilot 3/10 |
| 0.4.1 | Sep 28 | Release-validation fix: a required bundle-branch block needs QRS ≥ 120 ms | Confirmation 1/10, below target; stands as that version's result |
| **0.4.2** | Sep 29 | Announced calibration (details below) | Rescore of the earlier 20 runs 8/20, then **confirmation 3/10** |

**v0.4.2 changes:**
- ECG 108912996 is rhythm-ambiguous: AF or sinus accepted.
- 10004235's AF diagnosis codes are restored; 10020306 stays the hidden-AF case.
- QRS duration is graded only where a bundle-branch block is required, with a ±30 ms margin.
- First-degree AV block on 102280728 is accepted rather than required.

The full build log is in
[`docs/history/chartr_task4_build_log.md`](../docs/history/chartr_task4_build_log.md). It covers:
- per-pilot triage;
- the ECG catalog and edits;
- the per-field reader rules;
- QA;
- the classification of every post-pilot change as a defect fix, a label adjudication or a calibration.

The audit is in [`docs/audits/`](../docs/audits/), and the release validation in [`docs/release/`](../docs/release/).

## Limits

- **ECG labels.** They come from automated readers plus designer review, not blinded cardiologists. Ambiguous tracings
  accept every defensible reading.
- **Grading.** Explanations are not graded, so a pass certifies the graded fields, not a complete clinical interpretation.
- **Calibration history.** Several calibrations were made after seeing pilot runs. Rescores are development evidence; only
  the confirmation batches are results.
- **Data.** The outpatient layer, the memos and some edited tracings are synthetic. The data is not for clinical use.

## Licensing and citations

**Data licence.** The task uses open-access PhysioNet data under the **Open Data Commons Open Database License v1.0
(ODbL)**. The data is re-dated and extended with synthetic records; the resulting derived database is shared under the
same licence, is not for clinical use, and uses no credentialed PhysioNet data. The pinned inputs are listed in
[`environment/service/overlay/pinned.sha256`](environment/service/overlay/pinned.sha256).

**Datasets and PhysioNet:**
- Bennett, A., Ulrich, H., Wiedekopf, J., Szul, P., Grimes, J., & Johnson, A. (2025). *MIMIC-IV Clinical Database Demo on
  FHIR* (version 2.1.0). PhysioNet. https://doi.org/10.13026/vphg-y548
- Bennett, A. M., Ulrich, H., van Damme, P., Wiedekopf, J., & Johnson, A. E. W. (2023). MIMIC-IV on FHIR: converting a
  decade of in-patient data into an exchangeable, interoperable format. *JAMIA*, 30(4), 718–725.
  https://doi.org/10.1093/jamia/ocad002
- Gow, B., Pollard, T., Nathanson, L. A., Moody, B., Johnson, A., Moukheiber, D., Greenbaum, N., Berkowitz, S., Eslami, P.,
  Herbst, E., Mark, R., & Horng, S. (2022). *MIMIC-IV-ECG Demo — Diagnostic Electrocardiogram Matched Subset Demo*
  (version 0.1). PhysioNet. https://doi.org/10.13026/4eqn-kt76
- Gow, B., Pollard, T., Nathanson, L. A., Johnson, A., Moody, B., Fernandes, C., Greenbaum, N., Waks, J. W., Eslami, P.,
  Carbonati, T., Chaudhari, A., Herbst, E., Moukheiber, D., Berkowitz, S., Mark, R., & Horng, S. (2023). *MIMIC-IV-ECG:
  Diagnostic Electrocardiogram Matched Subset* (version 1.0). PhysioNet. https://doi.org/10.13026/4nqg-sb35. Its machine
  measurements were used only as one labelling reader and are not shipped.
- Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026).
  PhysioNet as a global platform for biomedical research. *Nature Health*, 1(8), 792–795.
  https://doi.org/10.1038/s44360-026-00096-z

**Clinical standard:** Joglar, J. A., Chung, M. K., et al. (2024). 2023 ACC/AHA/ACCP/HRS Guideline for the Diagnosis and
Management of Atrial Fibrillation. *Circulation*, 149(1), e1–e156. https://doi.org/10.1161/CIR.0000000000001193

**Software:**
- Makowski, D., Pham, T., Lau, Z. J., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing.
  *Behavior Research Methods*, 53(4), 1689–1696. https://doi.org/10.3758/s13428-020-01516-y. It is used for labelling and
  is available to the agent.
- WFDB Python (`wfdb` 4.3.1) reads the ECG records.
- Harbor 0.23.0 runs the task; the agent uses the Anthropic API through `anthropic_agent.py`.

## Final confirmation protocol, v0.4.2 (fixed September 29, 2026, before any v0.4.2 trial)

*Kept word for word as fixed before the batch. Paths and file names in it are as they stood then; `PROGRESS.md` is now in [`docs/history/`](../docs/history/PROGRESS.md).*

This replaces the v0.4.1 protocol (September 28), whose batch scored 1/10 and stands as that version's result
(`jobs/chartr/confirm-task4-0.4.1-20260928T235846Z/TRIAGE.md`). This batch confirms the final release. Nothing in this section changes once the batch has started. Running it makes paid
model calls and needs the user's authorization.

**Frozen configuration**

| | |
|---|---|
| Frozen commit | `98a881a` on `main`. The checkout may be a later `main` commit only if no evaluated file differs from `98a881a` (step 2); only READMEs, `PROGRESS.md` and reports may change |
| Task | `chartr/cardiology-population-review` **0.4.2** (`task.toml`, service `chartr-task4-0.4.2`, baseline) |
| Answer key | `tests/expected.json` sha256 `aea0888c3e014ec49ece381eedb45037896be8d98c8a4f44a7ba56c8b9dfd04b` |
| Sources | digest `bb92ea2825a1c4b0d492e22166878aac1dc502237f880dea6b394335cf6f3f0f`, attested by the provider at every trial start; PhysioNet inputs pinned in `overlay/pinned.sha256` (446 files) |
| Harness | adapter 0.4.0 (`anthropic_agent.py` sha256 `95ce935a…3ead`), provider `chartr_environment.py`, Harbor 0.23.0, anthropic 1.8.0; host environment from `requirements.lock.txt` |
| Model and budgets | `claude-opus-5`; `-k 10 -n 10`; `max_turns=300`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`, `tool_timeout_sec=900`, `prompt_cache=true` |
| Host | Docker with ≥ 10 CPUs and 8 GB; no other ChartR trial running; `caffeinate` so the host cannot sleep |

**Exact commands** (bash, from the repository root)

1. Update the checkout: `git fetch origin && git checkout main && git pull --ff-only`
2. Frozen files unchanged (must print `frozen-files-ok`):
   ```bash
   git diff --quiet 98a881a HEAD -- chartr_task4 ':(exclude)chartr_task4/README.md' anthropic_agent.py chartr_environment.py chartr_job.yaml requirements.lock.txt && echo frozen-files-ok
   ```
3. Preflight (every line must be `ok`): `python3 qa/task4_preflight.py 0.4.2`
4. Create the batch's unique output directory. It is never reused; the command refuses an existing path and records the
   dispatch state:
   ```bash
   D="$PWD/jobs/chartr/confirm-task4-0.4.2-$(date -u +%Y%m%dT%H%M%SZ)"; test ! -e "$D" && mkdir -p "$D" && { git rev-parse HEAD; python3 qa/task4_preflight.py 0.4.2; } > "$D/DISPATCH.txt" && echo "$D"
   ```
5. Run the batch (job name `batch`):
   ```bash
   caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=300 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak tool_timeout_sec=900 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$D"
   ```
6. Score: `python3 qa/confirm_summary.py chartr_task4 "$D"`. If it reports `INCOMPLETE`, rerun the same command with
   `-k N -n N`, where N is the number of missing valid attempts. Use the next unused job name (`rerun-1`, `rerun-2`, …) in the
   same `$D`, then score again.
7. Write `$D/TRIAGE.md`, then commit `$D` to the `task4-pilot-results` branch.

**Counting rules** (applied by `qa/confirm_summary.py`)

- **Headline:** passes among the first 10 valid attempts, in start order. The 2–7 of 10 target is judged on this number alone.
  It is reported whatever it is, and no further batch is run to reach the target.
- **Invalid attempts** get no reward and are not attempts: API or adapter errors, cancellation, service faults, and evidence or
  integrity failures. Report them and rerun under the same command (step 6) until there are 10 valid attempts.
  - If one job has 3 or more invalid attempts, stop and fix the infrastructure without touching frozen files.
  - If a frozen file must change, the batch is void.
- **Budget failures:** valid attempts that end on output truncation, turn, wall or tool timeout, or context exhaustion count as
  failures in the headline. They are also listed as a separate category.
- **Provenance:** every trial's manifest must match the frozen task files (README excepted), provider, adapter, model and
  budgets. One mismatch voids the batch; the script exits 1.
- **Triage:** classify each failure from its saved items and trace as a model failure, a task/grader defect, or a budget
  failure.
  - A defect is fixed in a new version and reported separately.
  - This batch is never re-scored, and it is not pooled with earlier batches (the v0.4.0 pilot 3/10 and the v0.4.1 confirmation 1/10 stand as those versions' results).
