# Design principles to integrate (Tasks 1 and 3)

Sources:
- Anthropic, "Demystifying evals for AI agents":
  https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Mechanize, "What working here is like":
  https://www.mechanize.work/what-working-here-is-like/

## The core diagnosis

Deterministic grading pushed us to write explicit protocols. Explicit protocols over
regular records turn each task into a programming exercise, and Opus writes a correct
solver every time (5/5 on both recent probes). Mechanize names this directly: procedural
tests "force prompts to be overly prescriptive." The difficulty ceiling comes from how
prescriptive we've been, not from the clinical content. The fix is fewer written rules,
not more.

## What to change

### 1. Replace house policy with the standard of care
- Delete any rule a competent clinician would already agree on without it. Ground truth
  becomes established guidance (e.g., CDC STI treatment guidelines), not our own
  protocol text.
- **Keep only local conventions an outsider couldn't know:**
  - the evaluation date;
  - the output schema and interface;
  - clinic-specific authority (who can sign off);
  - site attribution.
- **Public docs** = task goal + tool/interface facts + those local conventions. No
  protocol tables that restate clinical practice, and no warnings or hints.

### 2. Choose cases that need judgment, but have one defensible answer
- **The test for every case:** two domain experts reading the chart would independently
  reach the same verdict (Anthropic's bar). If they wouldn't, cut the case. Ambiguity
  makes failures unfair, not hard; Task 1 already showed this.
- **Prefer cases where the guidance is clear but applying it takes reasoning over messy
  notes.** Examples:
  - dose-interval tolerance that differs in pregnancy;
  - whether an undocumented stage actually changes the answer, given the regimen used;
  - doxycycline as treatment vs. prophylaxis;
  - whether a referenced outside record or pending result is decision-relevant.
- **Use realistic, varied clinical text,** not regular templated amendments a parser
  can split on.

### 3. Test both directions
- Include cases where the behavior should happen and cases where it shouldn't (flag vs.
  don't flag, conclude vs. abstain), so neither over- nor under-triggering pays off.
- Task 3's "undeterminable" vs. "determinable despite gaps" split does this; keep it.
  Task 1 should likewise mix real issues with complex-looking non-issues.

### 4. Several sources of difficulty in one task
- Mechanize: tasks should have "multiple different sources of difficulty"; take the
  planned task and "make it ten times harder." That means more kinds of difficulty
  at once, not a longer rulebook.
- For us, combine:
  - search and triage (unknown number and location of issues);
  - clinical inference from standard of care;
  - reading messy text;
  - calibration (knowing when not to conclude).

### 5. Grade outcomes, not paths
- Grade the final saved state; never grade tool-call sequences or exact citation lists.
- Accept every valid route to the right answer, and give partial-credit diagnostics per
  dimension even with a binary pass rule.
- Avoid graders that check things the model had no way of knowing (Mechanize's
  "query parameter name" example).

### 6. Validate cases independently before any paid run
- For each case, an independent reviewer given only the chart and the public docs
  (plus the standard-of-care source) must reach the authored answer. Use me plus a
  second model. Where they disagree, fix or cut the case.
- Keep the deliberately wrong algorithms (never abstain, always abstain, flag
  everything, latest source wins, …), and confirm each fails on its target cases.

### 7. Read transcripts and explain every failure
- For each pilot, write down *why* each miss happened, from the transcript. Every
  failure should look fair: a competent clinician would have caught it.
- Anything that looks like a task or grader defect gets fixed and versioned, not
  counted. This is the "failures are the model's fault" evidence ChartR asked for.

### 8. Treat saturation as a signal
- A task at 10/10 gives no signal. The 5/5 probes mean it's time to change *what* we
  measure (less prescription, more inference), not add more rules of the same kind.

## Applying this to each task

- **Task 1:** strip the policy back to local conventions. Let the treatment-review
  determinations (unresolved concern, conflicting plans, resolution) rest on clinical
  standard of care. Add complex-looking non-issues and cases where the answer depends
  on clinical inference rather than a written rule. Re-run the two-experts check on
  every case.
- **Task 3:** keep the cohort audit with calibrated abstention. Define issue types by
  their clinical meaning rather than protocol tables. Publish only the output vocabulary
  (including missing-evidence codes) and local conventions. Make the
  "determinable despite gaps" and "undeterminable" cases depend on standard-of-care
  reasoning over realistic notes.
