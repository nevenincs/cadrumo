---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a93d86ced58d2b53cb4514e961f05a07a95e31c2b01386b42f79117aa007ecf7'
step_id: 'S26'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---
# Enroll the compatibility workflow in change-class and fork-safety invariants

## Scope

- `dev/ci/tests/test_change_class_tiers.py`

## Changes

- `M` `dev/ci/tests/test_change_class_tiers.py`
- `verify:` `uv run --no-sync pytest -q -o addopts='' dev/ci/tests/test_change_class_tiers.py; uv run --no-sync ruff check dev/ci/tests/test_change_class_tiers.py` -> `pass`

