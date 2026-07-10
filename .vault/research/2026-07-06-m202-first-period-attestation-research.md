---
tags:
  - '#research'
  - '#m202-first-period-attestation'
date: '2026-07-06'
modified: '2026-07-06'
related: []
---

# `m202-first-period-attestation` research: `first-year modalidad-cuota suppression grounding`

This research backfills the same-feature grounding for the accepted
`2026-06-19-m202-first-period-attestation-adr`. It re-read the ADR, searched the
vault and code indexes with `vaultspec-rag`, and confirmed the live
implementation and tests with exact-symbol grep before recording the bridge.

## Findings

- The accepted decision remains narrow and legally keyed. The problem is a
  first-year Impuesto sobre Sociedades filer under Modelo 202 modalidad cuota:
  LIS art. 40.2 needs the cuota integra of the last IS return whose filing
  deadline has elapsed, but a first-year company has no prior IS return and no
  Modelo 202 fractional-payment obligation. The sibling
  `2026-06-13-first-filer-attestation-adr` does not cover this because Modelo
  202 periods (`1P`, `2P`, `3P`) have no calendar span for the pre-activity
  predicate. Source: `2026-06-19-m202-first-period-attestation-adr`, Problem
  Statement and Considerations.
- The modality boundary is still derived from the single registry definition.
  `modelo_202_modality_from_inputs` returns `INCOMPLETE` for non-legal entities
  or missing INCN, `ART_40_3_MANDATORY` above 6,000,000 EUR, and
  `ART_40_2_OPTIONAL` at or below the threshold; `derive_modelo_202_modality`
  delegates to that same function. Sources:
  `src/aeat/domain/calculations/registry/_applicability_modelo202.py:77` and
  `src/aeat/domain/calculations/registry/_applicability_modelo202.py:119`.
- The clean-state gate implements the ADR as a fail-closed filter over the
  registry-derived dependency graph, not as a caller-invented graph shrink.
  `_qualifies_for_first_year_fractional_suppression` accepts only source modelo
  `202`, derived modality `ART_40_2_OPTIONAL`, a recorded activity-start date,
  and `activity_start_date.year >= target_filing_year`; every other case stays
  in scope and blocks normally. Sources:
  `src/aeat/application/calculations/_cross_period_clean_state.py:338` and
  `src/aeat/application/calculations/_cross_period_clean_state.py:399`.
- The suppression is explicit and non-silent. The evidence builder stamps
  `NO_FRACTIONAL_PAYMENT_OBLIGATION_FIRST_YEAR` with operator-declared
  provenance, while the model properties keep this facet distinct from
  pre-activity suppression. Verification emits a warning advisory with LIS art.
  40.2 and art. 40.3 legal refs rather than claiming AEAT-sourced evidence.
  Sources: `src/aeat/application/calculations/_cross_period_clean_state.py:305`,
  `src/aeat/application/calculations/_cross_period_models.py:95`,
  `src/aeat/application/calculations/_cross_period_models.py:348`, and
  `src/aeat/application/modelo/_verification_cross_period.py:457`.
- The calculation relation resolver mirrors the same determination for the M200
  annual fold-in path. `_first_year_modalidad_cuota_no_m202` derives modality
  from the wizard-free profile projection and fails closed for missing profile,
  malformed entity type, missing activity date, non-40.2 modality, or incomplete
  modality. The zero relation value is emitted only when that flag is true and
  the relation source is Modelo 202, and the caller scopes the flag to Modelo
  200 annual fold-in rather than Modelo 202 intra-year cumulation. Sources:
  `src/aeat/application/calculations/_relation_prefill.py:315`,
  `src/aeat/application/calculations/_relation_prefill.py:556`, and
  `src/aeat/application/calculations/_relation_prefill.py:753`.
- Behavioral coverage exists at the gate, resolver, modality, and end-to-end
  layers. The focused gate tests cover qualification, refusal under mandatory or
  incomplete modality, missing activity date, non-M202 dependencies, and facet
  separation. The modality tests cover threshold behavior and incomplete
  profiles. The resolver and E2E tests prove the first-year zero-resolution
  reaches the M200 calculation/verify path without depending on the wizard
  catalogue. Sources:
  `src/aeat/application/calculations/tests/test_cross_period_first_year_fractional.py:88`,
  `src/aeat/application/calculations/tests/test_cross_period_clean_state.py:764`,
  `src/aeat/domain/calculations/registry/tests/test_modelo_200_cuota_integra_lanes.py:405`,
  `src/aeat/application/calculations/tests/test_modelo_200_202_pagos_fraccionados_fold.py:119`,
  `src/aeat/application/modelo/tests/test_modelo_200_first_year_cuota_e2e.py:177`,
  and
  `src/aeat/application/calculations/tests/test_first_year_modalidad_cuota_no_wizard_catalogue.py:140`.
- No new ADR or implementation plan is recommended from this bridge. The live
  implementation matches the accepted ADR's safety boundary: no new binding
  source kind, no new resolver convention, no local-evidence laundering, and no
  silent under-declaration path were found in this pass.
