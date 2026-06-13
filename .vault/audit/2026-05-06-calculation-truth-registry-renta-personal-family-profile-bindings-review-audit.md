---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-phase4-renta-personal-family-profile-bindings-exec]]'
---



# `calculation-truth-registry` Code Review

CALC-TRUTH-REGISTRY-001 | MEDIUM | CCAA profile binding is backed by unrelated source-citation text
The Modelo 100 2025 `renta-2025-profile-tax-residence-ccaa` binding targets `ZCCAD` and selector field `ccaa`, but its attached `boe-modelo-100-2025-form` source citation requires only the text `número de identificación fiscal (NIF)`. That phrase proves identity/NIF content, not the autonomous-community declaration field. Because the registry validator accepts required text presence as source closure, this can let an unrelated official-text match satisfy evidence for the CCAA binding and weaken the source-evidence gate required by the accepted registry ADR. Review `registry/aeat/modelos/100.toml` around lines 4823-4832 and replace the citation with text that specifically supports `ZCCAD` or the official CCAA declaration field.

Resolution: fixed. The binding now cites BOE text specific to common-regime
autonomous community residence for ejercicio 2025, and registry validation
passes with the narrower citation.

CALC-TRUTH-REGISTRY-002 | LOW | Tests do not prove all spouse conditional selectors remain complete
The registry data contains `required_when_profile_key = "declaration.type"` and `required_when_value = "2"` for the four spouse bindings, but the focused test only asserts the guard key for `renta-2025-profile-spouse-tax-id`. A regression could drop the required value or omit the conditional selector from the spouse name, birth-date, or sex binding while leaving this test green if registry validation does not enforce the semantic convention. Review `src/aeat/domain/calculations/registry/test_modelo_100_registry.py` around lines 226-241 and add behaviour assertions covering both conditional selector fields for all spouse bindings.

Resolution: fixed. The focused registry test now asserts both
`required_when_profile_key` and `required_when_value` for every spouse profile
binding.

## Residual Risk

No high or critical issues were found in the scoped review. The slice has the expected 11 `renta-personal-family` bindings and 11 bound casillas, spouse casillas are optional at the casilla level, spouse selectors carry the joint-taxation condition in the registry data, and `PROFILE_KEYS` keeps only `tax.id` and `activity` required. Residual risk is concentrated in evidence specificity and test coverage for conditional selector semantics, not in the observed binding count or profile-key requirement flags.
