---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:039e4516be73a2fc7bc1bf212b8507ec8682718d7adfc373dacacc865b2f4dc5'
step_id: 'S08'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# Confirm manifest authoring worklist and tranches

## Scope

- The 38 loaded registry revisions whose `completeness_manifest` is absent after the canonical on-disk shape migration.
- The owner-ruled manifest-authoring tranche assignment in the casilla-schema plan.

## Description

- Load the production registry authority and derive the manifest-less revision population from typed snapshots.
- Assign IRPF, IVA, and retenciones revisions to tranche 1, including Modelo 145 and title-grounded Modelo 270.
- Assign the remaining annual informative declarations to tranche 2.
- Assign monthly, profile-based, ad-hoc, and non-informative remainder revisions to tranche 3.
- Obtain owner confirmation before appending one immutable plan step per revision.

## Outcome

Pending owner confirmation. The current loaded denominator is 38 revisions: 14 proposed for tranche 1, 12 for tranche 2, and 12 for tranche 3.

### Proposed tranche 1

| Modelo | Revision |
| --- | --- |
| 121 | 2017-y-siguientes |
| 122 | 2017-y-siguientes |
| 140 | 2020-y-siguientes |
| 143 | 2014-y-siguientes |
| 145 | 2012-01-31-y-siguientes |
| 270 | 2013-y-siguientes |
| 280 | 2025 |
| 308 | 2009-y-siguientes |
| 341 | 2000-y-siguientes |
| 345 | 2025 |
| 360 | 2010-y-siguientes |
| 361 | 2010-y-siguientes |
| 379 | 2024-y-siguientes |
| 380 | 2005-y-siguientes |

### Proposed tranche 2

| Modelo | Revision |
| --- | --- |
| 156 | 2003-y-siguientes |
| 165 | 2013-y-siguientes |
| 179 | 2021-y-siguientes |
| 181 | 2009-y-siguientes |
| 189 | 2025 |
| 231 | 2021-y-siguientes |
| 233 | 2018-y-siguientes |
| 238 | 2024-y-siguientes |
| 289 | 2025 |
| 347 | 2008-y-siguientes |
| 721 | 2023-y-siguientes |
| 848 | 2003-y-siguientes |

### Proposed tranche 3

| Modelo | Revision |
| --- | --- |
| 038 | 2002-y-siguientes |
| 185 | 2025-y-siguientes |
| 186 | 2003-y-siguientes |
| 220 | 2024-y-siguientes |
| 222 | 2025-y-siguientes |
| 234 | 2021-y-siguientes |
| 490 | 2021-y-siguientes |
| 576 | 2007-y-siguientes |
| 592 | 2022-y-siguientes |
| 604 | 2021-y-siguientes |
| 763 | 2011-y-siguientes |
| 840 | 2003-y-siguientes |

## Notes

Modelo 270 is the only cross-axis adjudication: its registry tax domain is `informative`, but its official title is `Resumen anual de retenciones del gravamen especial sobre premios de loterias`. The proposal puts it in tranche 1 because S08 requires classification from both legal domain and title and explicitly prioritises retenciones. No plan rows have been appended and S08 remains open until the owner confirms this assignment.
