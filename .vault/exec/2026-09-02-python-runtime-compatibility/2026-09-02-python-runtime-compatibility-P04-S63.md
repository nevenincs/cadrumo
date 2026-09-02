---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:1b72f67d9e0f5e4b7df25d13f500f73b2f8ca4ece5fb30cddd3951aec81848ec'
step_id: 'S63'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Prove clean cohort construction accepts digest-bound local wheels

## Scope

- `dev/packaging/tests/test_release_cohort.py`

## Changes

- `M` `dev/packaging/tests/test_release_cohort.py`
- `verify:` `uv run --no-sync pytest -q -p no:randomly dev/packaging/tests/test_release_cohort.py dev/packaging/tests/test_python_cohort_digest_assertions.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/packaging/python_cohort.py dev/packaging/tests/test_release_cohort.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.packaging.release_cohort verify --cohort-dir var/release-cohort-pycompat-final` -> `pass`
- `verify:` `uv run --no-sync python -c \"import json; from pathlib import Path; p=Path('var/python-runtime-compatibility'); files=[p/'final-cp313'/'binary'/'evidence.json',p/'final-cp314'/'binary'/'evidence.json',p/'final-cp315-next'/'binary'/'evidence.json']; e=[json.loads(f.read_text()) for f in files]; assert [(x['runtime']['python'],x['status'],x['dependency']['status']) for x in e]==[('3.13.14','passed','resolved'),('3.14.6','passed','resolved'),('3.15.0b4','failed','missing-wheel')]; print('binary runtime evidence: pass')\"` -> `pass`

## Notes

- Real clean cohort build completed at source commit `10154f14aefd237ea7163940fb6bcfc1e96b95f3` with the exact CPython `3.13.11` builder and cohort verification passed.
- Binary evidence passed with resolved dependencies on CPython `3.13.14` and `3.14.6`; advisory CPython `3.15.0b4` recorded the expected attributable `missing-wheel` failure for PyYAML rather than a skip.
