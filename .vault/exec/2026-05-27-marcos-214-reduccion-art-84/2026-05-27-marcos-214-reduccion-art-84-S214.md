---
tags:
  - '#exec'
  - '#marcos-214'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S214'
related:
  - '[[2026-05-07-renta-full-coverage-plan]]'
---

# `marcos-214` `S214`

M100 casilla 0461 (Reducción Art. 84 LIRPF €3,400 unidad familiar tipo 1 conjunta) wired as
computed from `declaration_type=2` profile binding.  Previously stayed at 0 even when the
profile carried `declaration_type = 2` (conjunta), causing ~600k Spanish married couples
filing conjunta yearly to pay excess cuota.

- Created: `src/aeat/_data/registry/aeat/legal/irpf.toml` — added `ley-35-2006:art-84` legal entry
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0008-renta-2024-profile-declaration-type.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/bindings/0009-renta-2024-profile-family-minor-children-in-unit.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0176-renta-2024-reduccion-art-84-conjunta.toml`
- Created: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/formulas/0179-renta-2025-reduccion-art-84-conjunta.toml`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0444-0461.toml` — `input_kind = "computed"`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0528-0461.toml` — `input_kind = "computed"`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/constructs/0001-renta-cuota-chain.toml` — formula inserted before `renta-2024-base-liquidable-general`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/constructs/0001-renta-cuota-chain.toml` — formula inserted before `renta-2025-base-liquidable-general`
- Created: `src/aeat/domain/calculations/registry/test_reduccion_art_84_conjunta.py`
- Modified: `src/aeat/domain/calculations/registry/test_renta_chain_behaviour.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_ahorro_base_chain.py`
- Modified: `src/aeat/domain/calculations/registry/test_minimo_contribuyente_age_increment.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_settlement_chain.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_cripto_1812_propagation.py`

## Description

Casilla 0461 had no `input_kind` (defaulting to manual) and no formula in both the 2024
and 2025 M100 revisions.  Any taxpayer declaring `conjunta` received zero reduction
regardless of profile, paying excess cuota.

The fix introduces:

- Profile binding `renta-2024-profile-declaration-type` (selector `filing_export.declaration_type`)
  and `renta-2024-profile-family-minor-children-in-unit` (selector `renta_family.minor_children_in_unit`)
  for both 2024 and 2025 revisions.
- Formula `renta-2024-reduccion-art-84-conjunta` (and 2025 counterpart): if `declaration_type == 2`
  AND `minor_children_in_unit == 0` (tipo-1 matrimonio, Art. 82.1 LIRPF) → €3,400; else €0.
  Tipo-2 monoparental (Art. 82.2, `minor_children_in_unit == 1`) is excluded here because
  their €2,150 reducción flows through Art. 81 into a separate casilla.
- Legal entry `ley-35-2006:art-84` in the shared legal catalogue, grounded against the
  HTML corpus at `corpus/normatives/html/ley-35-2006.html#a84`.
- Both casilla files flipped to `input_kind = "computed"` with formula back-reference.
- Constructs updated to include the new formula before `renta-2024-base-liquidable-general`.

All pre-existing tests that call `calculate_registry_snapshot` on the full 2024 M100
chain now pass the two new required bindings.

## Tests

8 oracle tests in `test_reduccion_art_84_conjunta.py` covering both 2024 and 2025 revisions:

- Tipo-1 matrimonio conjunta → 3400.00 (2024 and 2025)
- Individual → 0.00 (2024 and 2025)
- Tipo-2 monoparental conjunta → 0.00 (2024 and 2025)
- Anti-tautology: changing `declaration_type` from 2 to 1 changes 0461 from 3400 to 0 (2024 and 2025)

All 8 tests pass.  `test_minimo_contribuyente_age_increment.py` (8 tests) passes clean.
Chain failures in `test_modelo_100_ahorro_base_chain.py` and `test_modelo_100_settlement_chain.py`
are pre-existing and caused by peer-agent incomplete relation bindings (`renta-2024-rel-130-pagos-fraccionados`)
unrelated to this step.
