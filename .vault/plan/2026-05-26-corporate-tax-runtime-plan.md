---
tags:
  - '#plan'
  - '#corporate-tax-runtime'
date: '2026-05-26'
modified: '2026-05-26'
tier: L2
related:
  - '[[2026-05-21-corporate-entity-calculation-adr]]'
  - '[[2026-05-21-taxpayer-type-applicability-plan]]'
  - '[[2026-05-21-cli-testimonial-audit]]'
  - '[[2026-06-04-corporate-tax-runtime-adr]]'
  - '[[2026-06-04-corporate-tax-runtime-research]]'
---


# `corporate-tax-runtime` plan: IS micro-empresa bracket dispatch, INCN-gated Modelo 202 modality, new-entity period rate

### Phase `P01` - profile facts and legal grounding

Land the two regulated profile facts and the BOE-grounded legal entry
they cite, with anti-tautology persistence-boundary roundtrip coverage.

- [x] `P01.S01` - Transcribe LIS Art. 40.3 against the BOE-A-2014-12328 corpus and register `ley-27-2014:art-40-3` as a resolvable scoped registry legal entry carrying the 6.000.000 EUR threshold text; `src/aeat/_data/registry/aeat/legal/is.toml`.
- [x] `P01.S02` - Add an `incn_prior_12_months` typed Decimal profile fact, project it onto `TaxpayerProfile`, collect it in the wizard with operator-language prompt, and bind a `--incn-prior-12-months` CLI flag on `config profile create` and `edit`; `src/aeat/domain/deadlines`.
- [x] `P01.S03` - Add a `new_entity_first_two_profit_periods` typed boolean profile fact, project it onto `TaxpayerProfile`, collect it in the wizard with operator-language prompt, and bind a CLI flag on `config profile create` and `edit`; `src/aeat/domain/deadlines`.
- [x] `P01.S04` - Roundtrip and anti-tautology tests for both new optional facts through the real encrypted SQL persistence boundary, populating non-default values and asserting strict equality on reload; `src/aeat/application/user_profile`.

### Phase `P02` - runtime, formula, and Modelo 202 modality

Wire the new facts into the calculation runtime so the micro-empresa
bracket, the new-entity 15 percent rate, and the Modelo 202 modality
gate all resolve correctly.

- [x] `P02.S05` - Introduce a `lookup_bracket_by_entity_type` calculation-runtime op modelled on the `lookup_bracket_by_ccaa` precedent, resolving a `bracket_table` parameter against the profile's `legal_entity_form` and period state and rejecting scalar parameters with a clear validation error; `src/aeat/domain/calculations/registry`.
- [x] `P02.S06` - Restructure the Modelo 200 cuota-integra formula to apply a tranche table per entity sub-form, routing a micro-empresa profile to `tipo-gravamen-pyme` via the new op and layering the new-entity 15 percent override via the period-state fact; `src/aeat/_data/registry/aeat/modelos/200`.
- [x] `P02.S07` - Register the Modelo 202 modality gate as a registry-derived applicability condition keyed on the INCN threshold, making Art. 40.3 mandatory above 6.000.000 EUR and keeping Art. 40.2 reachable below, each carrying the new `ley-27-2014:art-40-3` `legal_refs`; `src/aeat/_data/registry/aeat/modelos/202`.
- [x] `P02.S08` - Real-behaviour tests grounding expected IS cuota against AEAT Manual de Sociedades worked examples for the general, micro-empresa, and new-entity cases, plus structural tests proving the Modelo 202 modality gate; `src/aeat/domain/calculations/registry`.
