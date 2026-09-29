# Archive

These are earlier task prototypes and probes from building Tasks 3 and 4. They're kept for reference only. None is part of
an evaluated task image, and nothing on the final tasks imports them.

| Path | What it was |
|---|---|
| `early_tasks/chartr_task/` | Task 1, `chartr/treatment-review` v0.5.2: the original review-queue task. The case files and conceptual framework are in [`docs/design/`](../docs/design/) |
| `early_tasks/chartr_soc/` | `chartr/standard-of-care` v0.1.0: an episode follow-up determination prototype |
| `early_tasks/chartr_proto/` | `chartr/followup-induction` v0.1.1: a follow-up induction prototype |
| `early_tasks/chartr_probe/` | `chartr/dependent-history` v0.1.0: a dependent-history difficulty probe |
| `early_tasks/chartr_graph/` | `chartr/interacting-requirements` v0.1.0: an interacting-requirements probe |
| `early_tasks/chartr_notes/` | `chartr/messy-notes` v0.1.0: a messy-notes probe |
| `early_tasks/chartr_relevance/`, `early_tasks/chartr_relevance-0.1.0/` | `chartr/relevance` v0.2.0 and v0.1.0: relevance probes |
| `early_tasks/qa/` | Build scripts and test suites for the tasks above |
| `task2/` | Task 2: a design direction that was superseded and never built |

What each probe measured, and why the design moved on, is recorded in [`docs/history/PROGRESS.md`](../docs/history/PROGRESS.md).

The scripts in `early_tasks/qa/` expect their original locations at the repository root. To run one, check out the
`pre-cleanup` tag.
