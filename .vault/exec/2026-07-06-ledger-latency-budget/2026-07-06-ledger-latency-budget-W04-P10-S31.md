---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S31'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Replace the before-validator id derivation path with an after-validator invariant

## Scope

- `src/aeat/domain/transactions/_models.py`

## Description

- Attempt semantic grounding for the transaction id validator hot path; record the unavailable service and timed-out fallback.
- Confirm persisted transaction loads use `Envelope[Transaction].model_validate_json(record.payload)`.
- Add a validated-data default factory that derives missing `transaction_id` from the already validated `raw` field.
- Move `raw` before `transaction_id` so the default factory can consume pydantic-core validated raw data.
- Replace the `mode="before"` id derivation/coercion validator with a `mode="after"` invariant that rejects tampered ids.

## Outcome
- `src/aeat/domain/transactions/_models.py` no longer parses/coerces the entire transaction payload in `_enforce_derived_transaction_id` before pydantic-core validation.
- Missing transaction ids are still derived for normal construction paths.
- Explicit mismatched transaction ids are rejected after raw validation.
- `uv run ruff check src/aeat/domain/transactions/_models.py` passed.
- Focused domain model tests for id stability and JSON roundtrips passed.
- A direct tampered-id probe passed.
- The encrypted transaction repository roundtrip test passed.

## Notes

- `uv run vaultspec-rag search "Transaction _enforce_derived_transaction_id before validator RawTransaction validation manual coercion" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the transaction model, service, tests, and repository load path.
- The first inline Python tamper probe had shell quoting syntax errors; the stdin version passed.
- The first repository smoke pytest node name was stale; the current encrypted roundtrip test was located and passed.
- Obsolete manual coercion helpers remain for S32 removal.
