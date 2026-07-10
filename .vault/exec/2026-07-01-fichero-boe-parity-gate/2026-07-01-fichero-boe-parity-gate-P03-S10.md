---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S10'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Add a pre-write record and section-order assertion that the rendered record order follows the registry declaration order

## Scope

- `src/aeat/application/filing/_export.py`

## Description

- Add `_assert_record_order_fidelity` in `src/aeat/application/filing/_export.py`: derive the records that reach disk, excluding disposition-suppressed records such as the refund DID page, and assert that when emitted in their declared order they follow the registry export-layout declaration order and that no two rendered records share an emit order.
- Raise a hard `FilingExportError` enumerating either the duplicated emit orders or, per position, the registry-declared record versus the record the fichero-BOE would emit.
- Run the assertion pre-write as the first structural-fidelity check inside `assert_export_mirrors_manifest`, before the numbering and presence checks.

## Outcome

- The fichero-BOE parity gate now refuses, before any bytes are written, a `.boe` whose record sequence is permuted away from the registry declaration order or is ambiguous because two records share an emit order, closing the record/section-order dimension of the official-structure mirror.
- A standalone bite probe confirmed the assertion fires on a reversed record-order permutation and on collapsed duplicate emit orders for Modelo 130, and passes untouched on the real shipped structure of every covered modelo, including Modelo 200 with 77 records and Modelo 303 in both refund and non-refund dispositions.

## Notes

- Grounded the record/section order in the export-layout declaration order rather than the casilla declaration-order sections: a probe proved the fixed-width record and field byte layout deliberately does not emit casillas in registry casilla-declaration-section order for Modelo 303, Modelo 200, and Modelo 390 (their casilla-declaration section order diverges from the emit order at the first position), so the export-layout record sequence is the correct registry authority for the `.boe` record/section order and a casilla-section-order check would false-fire on legitimate layouts.
- A probe across the covered and dormancy modelos confirmed each renderable record set already has unique emit orders and a declaration order equal to its emit order, so the assertion does not false-fire on shipped data.
