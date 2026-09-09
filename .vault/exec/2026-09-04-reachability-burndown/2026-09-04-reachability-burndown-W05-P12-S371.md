---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a11933b0fafa2a2316c5356b5ae2f5a02eaebbddaea6aa78a7ac9292cd223549'
step_id: 'S371'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unused Modelo record-catalogue query Protocol and its query-only type imports.

## Scope

- `domain Modelo repository protocols`
- `filing-record repository roundtrip tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/domain/modelos/protocols.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/modelos/protocols.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/domain/modelos/tests/test_filing_record_repository_roundtrip.py -q` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`

## Notes

The broader `src/cadrumo/application/modelo/tests/test_modelo_work_review.py` suite remains red in its divergent-registry-coordinate case because the fixture now violates the calculation repository's parent-coordinate guard before review begins; this step did not alter that repository or fixture.
