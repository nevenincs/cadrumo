---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:e4e5904f8b9d32d08f1e8669f033142e09c199c54e065efdfc641cd64b05b8d9'
step_id: 'S36'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# Block direct governed-directory reads and unregistered loaders

## Scope

- `dev/quality`

## Changes

- `A` `dev/quality/tests/test_governed_fact_runtime_reads.py`
- `verify:` `uv run --no-sync ruff check dev/quality/tests/test_governed_fact_runtime_reads.py` -> `pass`
- `verify:` `uv run --no-sync pytest -n 0 dev/quality/tests/test_governed_fact_runtime_reads.py` -> `pass`

## Notes

- The only raw IVA legal-table reads permitted are ledger-derived, exact-reader exceptions pending S81-S85; country vocabulary is technical and authority configuration is path wiring rather than a read.
