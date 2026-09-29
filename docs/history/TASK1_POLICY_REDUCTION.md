# Brief: reduce Task 1's public documents to the bare minimum

Applies to the current Task 1 (the checkpoint-reconciliation task; `chartr_graph/` or its
successor). **Phase 1 is a proposal only.** Do not change files until I approve it.

## Goal

The model should see only what it strictly needs. Every determination should rest on one
of two things:

1. **The CDC standard of care,** inferred by the model from its own clinical knowledge.
2. **What is written in the patient's chart,** at the point where it's used.

The policy file should almost disappear. The rules shouldn't be listed for the model;
it should have to recognize and apply them.

## Steps

### 1. Classify every sentence in `instruction.md`, `policy.md` and `tools.md`

| Class | Meaning | Action |
|---|---|---|
| **CDC** | Covered by published guidance | **Delete** from the policy. Replace with one line naming the source (below). |
| **Chart** | A clinic-specific rule tied to particular records (schedules, windows, separations, branch conditions, pause effects, who corrected what) | **Move into the chart**, in natural clinical language on the relevant records |
| **Interface** | Commands, schemas, field vocabularies, limits, local FHIR extensions | **Keep** in `tools.md`, minimal |
| **Hint** | Previews a trap, explains why, restates another rule, or names a distractor | **Delete** |
| **Construct** | A global rule that is neither clinical nor chartable (e.g., "maximize the joint specimen assignment") | **Flag for me.** Either justify it as one interface-level line, or redesign or drop the mechanism |

**CDC ground truth covers:**
- regimens and treatment adequacy;
- the dose-gap restart rule, including the stricter rule in pregnancy;
- follow-up serology timing (6/12 months for P&S; 6/12/24 months for latent);
- fourfold titer change, treatment failure and reinfection;
- doxycycline treatment (100 mg twice daily × 14 days) vs. doxy-PEP (200 mg single dose);
- staging per the CDC/CSTE case definitions.

**Rules with no external source must come from the chart,** for example:
- the plan order states its own follow-up schedule, acceptance window, specimen
  separation and any conditional branch ("repeat RPR at 3 and 6 months if titer rises
  fourfold");
- a hold order states what it pauses and when it ends;
- a lab correction comes from a lab author;
- a clinician note records its own changes.

### 2. The resulting public surface

- **`instruction.md`:** the task goal, the evaluation time, "saved determinations are
  graded," pointers to the docs and the CLI. Nothing else.
- **`policy.md`:** only a few lines:
  - "Clinical determinations follow the CDC 2021 STI Treatment Guidelines (and the 2024
    doxy-PEP guidelines). Clinic-specific instructions in the chart govern where they
    apply."
  - Definitions of the output statuses, one line each (e.g., `unclear` = cannot be
    established from the records).
  - Any **Construct** rules I approve.
- **`tools.md`:** interface facts and local extensions only. Remove explanations of
  standard FHIR fields a FHIR-literate reader already knows.

No warnings, no examples mirroring fixture cases, no phrase tables, no repeated rules,
no explanations of why a rule exists.

### 3. Rewrite the fixture accordingly

- Chart text carries its own clinic-specific instructions in realistic, varied wording,
  not templated clauses a parser can split on.
- **Avoid CDC's hedged zones,** or have the chart settle them. CDC says a 10–14-day dose
  gap "might be acceptable" outside pregnancy. Either use gaps of ≤9 or ≥15 days, or have
  the order state the clinic's rule ("restart if more than 14 days"). The same goes for
  follow-up timing: CDC gives month points but no window, so the window must be in the
  plan order.
- Record text carries only clinical or operational content: no record-ID citations, and no
  sentences that exist to rule out wrong answers.

### 4. Validate

- **The two-experts test for every case:** an independent reviewer given only the chart,
  the minimal public docs and the CDC guidance must reach the authored answer. Use an
  independent solver or reviewer that never sees the private answers. Any disagreement
  means fix or cut the case. It is not a hard case.
- Regenerate expected answers only where moving rules into the chart genuinely changes
  them, and list every change.
- Wrong-algorithm controls still fail on their target cases. Oracle 1, no-op 0.
- New task version. Keep the previous version and all job evidence. No Anthropic API runs
  without my approval. Don't read `.env`. Don't upgrade pinned dependencies.

## Phase 1 deliverable (in chat, then stop)

1. The classification table: every current public sentence → CDC / Chart / Interface /
   Hint / Construct, and the action for each.
2. The full proposed text of the new `instruction.md`, `policy.md` and `tools.md`.
3. Two or three examples of chart records rewritten to carry their own rules.
4. Every **Construct** rule, with your recommendation to keep, redesign or drop it.
5. Any cases that touch CDC's hedged zones, and how each is settled.
6. The expected-answer changes, and the risks where two careful reviewers could still
   disagree.
