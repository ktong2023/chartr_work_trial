# Brief: upgrade Task 1 onto real MIMIC-IV demo data, with ECG comorbidity escalation

Read fully first. **Phase 1 is a design proposal only.** Do not build, download into the
task, or change files until I approve it. This builds on `TASK1_POLICY_REDUCTION.md` and
`TASK_DESIGN_PRINCIPLES.md`; both still apply.

## Goal

Task 1 is currently too easy. The upgraded task should:

1. **Use the real, messy MIMIC-IV demo cohort** (all 100 patients) as the clinic's
   population. Our syphilis cases are grafted onto real patients, and our synthetic
   records must not be distinguishable from the real ones.
2. **Scale up.** The agent reviews the whole population and must identify the syphilis
   patients itself, rather than being handed a target list.
3. **Add real ECGs** from the same patients. The agent reads the raw waveforms, identifies
   a defined set of actionable cardiac findings, and **escalates the related syphilis
   follow-up** to a higher-priority review item that states its reasoning and evidence.

All determinations rest on the CDC standard of care, instructions written in the chart,
and a bare-bones interface (per `TASK1_POLICY_REDUCTION.md`).

## Data sources and licensing (hard constraints)

- **Clinical base:** *MIMIC-IV Clinical Database Demo on FHIR* (PhysioNet, 100 patients,
  **Open Data Commons ODbL**). Resource types include patients, encounters, ED data,
  conditions, procedures, lab, micro, chart and ED observations, specimens, and the
  medication request, administration, dispense and statement records.
- **ECGs:** *MIMIC-IV-ECG Demo* (PhysioNet, ODbL), whose records sit under the same
  patient IDs as the clinical demo. Confirm and report the actual overlap: how many of the
  100 patients have ECGs, and how many ECGs each.
- **Use only these open datasets.** No credentialed MIMIC modules (full MIMIC-IV,
  MIMIC-IV-Note, cardiologist reports). PhysioNet's rules prohibit sending credentialed
  data to third-party APIs, and every trial sends chart contents to the Anthropic API.
- Include the ODbL attribution notice. Derived databases we share stay under ODbL.

## Part A: graft the syphilis cases into the real cohort

- **Choose patients deliberately.** For each existing Task 1 case (and new ones, see
  scale), pick a demo patient whose age, sex and real history fit.
- **Screen each patient's real record for conflicts** (prior penicillin, relevant labs,
  conditions that would change the answer). Either choose a non-conflicting patient, or
  keep the conflict intentionally as a validated distractor with a documented expected
  answer.
- **Match the time frame.** MIMIC dates are shifted per patient into the future. Place
  every grafted episode, and the evaluation time, coherently on each patient's timeline.
  Propose one approach: a global shift of the demo, or per-patient anchoring.
- **Blend in completely.** Synthetic resources must follow the demo's conventions exactly:
  - the same profiles and `meta` fields, identifier systems, ID format, and code systems
    (local lab item codes and any LOINC mappings, medication coding, ICD version by era);
  - the same encounter, location and organization linkage;
  - the same timestamp precision and value formats;
  - the same missing-field patterns, with volume and distribution comparable to real
    records.
- **Run a distinguishability test.** Write a check (and have an independent reviewer try)
  to tell synthetic resources from real ones using only structural features: field
  presence, ID shape, codes, precision, ordering, `meta`. Anything that separates them
  better than chance must be fixed. Report the result.

## Part B: synthetic notes across all 100 patients

- The demo has no free-text notes, so notes that exist only for case patients would give
  the cases away. Add realistic clinical notes (progress, nursing, telephone, outside
  records requests, lab comments) for **every** patient.
- **Each note must agree with that patient's real data** (diagnoses, meds, labs, dates),
  generated from the patient's actual record.
- **Notes add confusion without creating unintended answers:**
  - realistic mentions that look relevant but aren't decisive (a negative RPR screen, a
    penicillin course for a non-syphilis infection, doxycycline for another indication,
    a remote history of treated syphilis with a documented response);
  - the Task 1 case content itself, in varied natural wording.
- **Every control-patient note must be verified** to create no target determination. Any
  note that could reasonably create one gets fixed or gets a documented expected answer.
- No record-ID citations in prose, no sentences written to rule out wrong answers, no
  templated clause structure.

## Part C: ECG findings and escalation

- **The agent gets raw WFDB waveforms only.** Strip machine measurements and machine or
  cardiologist interpretation statements from anything the agent can reach. Keep them
  private, as designer aids only.
- **A defined, short list of target findings** (a definition, not a hint). Proposed:
  atrial fibrillation; high-grade (second-degree Mobitz II or third-degree) AV block;
  QTc above a stated threshold using a stated correction formula. Propose the final
  list, threshold and formula.
- **Only clear-cut ECGs count.** A finding is used only if it is unambiguous with a wide
  margin (sustained AF; QTc well above or below threshold). Ambiguous ECGs are excluded
  or used only as clearly normal controls. Document how each label was established.
- **Signal-vs-noise controls:**
  - real normal ECGs with added realistic artifact (baseline wander, motion, muscle noise,
    lead swap) that mimics a finding;
  - real findings on noisy recordings;
  - patients with several ECGs where only one shows the finding, or an older finding that
    has since resolved (evaluation-time logic applies).
- **Clinical link: escalation.** When a patient in active syphilis follow-up has a
  qualifying ECG finding current at evaluation time, their follow-up review item is
  escalated to a higher-priority item that records, in structured fields:
  - the finding code;
  - the source ECG record ID(s);
  - the key measured values (e.g., heart rate, QTc in ms), within a stated tolerance;
  - the syphilis follow-up item it escalates;
  - a short explanation.

  The escalation rule is a local clinic convention, so it gets one line of policy,
  or lives in a clinic standing-order record in the chart. Propose which.
- **Libraries:** preinstall pinned `numpy`, `scipy` and `wfdb`. **Do not** preinstall
  ECG delineation packages (e.g., `neurokit2`); building beat detection and interval
  measurement is part of the task. Flag this choice for me to confirm.
- **The agent can't view images** (bash-only adapter). Every target finding must be
  determinable from signal computation.

## Scale and cohort

- The agent reviews **all 100 patients** and must identify syphilis patients itself. Don't
  return a target-episode list. Being in the cohort is determined by the chart and CDC
  staging definitions.
- Propose the numbers: roughly 25–40 syphilis case patients (existing Task 1 mechanisms
  plus titer-series interpretation per CDC: compare like assays and labs only, one
  dilution is noise, fourfold means significant, a rise must persist more than two
  weeks); roughly 15–25 patients whose ECGs are used as findings or controls; the rest
  are real controls.
- Mix case kinds without signposting. No obvious twin cases.

## Interface

- **Realistic access:** search by patient and resource type with paging, like SMART on
  FHIR, plus a tool to fetch an ECG's WFDB files into the workspace. Large results go to
  files, not tool output.
- **Budgets are never a source of difficulty.** Use the healthy pilot settings (150 turns,
  16K output tokens, generous time and tool-output limits), log every truncation, and
  treat truncation-caused misses as environment failures.
- Public docs stay bare bones (see `TASK1_POLICY_REDUCTION.md`): task goal, evaluation
  time, the CDC-guidelines line, status and priority vocabulary, the ECG finding list and
  thresholds, the escalation convention (if it lives in the policy), and interface facts.

## Grading and validation

- **Separate diagnostics for each component:**
  1. cohort identification;
  2. syphilis determinations;
  3. titer interpretation;
  4. ECG findings;
  5. escalation items.

  Propose a pass rule, and say whether all components are required.
- Grade structured fields exactly. Measured values are graded within stated tolerances.
  Explanations are not graded.
- **The two-experts test for every case:** an independent reviewer, given only the chart,
  the public docs and the CDC guidance, must reach the authored answer. An independent
  solver must not see the private answers.
- **Wrong algorithms that must fail:**
  - flag every patient with a syphilis-related code;
  - treat artifact as AF;
  - compare RPR and VDRL titers directly;
  - count a one-dilution change as significant;
  - escalate without a current qualifying finding;
  - miss patients whose case evidence appears only in notes;
  - ignore real MIMIC records that affect the answer.
- The distinguishability test passes. Reference solution, oracle 1, no-op 0.
- Run renamed IDs and shuffled record order to confirm answers are unchanged.

## Constraints

- New task version or directory. Keep the current Task 1 and all job evidence.
- Do not read `.env`. Do not upgrade pinned dependencies. **No Anthropic API runs without
  my approval.**
- Datasets are fetched at image build time from the pinned PhysioNet versions, and their
  checksums are recorded.

## Phase 1 deliverable (in chat, then stop)

1. Confirmed data facts: demo resource types and volumes, ECG overlap per patient, how
   the date shift works.
2. The grafting plan: patient selection criteria, conflict screening, date alignment,
   blending conventions, and the distinguishability test design.
3. The notes plan: note types, how they're generated from each patient's real data, and
   how control notes are verified.
4. The ECG plan: target findings, threshold and formula, how labels are established,
   artifact types, and the escalation rule and where it lives.
5. Cohort numbers and a table of case kinds.
6. The interface and the full proposed public docs text.
7. Grading components, the pass rule, and the wrong-algorithm list.
8. Risks: especially real-data conflicts, ECG label ambiguity, runtime and context size,
   and anything two careful reviewers could disagree on.
