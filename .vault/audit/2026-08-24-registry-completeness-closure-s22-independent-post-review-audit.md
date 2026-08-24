---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ad78f74ff925008114fcd7451c3e1d5e59b3fd455dbac7dcb2c06b6093b9df08'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# `registry-completeness-closure` audit: `S22 independent Modelo 390 2021 post-review`

## Scope

Independent post-review of commit `6030f73871`, limited to Modelo 390 revision
`2021`: the exact AEAT record-design authority and annual selector, the loaded
parser-only casilla surface, the non-fileable boundary, the source-casilla and
export owner routes, and a semantic-plus-exact check for a duplicate filing
implementation.

## Findings

No S22 finding. PASS.

The registered `aeat-dr-390-2021` source is exact, not inferred from a later
epoch: its local workbook SHA-256 is
`0164fbea6f500a63950b762f5b5e43c5d771f84ac8d260e70dc1497acaed4246`, matching
both the source catalogue and the AEAT manifest. Its registered authority,
record-design epoch, and closed applicability window are `aeat`, `2021`, and
2021-01-01 through 2021-12-31. A direct compile of the Modelo 390 directory
selects revision `2021` for `2021/0A` and reports applicability grade, ten
casillas, zero bindings, zero formulas, zero export layouts, and the sole
`extractor` application surface. The four filing-grade sibling surfaces carry
325, 329, 393, and 393 casillas respectively. The worklist's real shortfall
classifier therefore returns the recorded refusal: the exact design era matches,
but a ten-casilla file would omit boxes AEAT expects.

The required Vaultspec-RAG pass located the existing `ValidatedRegistryAuthority`
snapshot boundary and the generic filing-export coverage and live proof path.
Whole-module reading and exact `rg` confirmation show that `export_draft` is
the one production byte writer. The one existing Modelo 390 development helper
is explicitly prospective and admits only source epochs 2022 through 2025; it
cannot select or emit a 2021 target. There is no `m390.` producer-key namespace,
no 2021 Modelo 390 semantic-map or render-profile directory, and no competing
2021 writer or closure composer. S22 itself changes only its execution record,
reference, and canonical plan checkbox.

The non-fileable conclusion and routes are therefore accurate. `W02.P04.S27`
owns the missing source-grounded casilla/value-arrival surface; `W02.P04.S28`
owns approved producers, source-bound map and profile, generated fragments,
and real `export_draft` offset evidence. The exact annual source and selector
already agree, so no temporal owner is needed. No code-redeclaration follow-up
is warranted.

## Verification limitation

The focused global registry test could not start because concurrent shared-tree
work currently leaves Modelo 322's `2008-2022` deadline-window fragment without
the required revision table. That unrelated loader error occurs before Modelo
390 test setup. This review instead ran the same real compiler on the complete
Modelo 390 directory and the worklist's real casilla-shortfall classifier; it
does not describe the blocked global run as passing.

## Recommendations

Retain Modelo 390 2021 as applicability-only until both existing owner routes
close with a full source-grounded value surface and canonical emitted-byte proof.
Do not reuse the 2022--2025 prospective helper, infer later layouts backward,
or add a Modelo-specific export route.
