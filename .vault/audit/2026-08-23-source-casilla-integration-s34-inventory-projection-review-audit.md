---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a2e35f1727874fd9d53a974cde5e080d58e18d2a572ad3b24ebe3b4e1a19abd2'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-23-inventory-casilla-mapping-adr]]"
---

# `source-casilla-integration` audit: `S34 inventory projection formal code review`

## Scope

Formal review of `W02.P06.S34` against the accepted inventory mapping decision,
its official-source grounding research, and the source-casilla integration plan.
The review covered only `src/cadrumo/domain/contribuyente/inventory/__init__.py`,
`src/cadrumo/domain/contribuyente/inventory/tests/test_anexo_d_projection.py`,
`src/cadrumo/_data/source_connectivity/census.toml`, and
`docs/architecture/index.md`. It checked the 2025 boundary, activity/year grain,
variation arithmetic and rounding, strict result validation, explicit-closing
refusal, removal of the obsolete signed `0155` API, census truthfulness, and test
quality. The six projection tests pass and the scoped diff has no whitespace
errors. The broader census-completeness gate could not reach this slice because
concurrent CLI command-spec work currently fails discovery first at
`src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py`.

## Findings

### cross-period-movement | medium | The projection includes movements outside its declared filing-year coordinate

`compute_inventory_anexo_d_projection` checks only `ledger.year == 2025` and
then passes every `period_movements` row to `compute_inventory_valuation`.
Neither `InventoryLedger` nor the projection requires each `movement_date.year`
to equal the ledger year. A ledger labelled 2025 containing a 2024 purchase is
therefore accepted and emits that purchase as a 2025 closing-stock increase in
`casilla_0177`. This violates the ADR's exact taxpayer-year-activity grain and
coordinate-identity validation requirement. The new tests exercise a wrong
ledger year, but not a wrong movement year, so they do not detect the
cross-period declaration.

Resolved in S34: the projection now refuses every movement whose date year
differs from the ledger filing year and the focused regression proves the
refusal. Moving the invariant onto the broader ledger write model remains
outside this correction-only Step.

### non-cent-result-basis | low | The strict result model accepts unnormalised monetary basis values

`InventoryAnexoDResult` constrains its four monetary fields to be non-negative,
but does not require them to equal the canonical cent-rounded representation.
Its invariant rounds only `closing_value - opening_value`; consequently a public
instance with `opening_value=100.001`, `closing_value=100.002`, and both casillas
zero is valid. The production constructor currently supplies cent-rounded
values, but callers can construct a frozen result whose advertised audited
basis has sub-cent precision and whose displayed split no longer follows from
the stored values without knowing the hidden rounding operation. The tests
cover mutual exclusion but not monetary normalisation or a half-cent boundary.

Resolved in S34: the result invariant now refuses any opening, closing, or
casilla value that is not canonically cent-quantised, with direct-construction
coverage for a sub-cent audited basis.

## Recommendations

- For `cross-period-movement`, enforce that every period movement belongs to the
  ledger year at the canonical `InventoryLedger` validation boundary, and add a
  projection regression proving a 2024 or 2026 movement in a 2025 ledger is
  refused rather than included or silently skipped.
- For `non-cent-result-basis`, require every monetary field on
  `InventoryAnexoDResult` to be canonically cent-normalised, or centralise a
  clearly typed monetary field contract that does so, and add half-cent and
  direct-construction regressions.
- After the concurrent command-spec changes settle, rerun the discovery and
  census-completeness tests so the updated helper identity and locator receive
  their intended machine-checked proof.
