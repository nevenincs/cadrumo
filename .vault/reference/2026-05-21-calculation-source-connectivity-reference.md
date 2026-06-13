---
tags: ["#reference", "#calculation-source-connectivity"]
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-20-calculation-source-connectivity-research]]'
  - '[[2026-05-20-calculation-source-connectivity-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` reference

This reference captures the current code state before executing the source mesh
plan. It is intentionally code-grounded and narrow.

## Current Connected Path

`src/aeat/application/aggregation/_modelo_bindings.py` contains the existing
bucket-local ledger bridge:

- `ModeloLedgerBindingAggregation`
- `resolve_modelo_ledger_binding_values_from_repositories`
- `aggregation_period_for_modelo`

The bridge reads a bucket transaction catalogue through
`TransactionCatalogueRepository`, projects IVA observations through
`aggregate_iva_ledger_observations_from_repositories`, projects Renta expense
observations through `aggregate_renta_ledger_expenses_from_repositories`, and
then resolves registry binding values through the pure registry resolvers.

It only runs when the selected `ModeloRevision` declares
`ledger_iva_aggregation` or `ledger_renta_expense_aggregation`.

## Current Calculation Paths

`src/aeat/application/modelo/_actions.py` has two paths:

- `calculate_modelo_revision` is the low-level calculation path. It resolves
  profile, borrador, relation, IVA wallet, informational period inputs, bound
  casilla inputs, and then runs `calculate_registry_snapshot`.
- `calculate_modelo_revision_from_bucket_aggregation` wraps the low-level path
  with ledger binding resolution, caller collision checks, backend binding
  values, backend bound casilla inputs, and `source_transaction_ids`.

The current collision guard is ledger-specific:

- `_ledger_binding_ids`
- `_ledger_bound_casilla_ids`
- `_reject_caller_overrides_of_ledger_bindings`

This is the concrete generalization target for the source mesh ownership map.

## Current CLI Bypass

`src/aeat/entrypoints/cli/_modelo.py` still routes `app modelo work calculate`
to `calculate_modelo_revision`, not to
`calculate_modelo_revision_from_bucket_aggregation`.

That means the operator-facing calculate path can bypass real bucket ledger
aggregation even though the application bridge exists and is tested.

## Existing Real-Behavior Coverage

`src/aeat/application/modelo/test_bucket_aggregation_flow.py` proves the bridge
works with real secure repositories:

- `test_calculate_modelo_revision_from_bucket_aggregation_uses_bucket_transaction_catalogue`
  seeds two real transactions and verifies Modelo 303 binding overrides,
  bound casilla inputs, calculation values, typed observations, source refs,
  legal refs, source transaction ids, and bucket events.
- Conflict tests verify caller binding and casilla overrides are rejected for
  ledger-owned inputs.

The missing coverage is the CLI path using the same bridge or future mesh.

## Missing Source Mesh Surface

No `src/aeat/application/aggregation/_source_mesh.py` exists yet, and no
`test_source_mesh.py` exists yet.

The aggregation public surface in `src/aeat/application/aggregation/__init__.py`
exports existing per-source aggregation families and the narrow
`ModeloLedgerBindingAggregation`, but no generic source context, resolver,
resolution, diagnostic, or ownership model.

## Registry Source Surface

`src/aeat/domain/calculations/registry/_schema.py` defines
`DataBindingDefinition.source` literals. Current source kinds include legacy
generic values plus concrete source families such as:

- `profile`
- `previous_filing`
- `manual_input`
- `ledger_oss_aggregation`
- `ledger_iva_aggregation`
- `ledger_renta_expense_aggregation`
- `payable_invoice`
- `collectible_invoice`
- `ledger_transaction`
- `purchase_invoice_evidence`
- `withholding`
- `related_party_operation`
- `foreign_asset`
- `atribucion_member`
- `refund_operation`

The mesh must not change registry purity. Registry resolvers remain typed,
storage-free functions. Application resolvers adapt repositories into those
typed observation shapes.

## First Safe Implementation Boundary

Start with `W01.P01` only:

- add strict frozen source mesh boundary models;
- add resolver protocol and ownership declarations;
- add merge semantics for decimal binding values, enum binding values, bound
  casilla inputs, source transaction ids, diagnostics, and provenance;
- add tests for duplicate binding ownership, duplicate bound casilla ownership,
  and unhandled source diagnostics.

Do not route CLI or replace ledger behavior until the ownership and merge
contract is tested independently.

## State Surveillance

Before each execution slice:

- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-20-calculation-source-connectivity-plan.md --json`
- `uv run --no-sync vaultspec-core vault plan query .vault/plan/2026-05-20-calculation-source-connectivity-plan.md --open`

After each slice:

- close only the exact completed steps;
- add an execution record under `.vault/exec/2026-05-20-calculation-source-connectivity`;
- regenerate `registry-authority-flow` only when touching that feature, and
  generate `calculation-source-connectivity` after this feature receives exec
  records;
- keep vault-wide hygiene separate from implementation correctness.
