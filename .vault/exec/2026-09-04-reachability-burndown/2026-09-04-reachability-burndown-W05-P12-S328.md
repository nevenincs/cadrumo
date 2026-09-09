---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:782610b1cb22cb519c3bbfc99c99b0d4484b12ad803aa0408eaa97265fd1ebdf'
step_id: 'S328'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the repository-wide hardcoded-literal census and its path exemptions

## Scope

- `literal inventory gate`
- `direct Sede browser and PDF behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_hardcoded_constants_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/outbound/aeat/sede/tests/test_playwright_wait_constants.py src/cadrumo/adapters/outbound/aeat/sede/tests/test_pdf_response_contract.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 279 unused symbols.
