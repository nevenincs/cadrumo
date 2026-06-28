---
tags:
  - '#exec'
  - '#m303-form-vs-semantic-casilla-dual-keying'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S21'
related:
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-plan]]"
---




# Verify the BOE/fichero export field modelo-303-page-01-casilla-27 and the sibling casilla-NN export refs now write the projected value not zero, and confirm the workbook/BOE parity gate stays green (modelo-export-mirrors-official-structure)

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/`

## Description

- Verify export-ref value carriage: the casilla-27 export field still targets box 27, which now carries the projected (non-zero) cuota on a ledger-fed calculate, so the export reads value not zero.
- test_export_ref_points_at_projected_box_carrying_value asserts this; the existing fichero export test (test_export_modelo_303_wallet_only...) exercises the full BOE render with non-zero repercutido. The workbook/BOE parity gate (test_record_design completeness manifest, test_registry_reviewability) stays green after adding the ten boxes to the manifest fragment.

## Outcome

- Step landed; focused gates green (registry M303 load, verification-substance operator parity, the M303 official-box projection suite).

## Notes

- The DSL-operator edits touch `_schema.py` and `_verification_actions.py`, which carried concurrent peer WIP (a DT-12 advisory extraction). The edits are additive and in disjoint regions; the working tree is internally consistent and all focused tests pass.
