---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S32'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Remove obsolete manual transaction coercion helpers after callers are reconciled

## Scope

- `src/aeat/domain/transactions/_models.py`

## Description

- Attempt semantic grounding for obsolete transaction coercion helpers; record the unavailable service and timed-out fallback.
- Confirm the old helper names are now referenced only by their own definitions.
- Remove `_json_default`, `_coerce_raw_transaction`, transaction-specific enum/decimal/temporal/string/collection coercion helpers, and their private constants.
- Remove the now-unused `ValidationError` import.
- Keep shared helpers used by other transaction submodels.

## Outcome
- `src/aeat/domain/transactions/_models.py` no longer carries the manual transaction coercion path formerly used by the before-validator.
- `uv run ruff check src/aeat/domain/transactions/_models.py` passed.
- Focused domain model tests and the encrypted repository roundtrip smoke test passed.
- `rg` confirmed the removed helper names no longer exist in `_models.py`.

## Notes

- `uv run vaultspec-rag search "obsolete manual transaction coercion helpers after validator remove _coerce_raw_transaction" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct `rg` references and source reads.
