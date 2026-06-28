---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W33.P161'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-domain-harvest-oss-ioss-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W33.P161`

Landed the application-layer wrapper for Modelo 369 OSS / IOSS
aggregation. The wrapper closes the gap the ADR identified between
the existing substrate (regime taxonomy, lookup_rate,
OssIossLedgerObservation, ledger_oss_aggregation binding resolver)
and the modelo calculation path.

- Created: `src/aeat/application/aggregation/_oss_ioss.py`
- Modified: `src/aeat/application/aggregation/__init__.py`

## Description

Public surface added to `aeat.application.aggregation`:

- `OssIossLedgerCandidate` — the application-layer hand-off shape.
  Carries the four classification axes (regime, destination Member
  State, rate tier, invoice direction), the substrate
  `TransactionKind`, and the persisted base / IVA amounts. Strict,
  frozen, extras-forbid Pydantic v2 model that rejects negative
  amounts and unknown axes.
- `validate_oss_ioss_observation(candidate) -> OssIossLedgerObservation`
  — looks up the destination MS rate via
  `aeat.domain.vat.lookup_rate(destination, rate_kind, supply_date)`,
  derives the expected IVA from `base * rate / 100`, and rejects the
  line through `AggregationValidationError` when the persisted IVA
  deviates by more than the one-cent tolerance.
- `validate_oss_ioss_observations(candidates) -> tuple[...]` — batch
  helper that preserves input order and fails fast on the first bad
  row.
- `aggregate_oss_ioss_bindings(revision, candidates) -> dict[str, Decimal]`
  — full pipeline that validates every candidate then routes the
  resulting observations into the registry's
  `resolve_ledger_oss_aggregation_binding_values`. The aggregator is
  what the `aeat app modelo calculate` path for Modelo 369 will
  consume.

Errors:

- `AggregationValidationError` already in `application.aggregation`
  is reused for IVA-amount-rate mismatches; the structured `context`
  attaches `ledger_id`, `destination_member_state`, `rate_kind`,
  `transaction_date`, `base_amount`, `persisted_iva_amount`, and
  `expected_iva_amount` so the modelo orchestrator can surface a
  humane diagnostic.
- `VatRateNotFoundError` from `aeat.domain.vat` propagates when the
  substrate has no registered rate for the destination / tier at the
  supply date. The line cannot be aggregated; the caller must fix
  the registry.

Tolerance:

- `_IVA_TOLERANCE = Decimal("0.01")`. Ledger amounts are persisted
  at two decimal places; a one-cent drift is rounding noise. A
  two-cent or greater drift is a hard blocker.

Closed plan rows: `W33.P161.S0961`, `W33.P161.S0962`,
`W33.P161.S0963`, `W33.P161.S0964`, `W33.P161.S0965`,
`W33.P161.S0966`.

## Tests

`uv run --no-sync pytest src/aeat/application/aggregation/test_oss_ioss.py -q`
— 17 / 17 pass.

Wider aggregation + Modelo 369 registry + OSS substrate suites stay
green: 131 / 131 across
`src/aeat/application/aggregation/`,
`src/aeat/domain/calculations/registry/test_ledger_oss_aggregation_binding.py`,
`src/aeat/domain/calculations/registry/test_modelo_369_registry.py`,
and `src/aeat/domain/vat/test_oss.py`.
