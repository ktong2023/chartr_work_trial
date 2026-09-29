# Confirmation batch results

Each batch ran once under its task's predeclared protocol and was scored by `qa/confirm_summary.py`. The batches are not
pooled.

| Batch | Task | Frozen commit | Headline |
|---|---|---|---|
| [`confirm-task3-0.3.1-20260928T232731Z`](confirm-task3-0.3.1-20260928T232731Z/TRIAGE.md) | Task 3 v0.3.1 | `19edc3b` | **5/10** |
| [`confirm-task4-0.4.1-20260928T235846Z`](confirm-task4-0.4.1-20260928T235846Z/TRIAGE.md) | Task 4 v0.4.1 | `19edc3b` | 1/10 |
| [`confirm-task4-0.4.2-20260929T050729Z`](confirm-task4-0.4.2-20260929T050729Z/TRIAGE.md) | Task 4 v0.4.2 (final) | `98a881a` | **3/10** |

Each folder has:
- `TRIAGE.md`: a classification of every failure;
- `DISPATCH.txt`: the dispatch commit and preflight output;
- `SUMMARY.txt`: the output of `qa/confirm_summary.py`, regenerated from the full batch;
- `RESULTS.json`: Task 3 only.

To regenerate `SUMMARY.txt` for the v0.4.1 batch, pass `--frozen 19edc3b`.

The full batch folders (trial logs, agent trajectories, snapshots; about 93 MB each) are on the `task3-pilot-results` and
`task4-pilot-results` branches, at `jobs/chartr/<batch>/`.
