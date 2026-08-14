---
tags:
  - '#audit'
  - '#modelo-303-regimen-simplificado'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:ac70422f7cd195209181d2538c1168ded58680bbf2f5ba380f153f450b2cb8cd'
related:
  - "[[2026-07-01-modelo-303-regimen-simplificado-adr]]"
---

# `modelo-303-regimen-simplificado` audit: `S84 immutable annual-summary handoff review`

## Scope

Independent Sol architecture review of the accepted M303 simplified-regime ADR's S84 amendment. The review tested the immutable M303 fourth-quarter to M390 annual-summary handoff for official box mapping, calculation and evidence identity, lifecycle selection, non-self-referential digest construction, agricultural unavailability, selection-only projection, and atomic retirement of the scalar box-79 relation. It inspected the official 2022 M303 and M390 record designs, the implemented work-unit and calculation-revision state model, the application revision selectors, the S76 and S77 calculation cutover, the S83 agricultural refusal, and the live scalar-relation contract being replaced.

## Findings

### s84-immutable-annual-summary-handoff-review | medium | source lifecycle selector was ambiguous

The first reviewed draft required one immutable source revision selected by a canonical work-unit lifecycle pointer, but a work unit has distinct `current_calculation_revision_id` and `filed_calculation_revision_id` pointers. The generic export selector can choose a filed `PRESENTADO` revision, a current `VERIFICADO_COMPLETO` revision, or one unambiguous verified revision. Those candidates may legitimately diverge after a draft, verification, amendment, or refiling, so the draft did not uniquely determine which ten annual values reached M390.

The ADR was amended to admit only Modelo 303 period `4T` whose non-null filed pointer resolves to `PRESENTADO`, whose current calculation pointer equals that filed pointer, and whose current filing record names the same calculation revision. It explicitly refuses filed/current divergence, `VERIFICADO_COMPLETO` current revisions, the generic export-selector precedence, unambiguous-revision search, and `PRESENTADO_SUPERSEDIDO` revisions. Independent re-review found no remaining findings.

The official mappings were independently confirmed as M390 boxes 74 and 75 equal the non-agricultural and agricultural `cuota_resultante` cohort sums, followed by 76 from M303 box 51, 77 from 53, 78 from 52, 79 from 54, 80 from 55, 81 from 56, 82 from 57, and 83 from 58. The identity construction is non-self-referential, agricultural unavailability refuses without a partial handoff or default zero, and the scalar relation retirement boundary covers its declarations, edges, references, overrides, fixtures, tests, and equivalent aliases.

## Recommendations

The lifecycle-selector finding was resolved in the governing ADR before implementation. S84 implementation must use the exact filed-current convergence rule and exercise refusal cases for a missing filed pointer, a merely verified current revision, a newer draft or verified amendment, a superseded filing, mismatched filing-record identity, and all source evidence or digest divergence. No further ADR is required for this handoff contract.
