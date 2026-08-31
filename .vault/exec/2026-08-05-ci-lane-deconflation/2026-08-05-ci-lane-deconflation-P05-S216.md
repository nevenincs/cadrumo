---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:3100546cc9c4b4790ffbe4a4fbad268a1fe6248376a4100194686fd45ec554e4'
step_id: 'S216'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in establishment.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/domain/iva/establishment.py`

## Changes

- `M` `src/cadrumo/domain/iva/establishment.py`
- `A` `src/cadrumo/domain/iva/country_vocabulary.py`
- `M` `src/cadrumo/domain/iva/tests/test_printed_country_name.py`
- `M` `src/cadrumo/domain/iva/tests/test_stated_country_code.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S216.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p05-s216-execution-self-review-audit.md`

## Notes

- Source commit `f8c4416febb4b17c2c6b97c7d61d0f31e661fd29` reduced `establishment.py` from 1,298 to 1,066 raw physical lines and added `country_vocabulary.py` at 254.
- Private vocabulary indexes have one direct sibling home; public establishment resolvers remain canonical, with no facade or re-export. AST review reported 34 definitions conserved and independent source review reported C/H/M/L 0.
- The executor reported clean Ruff, compile, and diff checks; literal transcripts are not retained, so these are qualified executor reports.
- Focused pytest is blocked before collection at root `conftest` import by external missing `cadrumo.tests._env_loader`; no test body ran and no pass is claimed.
