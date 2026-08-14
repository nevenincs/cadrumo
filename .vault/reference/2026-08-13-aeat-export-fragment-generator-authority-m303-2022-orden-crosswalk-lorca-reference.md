---
tags:
  - '#reference'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:a4404e7cac64e92f5a1240c0745d4f4cd3b4993bd5cc57e6aa3a8e71fa9b961a'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` reference: `M303 2022 Orden, crosswalk, and Lorca authority`

## Summary

The bundled official 2022 source is BOE-A-2021-19904, Orden HFP/1335/2021. Its
Anexo II supplies forty-nine non-agricultural IVA activity tables and one
hundred forty-one module rows; Anexo I supplies sixteen agricultural index and
ingreso-a-cuenta rows. The corpus artefact is pinned by its SHA-256 and byte
count before extraction, and its generated sidecar must contain exactly the
same authority units as the parser.

The 2022 AEAT record design is an independent, epoch-pinned source. Its
DP30302 agricultural activity field is two numeric positions, but neither it
nor the 2022 annual Orden publishes the required code-to-activity crosswalk.
The implementation therefore preserves a typed unavailable state carrying
both source identities, the literal DP30302 field coordinate, and the
two-digit constraint. It contains no activity-code inference, description
matching, raw-key selection, or zero-rate substitute.

Disposición adicional cuarta, apartado 2 of the same Orden separately grants
a 20-percent reduction for Annex-II simplified-regime activities in Lorca in
2022. The source states both quarterly and annual calculation scope. The
compiled authority consequently carries the exact rate, Annex-II boundary,
period pair, legal reference, and source reference, without applying a
calculation or borrowing the unrelated 2024 DANA mechanism.

## Implementation boundary

The shared annual-Orden parser accepts the older 2022 HTML encoding only
through exact structural rules: its Annex-I heading class, IAE spelling
without punctuation, period-suffixed module ordinals, and columns that carry
multiple source values. Completeness checks still require the fixed official
counts and ordered module sequence.

The generator manifests one source per supported exercise and records the
2022 Lorca percentage. The registry resolves a 2022 Modelo 303 snapshot to
the 2022 record-design source, retains the crosswalk refusal, and retains the
available Lorca authority. Calculation and filing projection are intentionally
outside this source-authority step.
