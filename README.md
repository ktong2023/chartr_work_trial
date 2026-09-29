# ChartR agent tasks

This repo has two long-horizon clinical-review tasks for evaluating AI agents, built for [Harbor](https://github.com/laude-institute/harbor).

**What the agent does in each task:**
- It works inside a simulated clinic system through a command-line tool.
- It reads patient records, applies a written clinic policy, and saves structured review items.

**How grading works:**
- A private, deterministic grader compares the saved items with a hand-authored answer key.
- A run passes only if every graded item and field is right.

**Target difficulty:** Claude Opus 5 should pass **2–7 of 10** attempts. Every failure should be a genuine reasoning or
reading error, not a task or grader defect.

## Final results

Each task was confirmed with one ten-attempt batch. The protocol for each batch was fixed and committed before the batch
ran; it covers the frozen files, the exact command, the budgets and the counting rules.

| Task | Version | Headline | Protocol | Triage |
|---|---|---|---|---|
| [Task 3: cohort audit with calibrated abstention](chartr_task3/README.md) | 0.3.1 | **5/10** | [protocol](chartr_task3/README.md#final-confirmation-protocol-fixed-september-28-2026-before-any-confirmation-trial) | [triage](results/confirm-task3-0.3.1-20260928T232731Z/TRIAGE.md) |
| [Task 4: cardiology population review with raw ECGs](chartr_task4/README.md) | 0.4.2 | **3/10** | [protocol](chartr_task4/README.md#final-confirmation-protocol-v042-fixed-september-29-2026-before-any-v042-trial) | [triage](results/confirm-task4-0.4.2-20260929T050729Z/TRIAGE.md) |

- **Validity:** every batch had 10 valid attempts, with no reruns and no budget failures. Every trial's provenance matched
  its frozen commit.
- **Task 4 history:**
  - v0.4.1 scored [1/10](results/confirm-task4-0.4.1-20260928T235846Z/TRIAGE.md), below target. That result stands for
    that version.
  - v0.4.2 is an announced calibration; its changes are listed in the task README.
- **More detail:**
  - [`results/`](results/README.md) has the per-batch summaries.
  - The `task3-pilot-results` and `task4-pilot-results` branches hold the full trial logs of every pilot and confirmation
    batch.

## The tasks

**Task 3 — `chartr/cohort-audit`** ([`chartr_task3/`](chartr_task3/README.md)).
- The agent audits the syphilis care of a synthetic 200-patient cohort against the CDC 2021 STI guidelines.
- It also answers review requests.
- It must abstain with a stated reason (`cannot_determine`) where the records genuinely do not settle a question. Examples:
  cross-chart specimen identity conflicts, or tests still pending.
- Difficulty comes from follow-up windows that chain across episodes and from calibrated abstention.

**Task 4 — `chartr/cardiology-population-review`** ([`chartr_task4/`](chartr_task4/README.md)).
- The data is a 100-patient population built on the real MIMIC-IV Clinical Database Demo (FHIR) and MIMIC-IV-ECG Demo, with
  a synthetic outpatient layer.
- The agent flags issues in four areas:
  - anticoagulation, including AF documented only in notes or charting;
  - QT safety on watch-list drugs;
  - document-driven follow-up;
  - contradictions.
- It also interprets every living patient's most recent raw 12-lead ECG (500 Hz WFDB): rhythm, rate, intervals, axis,
  conduction, and changes from the prior ECG.
- ECG answers are graded against where three independent readers agree.

## Repository layout

| Path | Contents |
|---|---|
| `chartr_task3/`, `chartr_task4/` | The tasks, in Harbor's layout: `instruction.md`, `task.toml`, `environment/`, `tests/` (grader and key), `solution/` (reference) |
| `anthropic_agent.py` | Direct Anthropic Messages API agent adapter (0.4.0) used for every batch |
| `chartr_environment.py`, `chartr_job.yaml` | Harbor environment provider and job config |
| `qa/` | Private build scripts, answer-key generation, test suites, preflights and `confirm_summary.py` (protocol scoring) |
| `results/` | Summaries and triage of the three confirmation batches |
| `docs/` | Design principles, audits, release validation and the build history ([index](docs/README.md)) |
| `archive/` | Earlier task prototypes and probes, kept for reference ([index](archive/README.md)) |

The evaluated files are `chartr_task3/`, `chartr_task4/`, `anthropic_agent.py`, `chartr_environment.py`, `chartr_job.yaml`
and `requirements.lock.txt`. They stay at these paths because the protocols' frozen-file checks diff them against the frozen
commits.

## Running

Set up a fresh environment from `requirements.lock.txt`: Harbor 0.23.0 and anthropic 1.8.0. You need Docker with at least
10 CPUs and 8 GB, and an `.env` file with the API key.

Each task README has the exact preflight, batch command and scoring steps. In outline:

```bash
python3 qa/task4_preflight.py 0.4.2
caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=300 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak tool_timeout_sec=900 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$PWD/jobs/chartr/<dir>"
python3 qa/confirm_summary.py chartr_task4 jobs/chartr/<dir>
```

Offline test suites need no API key:

```bash
.venv/bin/python -m unittest qa.test_task3 qa.test_task4 qa.test_preflight qa.test_adapter
```

## Data and licence

- Task 4 uses the MIMIC-IV Clinical Database Demo on FHIR v2.1.0 and the MIMIC-IV-ECG Demo v0.1 (PhysioNet, Open Data
  Commons Open Database License v1.0).
  - Both are fetched at image build time and checksum-verified against pinned hashes.
  - They are re-dated and extended with synthetic records, and are not for clinical use.
- Task 3's patients are entirely synthetic.
