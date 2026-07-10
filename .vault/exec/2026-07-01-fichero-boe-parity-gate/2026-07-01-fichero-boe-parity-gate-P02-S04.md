---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-01'
modified: '2026-07-08'
step_id: 'S04'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Widen the rendered casilla-set derivation to enumerate every casilla-bearing field kind that reaches disk

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add `boe_representable_casilla_ids` and `rendered_casilla_ids` to the export module, deriving the on-disk casilla set across all field kinds (xml-dictionary entries; fixed-width CASILLA fields plus binding-row `row_field_casilla_ids`) in non-suppressed records, intersected with `draft.values` for the rendered set.
- Leave `_exported_casilla_provenance` untouched; the widened enumeration is a new helper, not a mutation of the receipt provenance contract.

## Outcome

Landed with S05-S07 in the P02 commit. Ruff clean.

## Notes

Empirically grounded first: a naive manifest-subset-of-direct-CASILLA-fields check false-panics on 130 (1 casilla), 303 (19), 200 (1), and 100 (628; xml-dictionary carries zero CASILLA fields). The helper spans every casilla-bearing field kind so the gate can intersect the manifest with the truly-representable set rather than false-firing on calc-closure-only casillas.
