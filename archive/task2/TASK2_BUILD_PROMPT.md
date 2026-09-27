# Build brief: ChartR Task 2 — clinic-wide episode reconstruction

Read this fully before doing anything. **Phase 1 is a design proposal only.** Do not
implement until I approve it.

## Context

- Task 1 lives in `chartr_task/`. Read `HANDOFF.md`, `PROGRESS.md`,
  `chartr_task/README.md` and `chartr_task1_conceptual_framework_v0_1.md` to understand
  the architecture:
  - isolated agent container with a `clinic` CLI;
  - SQLite clinic sidecar with an audit log and read-only sources;
  - controller-collected frozen snapshot;
  - separate verifier;
  - custom Docker provider (`chartr_environment.py`);
  - direct Messages-API agent (`anthropic_agent.py`).
- Task 1 results show Opus reliably solves chart-by-chart puzzles: retractions,
  duplicates, outside treatment, date arithmetic, event chains, and rule induction. More
  of that is not new difficulty.
- The assignment: Opus should pass **2–7/10**, with failures that are the model's fault,
  not the environment's or grader's, and I must be able to show how I told them apart.

## Task 2 concept

The agent must build a **coherent clinic-wide history** of syphilis episodes from
synthetic records, where a record's meaning can depend on evidence elsewhere in the
dataset. Processing each patient independently should sometimes give the wrong answer.
A correct general algorithm should get full credit.

**Agent outputs, all submitted through the clinic interface:**
1. **Episode ledger.** One row per episode:
   - canonical patient ID and episode ID;
   - qualifying index test and index date;
   - stage;
   - distinct treatment events assigned to the episode;
   - adequacy, and treatment start date;
   - attributed site;
   - evidence record IDs.
2. **Q1:** the set of 2024 episodes with no adequate treatment started within 30 days of
   the index date.
3. **Q2:** for each site, the eligible early-syphilis episode set, the timely-treatment
   set (adequate treatment within 14 days), counts, and the rate.

4. **Q3:** "Site B's timely-treatment rate (from Q2) is lower than Site A's. Is the
   difference explained by patient mix, or does it persist?" Submit:
   - a conclusion category (`explained_by_patient_mix` / `persists` /
     `insufficient_data`);
   - the adjusted rate difference;
   - the patient characteristics adjusted for.

Q1, Q2 and Q3 must all be derivable from the ledger. The grader checks the ledger and
each answer separately.

### Q3 design: a comparison that stays correct under any defensible method

Q3 adds analytical judgment on top of reconstruction. It must be built so that **every
defensible analysis reaches the same conclusion and every tempting shortcut reaches a
different one**:

- **One hidden variable carries the whole gap.** Referral source (e.g., ED vs.
  clinic-referred) lowers the chance of timely treatment equally at every site, and
  Site B sees far more of those patients. Within each referral group the site gap is
  about 0, while the crude gap is large (e.g., about 20 points). Every other available
  characteristic (age, sex, insurance, stage, …) is balanced across sites, so adjusting
  for more or fewer of them, or using a different method, doesn't move the answer.
- **Build it with exact counts.** The generator must hit exact stratum counts *after*
  every mechanism is resolved: Q2's per-site numerators and denominators come from the
  same reconstructed episodes. Don't draw the counts randomly.
- **Tie it to the data.** Referral source is recorded inconsistently ("ED", "ER",
  "Emergency Dept", "triage", sometimes only on the encounter note), and reconstruction
  mistakes change which episodes are in the comparison. A model that parses naively, or
  reconstructs wrongly, should end up with a residual gap that lands in the wrong
  category.
- **Categories with a buffer, defined publicly:**
  - `explained_by_patient_mix` = adjusted difference within ±5 percentage points;
  - `persists` = 10 points or more;
  - 5–10 points is a buffer zone that is never a correct answer.

  Also define `insufficient_data` by a minimum per-stratum count. The true answer must
  sit far from every boundary. The public docs define the categories, thresholds and
  estimand (adjusted difference in timely-treatment rate). They must **not** say which
  variable matters or which method to use.
- **Robustness check before freezing:**
  - Run 10–15 defensible analyses (stratified or Mantel–Haenszel, standardization,
    logistic regression with average marginal effect, different balanced-covariate sets,
    different CI methods). **All** must land in `explained_by_patient_mix` with the
    estimate inside the graded band.
  - Run the tempting wrong analyses (see the wrong-pipeline list). **All** must land
    elsewhere.
  - Save this check as evidence for the write-up.

**Mechanisms to build in** (hypotheses, to be validated by pilots):

| Mechanism | Example |
|---|---|
| Ownership corrections across charts | A treatment event appears under patient A; an authorized correction elsewhere reassigns it to patient B, or an old patient ID maps to a new one |
| Notices that affect many records | A lab notice invalidates a specified batch of results; a later notice reinstates a documented subset |
| Treatment-to-episode assignment | A patient with more than one episode, imported duplicate treatment rows (one event, two rows by provenance), treatment that must be matched to the right episode |
| Corrections that cascade | An invalidated index test moves the index date to a later valid test, which changes the stage, treatment timing, the 14-day status, and the site's numerator or denominator |
| Sources with different meanings | One feed records administrations; another exports orders with later status changes. They must be normalized before combining. |

Include plenty of **plain control histories** that no mechanism touches. Keep
mechanisms connected: one notice or correction should affect several episodes across
different patients and sites.

## Top priorities

### 1. Test reasoning, not trivia or guessing
- Every hard case must be solvable from the documented tools and explicit evidence in
  the data. Every link (correction to target record, notice to batch, old ID to new ID)
  must be discoverable.
- Provide a **bulk export**, written to a file in the agent container, documented as
  complete. Cross-chart evidence must be reachable; per-patient reads alone must not be
  the only way in.
- No ambiguity with no way to resolve it. If two careful analysts could defensibly
  disagree, fix the rule or the data. Don't grade it.
- No obvious "twin" cases side by side in the evaluated dataset.

### 2. Public documents must be bare bones

Each sentence in `instruction.md`, `policy.md` and `tools.md` must be one of:
- (a) an interface fact (commands, schemas, fields, limits);
- (b) a definition needed for a unique answer (episode, the 90-day rule, adequacy, stage,
  site attribution, date semantics);
- (c) a general authority or precedence rule (e.g., "A correction record replaces the
  fields it names on the record it references").

**Not allowed:**
- warnings or hints ("watch for…", "note that X may appear under…");
- examples that mirror fixture cases;
- lists of the kinds of traps;
- restating the same rule in several files;
- anything explaining *why* a rule exists.

Describe record types and fields generically. Discovering that a relevant correction
or notice exists elsewhere is part of the test. Record text in the fixture must carry
only clinical or operational content: no record-ID citations in prose and no sentences
that exist to rule out wrong answers. (Task 1's 0.1.2 cleanup is the precedent.)

### 3. Grading that attributes failures
- Four graded layers:
  1. ledger reconstruction (membership, index, assignments);
  2. classification (adequacy, stage, site, timing);
  3. aggregation (Q1 set, Q2 counts and rates);
  4. analysis (Q3 category exact, adjusted difference within a declared band).

  Report diagnostics **per mechanism and per layer**.
- Also check Q3 for **consistency**: recompute a stratified adjusted difference from the
  agent's *own* submitted ledger and adjustment variables. That separates "wrong
  reconstruction fed a correct analysis" from "correct ledger, wrong analysis."
- Grade structured fields exactly. For evidence, check only that the referenced IDs
  exist and belong to the right patient and episode; don't judge whether they're
  sufficient in v0.1.
- Errors are not independent: one bug can hit many rows. Propose a pass rule; my default
  is "ledger exact on all mechanism histories, Q1 exact, Q2 exact," with any tolerance
  on control histories justified explicitly.
- Invalid runs (infrastructure or API faults) are classified as invalid, never scored 0,
  as in Task 1.

### 4. Independent validation
- Private generator; deterministic reference solution that uses only the public
  interface; private grader.
- An **independent second reconstruction** written from the public docs only, not
  sharing rule code with the generator or grader. Anywhere they disagree marks an
  ambiguity to fix.
- **Deliberately wrong pipelines** that must fail, each on the intended mechanism:
  - processes each patient independently;
  - ignores notices;
  - applies a notice without its later reinstatement;
  - doesn't merge IDs;
  - double-counts duplicate provenance;
  - patches the index date without recomputing what depends on it;
  - mixes orders and administrations;
  - Q3: reports the crude site gap without adjustment;
  - Q3: adjusts only for the balanced characteristics;
  - Q3: parses only the clean "ED" referral values;
  - Q3: runs the analysis on an episode set with duplicates or invalidated episodes left in.
- Manually audited example histories documented privately.
- Private variants (renamed IDs, shuffled rows, reworded notes) to check that difficulty
  survives surface changes.

## Reuse and constraints
- Create a separate task directory (e.g. `chartr_task2/`) with its own fixture,
  instruction, docs, reference, grader, baseline and version (`0.1.0`).
- Reuse the service, CLI pattern, audit log, attestation, trusted collection, separate
  verifier, provider and agent adapter wherever possible.
- **Do not change Task 1 behavior.** Task 1's offline tests, oracle and no-op must
  still pass afterwards.
- New operations:
  - bulk export (written to a file, raw records only, no derived eligibility or
    completion flags);
  - submit and read-back of the ledger and answers.

  Validate format only, never analytical correctness. Give submissions their own body
  size limit (Task 1's is 16 KiB).
- Run settings for this task: raise `max_tokens` well above 2048 (the adapter ends a run
  on truncation) and set `max_tool_chars` and the time budget from healthy pilot
  runs. Budgets must never be a source of difficulty. Preinstall pinned
  pandas/numpy in the agent image; the agent has no network access.
- Start with a **small bounded fixture: 20–30 histories** plus controls. Do not build a
  large generator until pilots show which mechanisms actually cause reasoning failures.
- Do not upgrade `.venv` or the pinned dependencies. Do not run anything that calls the
  Anthropic API without asking me first. Oracle, no-op and wrong-pipeline runs are fine;
  write them to new directories under `jobs/`.

## Phase 1 deliverable (stop after this)

Send me a design proposal in chat containing:
1. The public definitions you'd write (episode, 90-day rule, adequacy, stage, site
   attribution, date semantics, correction/notice authority), each checked against the
   bare-bones rules above.
2. The record types and export/submission schemas.
3. A sketch of the 20–30 histories: which mechanisms each exercises, how they connect,
   and which are controls.
4. The Q3 design:
   - target stratum counts;
   - how exact counts survive the mechanisms;
   - category thresholds and the graded band;
   - the minimum-count rule for `insufficient_data`;
   - the defensible and wrong analyses for the robustness check.
5. The grading layers, per-mechanism diagnostics and proposed pass rule. State whether Q3
   is required for a pass.
6. The list of wrong pipelines and what each should fail.
7. The changes needed to shared code, and how you'll prove Task 1 is unaffected.
8. Risks and open questions, especially any rule where you see room for defensible
   disagreement.
