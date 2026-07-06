---
tags:
  - '#research'
  - '#m210-categorical-conditional-predicate'
date: '2026-07-06'
modified: '2026-07-06'
related: []
---

# `m210-categorical-conditional-predicate` research: `M210 inmobiliaria text-casilla advisory grounding`

This research backfills the same-feature grounding for the accepted
`2026-06-30-m210-categorical-conditional-predicate-adr`. It re-read the ADR,
searched the vault and code indexes with `vaultspec-rag`, and confirmed the
live operator, registry predicate, validator, text-input channel, and tests with
targeted grep/read slices before recording the bridge.

## Findings

- The accepted decision targets a real silent-zero shape that the existing
  numeric `implies_nonzero` operator could not express. The M210 inmobiliaria
  branch is selected by text casilla `tipo_renta == "inmobiliaria"`, while the
  consequence is numeric `base_imponible != 0`; the old DSL could read Decimal
  casilla values but not a categorical text antecedent. Source:
  `2026-06-30-m210-categorical-conditional-predicate-adr`, Problem Statement
  and Considerations.
- The registry DSL now declares `casilla_equals_implies_nonzero` as a known
  operator for exactly this mixed shape. The schema comments keep it
  ADVISORY-only, name the M210 inmobiliaria use site, and distinguish it from
  numeric-antecedent `implies_nonzero`. Sources:
  `src/aeat/domain/calculations/registry/_schema.py:968` and
  `src/aeat/domain/calculations/registry/_schema.py:1172`.
- Runtime evaluation preserves the Decimal boundary. The advisory evaluator
  parses three tokens, compares the antecedent through `text_values`, and tests
  the consequent through `casilla_values`; missing or non-matching text holds
  trivially. `_evaluate_verification_predicates` accepts `text_values` as an
  additive optional parameter and only text-aware advisory operators consume it.
  Sources: `src/aeat/application/modelo/_verification_predicates.py:150`,
  `src/aeat/application/modelo/_verification_predicates.py:650`, and
  `src/aeat/application/modelo/_verification_predicates.py:790`.
- Verification passes persisted operator text to the predicate layer. The layer
  2 gate reads `CalculationRevision.input_values_by_casilla_id` as the
  `text_values` channel while the Decimal casilla projection remains separate.
  Source: `src/aeat/application/modelo/_verification_actions.py:967`.
- The post-review write-side correction is present. `WorkCalculateInputBundle`
  carries `text_casilla_inputs`; `calculate_modelo_revision` validates those
  text ids, passes them to `calculate_registry_snapshot(text_inputs=...)`, and
  merges the resolved text entries into persisted `input_values_by_casilla_id`.
  The bucket-aggregation wrapper forwards the same channel. Sources:
  `src/aeat/application/modelo/_calculate_input.py:131`,
  `src/aeat/application/modelo/_calculation_actions.py:165`,
  `src/aeat/application/modelo/_calculation_actions.py:277`,
  `src/aeat/application/modelo/_calculation_actions.py:320`, and
  `src/aeat/application/modelo/_calculation_actions.py:780`.
- The registry predicate is authored on the M210 2025 revision as an ADVISORY:
  `casilla_equals_implies_nonzero(["tipo_renta", "inmobiliaria",
  "base_imponible"])`, with legal refs to TRLIRNR art. 13.1.h and art. 24. The
  comments document the imputed-real-estate risk and why every inmobiliaria
  input can otherwise be absent without a required-casilla gate. Source:
  `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml:40`.
- Authoring validation is guarded. The surface validator routes the operator to
  a bespoke mixed-token validator, and tests reject bad arity, unknown casillas,
  empty literal, non-text antecedent, and text consequent while accepting the
  committed M210 predicate. Sources:
  `src/aeat/domain/calculations/registry/_validate_surfaces.py:219` and
  `src/aeat/domain/calculations/registry/tests/test_registry_schema_part2.py:348`.
- Behavioral coverage exists at unit, committed-registry, and real pipeline
  layers. M210 advisory tests prove the warning fires only for
  `tipo_renta == "inmobiliaria"` with zero base and stays silent for a positive
  base, another text value, or missing text values. Registry tests prove the
  committed predicate and legal refs are present. The inmobiliaria E2E test
  drives real calculate then verify, persists `tipo_renta`, obtains a rounded
  zero `base_imponible`, and observes the advisory from the persisted text
  channel. Sources:
  `src/aeat/application/modelo/tests/test_verification_m210_advisory.py:149`,
  `src/aeat/application/modelo/tests/test_verification_m210_advisory.py:157`,
  `src/aeat/domain/calculations/registry/tests/test_modelo_210_registry.py:428`,
  and `src/aeat/application/modelo/tests/test_modelo_210_inmobiliaria_e2e.py:242`.
- No new ADR or implementation plan is recommended from this bridge. The live
  implementation matches the accepted ADR's boundary: no heterogeneous
  `casilla_values` widening, no blocking-rule branch for the advisory-only
  operator, no new source kind, and no silent under-declaration gap found in
  the reviewed M210 inmobiliaria path.
