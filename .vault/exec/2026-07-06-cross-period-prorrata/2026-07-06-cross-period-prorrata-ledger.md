---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:6645372f5f5d613ae7c064d068a2be5a90a61e583c23920a0d4e9e04d483741b'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# `cross-period-prorrata` ledger

## Changes

- `S01` `T` `src/aeat/core/__init__.py`
- `S02` `T` `src/aeat/domain/prorrata_register/__init__.py`
- `S03` `T` `src/aeat/domain/prorrata_register/__init__.py`
- `S04` `T` `src/aeat/domain/prorrata_register/tests/test_prorrata_register.py`
- `S05` `T` `src/aeat/adapters/persistence/storage/_namespace_registry.py`
- `S06` `T` `src/aeat/adapters/persistence/profile/prorrata_register.py`
- `S07` `T` `src/aeat/application/prorrata_register/__init__.py`
- `S08` `T` `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`
- `S09` `T` `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`
- `S10` `T` `src/aeat/application/prorrata_register/_seed.py`
- `S12` `T` `src/aeat/application/prorrata_register/_seed.py`
- `S14` `T` `src/aeat/application/prorrata_register/__init__.py`
- `S15` `T` `src/aeat/application/prorrata_register/__init__.py`
- `S16` `T` `src/aeat/application/prorrata_register/__init__.py`
- `S17` `T` `src/aeat/application/prorrata_register/_seed.py`
- `S18` `T` `src/aeat/application/prorrata_register/tests/test_overrides.py`
- `S19` `T` `src/aeat/application/aggregation/_iva_ledger.py`
- `S20` `T` `src/aeat/application/aggregation/_modelo_bindings.py`
- `S21` `T` `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`
- `S22` `T` `src/aeat/application/aggregation/tests/test_iva_ledger_prorrata_apportionment.py`
- `S23` `T` `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
- `S24` `T` `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `S25` `T` `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `S26` `T` `src/aeat/application/modelo/_revision_persistence.py`
- `S26` `T` `src/aeat/adapters/persistence/profile/prorrata_register.py`
- `S26` `T` `src/aeat/application/modelo/tests/test_prorrata_settlement_writeback.py`
- `S27` `T` `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`
- `S28` `T` `src/aeat/_data/corpus/manual_oracles/modelo-303-prorrata-general-regularizacion.json`
- `S29` `T` `src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py`
- `S30` `T` `src/aeat/application/aggregation/_source_mesh.py`
- `S31` `T` `src/aeat/application/aggregation/_source_mesh.py`
- `S32` `T` `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `S33` `T` `src/aeat/application/calculations/__init__.py`
- `S33` `T` `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `S33` `T` `src/aeat/application/modelo/_calculation_diagnostics.py`
- `S33` `T` `src/aeat/application/modelo/_prorrata_regularizacion_advisory.py`
- `S33` `T` `src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
- `S33` `T` `src/aeat/application/calculations/tests/test_prorrata_missing_carry.py`
- `S34` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/verification_expectations/`
- `S34` `T` `src/aeat/application/modelo/tests/test_verification_m303_prorrata_advisory.py`
- `S35` `T` `src/aeat/application/calculations/tests/test_prorrata_regularizacion.py`
- `S36` `T` `.vault/exec/2026-06-19-silent-zero-base-aggregation/`
- `S37` `T` `.vault/exec/2026-07-06-cross-period-prorrata/`
- `S38` `T` `.vault/exec/2026-07-06-cross-period-prorrata/`
- `S39` `T` `.vault/exec/2026-07-06-cross-period-prorrata/`
- `S40` `T` `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`
- `S41` `T` `.vault/exec/2026-07-06-cross-period-prorrata/2026-07-06-cross-period-prorrata-W06-P09-S41.md`
- `S41` `T` `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`
- `S41` `T` `.vault/plan/2026-07-06-cross-period-prorrata-plan.md`
- `S42` `T` `src/aeat/domain/calculations/registry/_bindings.py`
- `S42` `T` `src/aeat/domain/calculations/registry/tests/test_selector_shape.py`
- `S43` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/`
- `S43` `T` `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/`
- `S43` `T` `src/aeat/domain/calculations/registry/tests/`
- `S44` `T` `src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/`
- `S44` `T` `src/aeat/domain/calculations/registry/tests/`
- `S45` `T` `src/aeat/application/modelo/_calculation_actions.py`
- `S45` `T` `src/aeat/domain/calculations/registry/_formula_initial_values.py`
- `S45` `T` `src/aeat/application/modelo/tests/`
- `S46` `T` `src/aeat/application/calculations/_prorrata_regularizacion.py`
- `S46` `T` `src/aeat/application/calculations/__init__.py`
- `S46` `T` `src/aeat/application/calculations/tests/`
- `S47` `T` `src/aeat/application/aggregation/_source_mesh.py`
- `S47` `T` `src/aeat/application/modelo/_calculation_actions.py`
- `S47` `T` `src/aeat/application/modelo/_calculation_source_policy.py`
- `S47` `T` `src/aeat/domain/calculations/registry/tests/test_binding_source_kind_taxonomy.py`
- `S47` `T` `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`
- `S47` `T` `src/aeat/application/aggregation/tests/`
- `S48` `T` `src/aeat/application/aggregation/_source_mesh.py`
- `S48` `T` `src/aeat/application/calculations/_bienes_inversion_regularizacion.py`
- `S48` `T` `src/aeat/application/modelo/_bienes_inversion_advisory.py`
- `S48` `T` `src/aeat/application/aggregation/tests/`
- `S49` `T` `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`
- `S49` `T` `.vault/exec/2026-07-06-cross-period-prorrata/`
- `S49` `T` `src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py`
- `S49` `T` `src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
- `S49` `T` `src/aeat/application/modelo/tests/test_verification_m303_prorrata_advisory.py`
