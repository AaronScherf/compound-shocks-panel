# 001: Step runner

Date: 2026-10-31. Status: accepted (spike passed). Owner of the decision: Claude, reviewed by the owner.

## Decision

Use **doit** (0.37.0) to run the pipeline's step graph, behind one command:
`python -m compound_shocks reproduce --instance NAME`. Users never call doit directly, so the runner can be
replaced without changing the command.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| doit | Python-native, cross-platform, skips unchanged work, light | Smaller community; dynamic dependencies need `calc_dep` |
| Make | Universal | Weak on Windows, which our non-technical users may use |
| Snakemake | Strong for large or cluster pipelines | Heavier; native Windows behavior unconfirmed |
| DVC | Data versioning with Git | A second tool; solves data tracking more than step order |

## Evidence from the spike

The skeleton reads each role directory, aggregates, and fuses (`src/compound_shocks/pipeline.py`).
`tests/test_reproduce_skeleton.py` checks six behaviours:

- The skeleton runs on a fixture instance and writes `panel.csv`.
- A second run with unchanged inputs runs no steps (checked through a log each action appends to).
- Changing one role's file bytes reruns that role's read, then aggregate and fuse, and not the other role's read.
- The command works with an empty `PATH`, so it never shells out to `make`.
- A missing instance and a role with no files give a plain one-line error naming the problem.

Results: all six pass on Windows 11 locally, and the CI matrix passed on both `ubuntu-latest` and `windows-latest`
(GitHub Actions run 41247439946, https://github.com/AaronScherf/compound-shocks-panel/actions/runs/41247439946).

## Limits and what we did not test

- The skeleton has a static graph. Data-dependent steps (for example a satellite query driven by conflict coordinates)
  need doit's `calc_dep` or a generated task list; the pilot has no such step, so this is untested.
- Roles are taken from the subfolders of `data/raw/` in the skeleton; Task 10 reads them from the instance config.
- doit's default change detection is a file checksum, so an edit that leaves bytes identical does not rerun a step. That is the intended behaviour.

## Fallback

If doit later fails on a platform or cannot express a needed step, replace `cli._reproduce` with a small runner that
takes the same `pipeline.tasks()` dicts (`name`, `file_dep`, `targets`, `actions`) and skips a step when its
input hashes match. The task definitions do not change.
