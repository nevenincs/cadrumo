---
tags:
  - '#exec'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:98bd28de60d621629b19892401eeb798ddf9d498d8723bad7f09c955cba9bc4e'
related:
  - "[[2026-09-17-github-actions-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `github-actions` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S12` `A` `dev/ci/change_scope.py`
- `S12` `A` `dev/ci/tests/test_change_scope.py`
- `S12` `M` `pyproject.toml`
- `S12` `verify:` `pytest dev/ci/tests/test_change_scope.py` -> `pass`
- `S12` `by:` `ci-scope`
- `S01` `A` `.github/actions/setup/action.yml`
- `S01` `verify:` `just check-workflows` -> `pass`
- `S01` `by:` `ci-setup`
- `S02` `M` `justfile`
- `S02` `verify:` `just --list` -> `pass`
- `S02` `by:` `ci-setup`
- `S03` `A` `.github/workflows/merge-gate.yml`
- `S03` `verify:` `just check-workflows` -> `pass`
- `S03` `by:` `ci-gate`
- `S16` `A` `.github/workflows/release.yml`
- `S16` `verify:` `just check-workflows` -> `pass`
- `S16` `by:` `ci-release`
- `S17` `M` `dev/packaging/campaign.py`
- `S17` `M` `dev/packaging/tests/test_campaign.py`
- `S17` `verify:` `pytest dev/packaging/tests/test_campaign.py` -> `pass`
- `S17` `by:` `ci-release`
- `S18` `A` `dev/release/pypi_publication_state.py`
- `S18` `A` `dev/release/tests/test_pypi_publication_state.py`
- `S18` `M` `dev/packaging/release_pointer_guard.py`
- `S18` `M` `dev/packaging/tests/test_release_pointer_guard.py`
- `S18` `verify:` `pytest dev/release/tests/test_pypi_publication_state.py dev/packaging/tests/test_release_pointer_guard.py` -> `pass`
- `S18` `by:` `ci-release`
- `S05` `M` `.github/workflows/release-please.yml`
- `S05` `verify:` `just check-workflows` -> `pass`
- `S06` `D` `.github/workflows/`
- `S06` `verify:` `dev.actionlint` -> `pass`
- `S06` `by:` `ci-retire`
- `S19` `M` `dev/ci/runner_queue_watchdog.py`
- `S19` `M` `dev/ci_contract.py`
- `S19` `M` `.github/ci-contract-allow.txt`
- `S19` `verify:` `dev.ci_contract` -> `pass`
- `S19` `by:` `ci-retire`
- `S20` `M` `dev/ci/tests/`
- `S20` `M` `dev/ci/lane_reachability.py`
- `S20` `M` `dev/test_runs/lanes.py`
- `S20` `M` `dev/tests/test_lane_reachability.py`
- `S20` `M` `src/cadrumo/tests/test_release_config.py`
- `S20` `M` `justfile`
- `S20` `M` `.github/workflows/release.yml`
- `S20` `M` `.github/workflows/merge-gate.yml`
- `S20` `verify:` `pytest dev/tests/test_lane_reachability.py src/cadrumo/tests/test_release_config.py` -> `pass`
- `S20` `by:` `ci-retire`
- `S21` `M` `.github/ci-control-plane.md`
- `S21` `M` `docs/_release_checklist.yaml`
- `S21` `M` `RELEASING.md`
- `S21` `M` `dev/runners/README.md`
- `S21` `by:` `ci-docs`

