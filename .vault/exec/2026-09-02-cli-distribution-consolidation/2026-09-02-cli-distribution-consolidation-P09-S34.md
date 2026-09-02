---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0206f5f5cd8c302170f336b40c8afef3264932f07ba391ccc85955cf095d89df'
step_id: 'S34'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Build every declared distribution from one command and refuse any file over the index cap

## Scope

- `justfile`

## Changes

- `A` `dev/packaging/distribution_cap.py`
- `A` `dev/packaging/tests/test_distribution_cap.py`
- `M` `justfile`
- `M` `.github/workflows/publish.yml`
- `verify:` `just packaging-distributions` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 dev/packaging/tests/test_distribution_cap.py` -> `pass`

## Notes

The publish workflow carried a bash copy of the index cap as the literal
`100000000`, which is the drifting duplicate `dev/packaging/_distribution_limits`
exists to prevent. The check now reaches that single declaration. It lives in its own
module rather than as a subcommand of the cohort builder because the publish job runs
before any development dependency is installed, and importing the cohort builder there
fails on its unresolved third-party imports; the new module imports only the standard
library and was exercised under a bare system interpreter to prove it.

All six distributions build and clear the cap: the two product distributions at 74.5 MB
and 59.6 MB, and the four corpus files between 76.2 MB and 77.5 MB. Measured on Windows
against the local interpreter rather than a hosted runner.

The immutable cohort builder refuses to run here at all, because it requires a clean
source snapshot and this worktree carries other contributors' work. Cohort-based
evidence needs a detached worktree at `HEAD`, which is how the remaining Phase `P09`
steps should obtain it.
