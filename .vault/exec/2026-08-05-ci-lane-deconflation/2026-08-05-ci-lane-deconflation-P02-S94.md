---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ff393f570fba8742b6f6067361b4fa9663de3b165b8f44b5d32ebd518968ddce'
step_id: 'S94'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution: `P02 S94 remediation attestation`

## Scope

- `src/cadrumo/domain/calculations/registry/errors.py`
- `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`
- `src/cadrumo/locales/{en,es,ca,hu}/errors.yml`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/errors.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_temporal.py`
- `M` `src/cadrumo/locales/en/errors.yml`
- `M` `src/cadrumo/locales/es/errors.yml`
- `M` `src/cadrumo/locales/ca/errors.yml`
- `M` `src/cadrumo/locales/hu/errors.yml`
- `M` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S94.md`
- `verify:` `pytest -q -n0 test_temporal.py::{M390 fallback, localized renderer}` -> `5 passed in 36.58s`
- `verify:` `py_compile errors.py test_temporal.py` -> `pass`
- `verify:` `ruff check errors.py test_temporal.py` -> `pass`
- `verify:` `python -m dev.locales audit` -> `ca.yml/en.yml/es.yml/hu.yml: ok`
- `verify:` scoped `git diff --check` -> `pass`

## Notes

Immutable implementation provenance is `be1ad83404`; the earlier structural-regression hunk is immutable commit `565f31c494`; neither supplies recoverable historical literal pytest output. This successor remedies the localized-renderer omission identified in review: the canonical translated refusal now renders the structured `available_revision_ids` context in every shipped locale, with fresh focused evidence recorded above.
