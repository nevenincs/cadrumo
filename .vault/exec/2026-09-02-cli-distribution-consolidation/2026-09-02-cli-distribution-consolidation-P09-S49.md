---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:88f14f299fbcd310981a4557a7dc385730d78094e907cb5c6b311ccd54279718'
step_id: 'S49'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Remove the repeated passes the cohort build makes over artifacts it has already produced

## Scope

- `dev/packaging/python_cohort.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `M` `dev/packaging/runtime_wheelhouse.py`
- `M` `dev/packaging/release_cohort.py`
- `M` `dev/packaging/tests/test_python_cohort.py`
- `M` `dev/packaging/tests/test_release_cohort.py`
- `M` `dev/packaging/tests/test_installed_oracles.py`
- `M` `packaging/scoop/tests/test_scoop_generate.py`
- `M` `packaging/homebrew/tests/test_homebrew_generate.py`

## Scope

- `dev/packaging/python_cohort.py`

## Changes
