---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:9f9cc6b53df0925009fd2584cffa75637d1459df9569d696d5bd7a32d8f0f9a9'
step_id: 'S33'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Preserve transaction construction paths that omit explicit transaction ids

## Scope

- `src/aeat/domain/transactions/_service.py`

## Description

- Attempt semantic grounding for transaction service construction paths; record the unavailable service and timed-out fallback.
- Inspect `link_invoice`, `set_classification`, and `_validate_transaction_update`.
- Confirm service update paths carry explicit ids from `transaction.model_dump(mode="python")`.
- Confirm missing-id construction is preserved by the S31 model-level default factory.
- Leave `src/aeat/domain/transactions/_service.py` unchanged.

## Outcome
- No service code changes were required for S33.
- `uv run ruff check src/aeat/domain/transactions/_service.py` passed.
- The direct missing-id construction probe passed.
- Focused catalogue service tests for invoice linking and classification updates passed.

## Notes

- `uv run vaultspec-rag search "transaction service model_validate model_dump omit transaction ids updated transaction construction" --limit 8` reported no running service.
- The same search with `--allow-fallback` timed out after 34 seconds, so grounding used direct source reads and `rg` results for the service and transaction tests.
- The first focused pytest command used stale node names; the current service test names were located and passed.
