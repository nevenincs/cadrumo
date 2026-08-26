---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:f54f4bd580e775e701471f71f860d64aed8989f3d0ed46c2eb65322f9fb95ea4'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S56 exonerado-390 activity-row authority closure review`

## Scope

Independent review of W04.P07.S56 at candidate `7af1f4b3c694b9f39a4bf91156bacfdeaadaac67`, directly parented by `fb5b2fc6ea5645825b6d4b6a9abc331fdbec43c4`. The review covered the immutable activity-row owner, exact `DP30304` value arrival, strict refusal paths, the M303 export applicability structural gate, and lifecycle closure.

The reviewer reported approval with zero unresolved critical, high, or medium findings. Independent evidence covered 90 focused tests, changed-file formatting and lint, targeted type checking, compileability, clean diff, five real record-design epochs with exact 13-field geometry, source identity, kind, epoch, hash, year checks, and `FilingExportError` translation. Full-repository type checking retains 35 unrelated baseline diagnostics outside this candidate's changed files.

Scoped Vault checks reported only unrelated lifecycle warnings: PLAN022 ordering, one plan blank-line warning, 13 peer template-annotation warnings, a stale feature index with 70 links for 91 documents, five missing required sections in peer S58 records, one unreferenced S54 research record, and eight peer modified-stamp warnings. This S56 audit and Step Record produced none of those warnings.

## Findings

### stale-s56-retired-census | high | The pre-S56 retired-symbol gate rejected the canonical S56 authority

The initial candidate caused `test_m303_export_applicability_internal.py` to fail one of two checks because its retired-symbol census still prohibited `M303Exonerado390ActivityRowEvidence`, `operaciones_terceros_declarables`, and `operaciones_terceros_reference`. The candidate was amended to preserve the real retired-symbol census and add an AST-backed positive census requiring exactly one `M303Exonerado390` owner for the row class and all three S56 fields. The corrected locked selector passed three of three checks; independent review found the revised owner immutable, unique, complete, and free of defaults.

## Recommendations

- Retain the positive owner census with the genuine retired-symbol census so future authority additions cannot be misclassified as legacy and legacy aliases cannot re-enter production.
- Keep broad type-check diagnostics outside this change's path scope tracked as baseline work rather than treating them as S56 review failures.
