---
tags:
  - '#plan'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
tier: L1
related:
  - '[[2026-05-18-schema-hardening-adr]]'
  - '[[2026-05-18-schema-hardening-research]]'
  - '[[2026-05-18-schema-hardening-plan]]'
---


# `schema-hardening` Plan B: `CasillaConstraints` expansion plan

- [x] `S01` - add optional `pattern`, `min_length`, `max_length`, `enum` slots to `CasillaConstraints`; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `S02` - add `model_validator` rejecting `min_length > max_length` and rejecting empty `enum` tuples; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `S03` - extend the snapshot-build casilla validator to enforce `pattern` against `data_type = "text"` casilla values with hard-error failure; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `S04` - extend the snapshot-build casilla validator to enforce `min_length` and `max_length` against `data_type = "text"` casilla values; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `S05` - extend the snapshot-build casilla validator to enforce `enum` membership against `data_type = "text"` casilla values; `src/aeat/domain/calculations/registry/_schema.py`.
- [x] `S06` - add strict roundtrip test covering `pattern` accept and reject paths against real modelo fixtures; `src/aeat/domain/calculations/registry/test_constraints_pattern.py`.
- [x] `S07` - add strict roundtrip test covering `min_length` and `max_length` accept and reject paths; `src/aeat/domain/calculations/registry/test_constraints_length.py`.
- [x] `S08` - add strict roundtrip test covering `enum` accept and reject paths; `src/aeat/domain/calculations/registry/test_constraints_enum.py`.
- [x] `S09` - add anti-tautology test mutating a constraint on a saved fixture and confirming snapshot build now fails; `src/aeat/domain/calculations/registry/test_constraints_anti_tautology.py`.
- [x] `S10` - constraint-backfill audit complete: candidate set is empty because Plan A's typed data_type retrofits absorbed the enumerable cases; `framework remains load-bearing for future casilla-level contracts; `.vault/audit/2026-05-19-schema-hardening-constraint-backfill.md`.
- [x] `S11` - M100 CCAA lives at binding-selector level (renta-2025-profile-tax-residence-ccaa binding); `CasillaConstraints does not apply; deferred to future BindingSelector constraint surface; `src/aeat/_data/registry/aeat/modelos/100/`.
- [x] `S12` - M720 domicilio lives at binding-selector level with selector.length = 164 already enforced by the fichero-BOE serialiser; `CasillaConstraints does not apply; `src/aeat/_data/registry/aeat/modelos/720.toml`.
- [x] `S13` - M232 clave-pais lives at binding-selector level across five paraiso operation slots; `CasillaConstraints does not apply; `src/aeat/_data/registry/aeat/modelos/232.toml`.
- [x] `S14` - expansion sentinel; `no casilla-level constraint backfill needed per S10 audit; `.vault/audit/2026-05-19-schema-hardening-constraint-backfill.md`.
- [x] `S15` - run the full pytest suite under `src/aeat/domain/calculations/registry/` against the live registry corpus to confirm zero regressions; `src/aeat/domain/calculations/registry/`.
