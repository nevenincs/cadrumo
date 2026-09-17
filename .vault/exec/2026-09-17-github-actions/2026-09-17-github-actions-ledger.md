---
tags:
  - '#exec'
  - '#github-actions'
date: '2026-09-17'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:4f3d73e125642b97f2f0bcdc518042489f95247421a35fc0e38439286ad21d1d'
related:
  - "[[2026-09-17-github-actions-plan]]"
---

# `github-actions` ledger

## Changes

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
- `S20` `M` `.github/workflows/release-please.yml`
- `S20` `M` `dev/packaging/cohort_manifest.py`
- `S20` `M` `dev/packaging/release_cohort.py`
- `S20` `M` `dev/packaging/tests/test_release_cohort.py`
- `S20` `verify:` `dev.actionlint` -> `pass`
- `S20` `by:` `ci-fix`

## Notes

- `S20` phase-close review fixes: scoped exclusions, sigpipe, prove commit binding, docs gating, release-please permissions
