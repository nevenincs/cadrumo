---
tags:
  - '#audit'
  - '#registry-bindings-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# `registry-bindings-boundary` audit: `binding resolver extraction boundary audit`

## Scope

Audited `src/aeat/domain/calculations/registry/_bindings.py` as the
largest production module in the registry package and the next planned
P04 monolith target. The audit assessed whether resolver families can be
split into private helper modules without creating a new binding
architecture, changing selector semantics, or disturbing concurrent
shared-worktree edits.

## Findings

### High

- `_bindings.py` is 3,040 working-tree lines and mixes core observation
  DTOs, previous-filing selectors, invoice aggregation, counterpart
  aggregation, OSS/IOSS ledger aggregation, IVA ledger aggregation, Renta
  ledger aggregation, withholding, related-party rows, foreign-asset
  rows, attribution rows, refund rows, profile selectors, manual-input
  selectors, and the selector-shape validation registry. This is too
  broad for reliable review, but the families are identifiable enough
  for a staged extraction.
- A current peer diff changes the previous-filing family by adding an
  opt-in `per_grupo_member` grouping path and same-period offset support.
  That family is not safe to extract in this slice because the working
  tree contains non-format feature WIP. Editing it now would risk
  cross-committing or obscuring another agent's change.
- Previous-filing is also coupled to runtime internals:
  `src/aeat/domain/calculations/registry/_formula_runtime.py` imports
  `_PreviousModeloSelector` directly. Any extraction of that family must
  preserve the private import contract or first move the runtime
  dependency behind a stable helper.

### Medium

- Invoice and counterpart aggregation share `_InvoiceSelector`,
  invoice-style row builders, and the `_counterpart_to_invoice` adapter.
  Counterpart should not be split independently until invoice helper
  ownership is explicit, or the extraction will create import cycles and
  selector duplication.
- Ledger aggregation is internally separable by source family: OSS/IOSS,
  IVA, and Renta have distinct observation models and selector builders.
  They are good extraction candidates after row-set families because
  they have broad application consumers and require a wider test surface.
- The low-coupling detail row-set families are the safest first
  extraction candidates: related-party rows, foreign-asset rows,
  attribution rows, and refund rows each have compact selector models,
  compact row builders, and direct focused tests.
- `validate_binding_selector_shape` currently depends on the module-local
  selector model registry. Moving it before selector families are
  relocated would either duplicate the registry or require an awkward
  cross-module import back into `_bindings.py`.

### Low

- `CasillaObservation`, `RegistryModeloObservation`,
  `OracleModeloObservation`, `RegistryModeloObservationRequirement`, and
  `resolve_bound_casilla_inputs` are core cross-family DTO/API elements.
  They can remain in `_bindings.py` during resolver extraction, or move
  later to a small observation module only after public API boundary tests
  guard the re-export contract.
- The current registry public API already exports many binding helpers,
  so extraction must leave `registry.__init__` and `_bindings.__all__`
  behavior-compatible. The desired result is smaller private modules, not
  a user-visible import migration.

## Recommendations

1. Do not perform a one-shot split of `_bindings.py`.
2. Extract low-coupling row-set families first into private binding
   helper module(s), preserving all existing exports from `_bindings.py`:
   related-party, foreign-asset, attribution, and refund.
3. Extract withholding next; it is larger than the row-set families but
   self-contained enough to validate with focused resolver tests.
4. Extract ledger families after that, either as one ledger helper module
   or as OSS/IOSS, IVA, and Renta helper modules if tests show cleaner
   ownership boundaries.
5. Treat invoice and counterpart as a paired extraction or move shared
   invoice helpers first, then counterpart. Avoid duplicating selector
   semantics.
6. Leave previous-filing extraction until the visible `per_grupo_member`
   peer WIP lands and the `_formula_runtime.py` private selector import
   is explicitly handled.
7. Leave `validate_binding_selector_shape` until the selector model
   registry can move with the selector classes it validates.
8. For each extraction, run the focused real-behavior tests covering that
   resolver family plus public API boundary coverage. Minimum surfaces:
   `test_detail_record_row_builders.py`,
   `test_counterpart_bindings.py`, `test_invoice_bindings.py`,
   `test_ledger_iva_aggregation_binding.py`,
   `test_ledger_oss_aggregation_binding.py`,
   `test_ledger_renta_expense_binding.py`,
   `test_selector_shape.py`, and
   `test_public_api_boundaries.py`, scoped to the touched family.

## Codification candidates

- **Source:** finding High-1.
  **Rule slug:** `registry-resolver-family-extraction`.
  **Rule:** Large registry resolver modules must be split by resolver
  family behind compatibility re-exports, with one family and its tests
  moved per commit.
