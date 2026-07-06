---
tags:
  - '#exec'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S37'
related:
  - "[[2026-07-06-ledger-perf-optimization-plan]]"
---

# Run the domain transaction model tests after the validator rewrite

## Scope

- `src/aeat/domain/transactions/tests`

## Description

- Re-ground the validator rewrite through semantic vault and code search, then pin the live symbols with `rg`.
- Run the full transaction-domain suite after the after-validator rewrite.
- Expand the step scope when catalogue JSON roundtrips exposed Python-mode nested transaction validation regressions.
- Route JSON-shaped nested catalogue transaction payloads through `Transaction.model_validate_json`.
- Re-run the focused failing catalogue JSON roundtrip tests and then the full transaction-domain suite.

## Outcome
- `src/aeat/domain/transactions/_models.py` now preserves catalogue-level JSON roundtrips after the validator fast-path rewrite.
- The first full `src/aeat/domain/transactions/tests` run failed only `test_persistence_round_trip_preserves_catalogue` and `test_confidence_survives_json_round_trip`.
- `uv run ruff check src/aeat/domain/transactions/_models.py src/aeat/domain/transactions/tests/test_models.py src/aeat/adapters/persistence/profile/tests/test_transactions_repository_roundtrip.py` passed.
- `uv run pytest -q -n 0 src/aeat/domain/transactions/tests/test_catalogue.py::test_persistence_round_trip_preserves_catalogue src/aeat/domain/transactions/tests/test_catalogue.py::test_confidence_survives_json_round_trip` passed.
- `uv run pytest -q -n 0 src/aeat/domain/transactions/tests` passed: 108 passed in 1.38s.

## Notes

- Earlier S37 semantic searches reported unavailable service and timed-out fallback, so the first fix pass used direct source reads. On resume, semantic vault and code searches returned the validator rewrite plan/research and `src/aeat/domain/transactions/_models.py`.
- One path-filtered semantic search expanded the path glob as native command arguments and failed with unexpected search options; the unfiltered semantic code search succeeded.
- The catalogue fix is scoped to JSON-shaped nested payloads. Normal Python-mode catalogue construction still validates nested transactions through `Transaction.model_validate`.
