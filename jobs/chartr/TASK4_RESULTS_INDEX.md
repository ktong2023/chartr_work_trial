# Task 4 pilot and QA job artifacts

This branch holds the paid Task 4 pilot job artifacts. They stay off `main` because job folders are gitignored there.
The task code and its history are in `chartr_task4/README.md` on `main`. The pilot batches below are claude-opus-5 runs.
Each batch with pilot results has a `TRIAGE.md`, and some have rescored JSON files.

| Folder | What it is |
|---|---|
| `task4-0.4.0-1790626310` | **Final frozen v0.4.0 batch, 10 trials: 3/10** |
| `task4-0.3.5-1790617318` | v0.3.5, 10 trials: raw 1/10; retrospective 4/10 against the v0.3.6 key |
| `task4-0.3.4-1790613876` | v0.3.4, 5 trials: 1/5 |
| `task4-0.3.2-1790609695` | v0.3.2, 5 trials: 0/5 |
| `task4-0.3.0-1790576029` | v0.3.0, 5 trials: 0/5 |
| `task4-0.2.0-1790573334` | v0.2.0, 5 trials: 0/5 |
| `task4-0.1.1-1790560349` | v0.1.1, 5 trials: 1/5 |
| `task4-0.1.0-1790555298` | v0.1.0, 5 trials: raw 0/5; rescored 1/5 |
| `task4-0.1.0-1790554704` | **Invalid infrastructure batch:** 60 s tool timeout, every run ended at its first export |
| `task4-0.3.6-audit-2026-09-28` | Independent v0.3.6 audit: Harbor probes, counterexamples, scripts |
| `task4-*-qa-*` | Docker oracle / no-op / boundary / concurrency / 10-way scale checks for each version |
