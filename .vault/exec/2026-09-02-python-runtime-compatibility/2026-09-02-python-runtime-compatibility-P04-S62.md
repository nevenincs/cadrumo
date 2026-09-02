---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:b16de55bc7573fe07d36e200bc5f2eabad3fc34ad52bac249c026ec525bfa050'
step_id: 'S62'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Scope hash enforcement without rejecting locally built cohort artifacts

## Scope

- `dev/packaging/release_cohort.py`

## Changes

- `M` `dev/packaging/python_cohort.py`
- `verify:` `uv run --no-sync pytest -q -p no:randomly dev/packaging/tests/test_python_cohort_digest_assertions.py dev/packaging/tests/test_release_cohort.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/packaging/python_cohort.py` -> `pass`
