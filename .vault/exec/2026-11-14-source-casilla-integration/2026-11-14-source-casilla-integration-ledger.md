---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-11-14'
modified: '2026-11-16'
body_schema: 'body-v2'
body_hash: 'sha256:f6fda025e1a89f6de30f3bf30a2588be0802306a62d483c99b14b5e3578cdb15'
related:
  - "[[2026-11-14-source-casilla-integration-plan]]"
---

# `source-casilla-integration` ledger

## Changes

- `S05` `M` `dev/registry/mappings/modelo_840/2003/0002-pagina01.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/casillas/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/constructs/0001-declarations.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/0001-record-m840-pagina01.toml`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/_generation.provenance.json`
- `S05` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/form_layouts/0001-form-layout.toml`
- `S05` `M` `src/cadrumo/core/filing_producer_key.py`
- `S05` `M` `src/cadrumo/locales/ca/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/en/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/es/modelo/schema/840.yml`
- `S05` `M` `src/cadrumo/locales/hu/modelo/schema/840.yml`
- `S05` `verify:` `target-current 840` -> `pass`
- `S05` `verify:` `conformance valid/runtime-load/integrity` -> `pass`
- `S06` `M` `native/desktop/tests/ux/window-ux-audit.test.mjs`
- `S06` `M` `src/cadrumo/application/filing/export_producer.py`
- `S06` `M` `src/cadrumo/application/filing/export_producer_m840.py`
- `S06` `M` `src/cadrumo/application/filing/producer_snapshot_m840.py`
- `S06` `M` `src/cadrumo/application/filing/tests/test_export_producer_m840.py`
- `S06` `M` `src/cadrumo/application/filing/tests/test_export_producer_supply.py`
- `S06` `M` `src/cadrumo/application/modelo/m840_anexo_profile.py`
- `S06` `M` `src/cadrumo/application/modelo/tests/test_m840_anexo_profile.py`
- `S06` `M` `src/cadrumo/locales/ca/application.yml`
- `S06` `M` `src/cadrumo/locales/en/application.yml`
- `S06` `M` `src/cadrumo/locales/es/application.yml`
- `S06` `M` `src/cadrumo/locales/hu/application.yml`
- `S06` `verify:` `test_every_cited_producer_key_is_resolvable` -> `pass`
- `S06` `verify:` `landed t24b tui 4bfa37a867` -> `pass`
- `S07` `M` `dev/registry/pipeline/export_tree.py`
- `S07` `M` `dev/registry/compiler/validate_export_layout_coverage.py`
- `S07` `M` `dev/registry/compiler/record_design_layout_markers.py`
- `S07` `M` `dev/registry/compiler/tests/test_export_layout_source_coverage.py`
- `S07` `A` `src/cadrumo/application/filing/tests/test_m840_export_round_trip.py`
- `S07` `M` `src/cadrumo/application/filing/tests/test_m840_anexo_sheets.py`
- `S07` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export`
- `S07` `verify:` `pytest src/cadrumo/application/filing/tests/test_m840_export_round_trip.py` -> `pass`
- `S04` `M` `dev/registry/mappings/modelo_840/2003/0001-records.toml`
- `S04` `M` `dev/registry/mappings/modelo_840/2003/0004-anexo.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/casillas/0001-declarations.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/constructs/0001-declarations.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/0005-record-m840-anexo.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/0006-record-m840-anexo.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/0007-record-m840-anexo.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/export/_generation.provenance.json`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/form_layouts/0001-form-layout.toml`
- `S04` `M` `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/projection_endpoints/0001-declarations.toml`
- `S04` `M` `src/cadrumo/application/filing/tests/test_m840_anexo_sheets.py`
- `S04` `M` `src/cadrumo/core/filing_producer_key.py`
- `S04` `M` `src/cadrumo/core/filing_projection_m840.py`
- `S04` `M` `src/cadrumo/core/filing_projection_ref.py`
- `S04` `verify:` `test_m840_anexo_sheets` -> `pass`
- `S01` `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S01` `verify:` `pytest test_iae_local_custody test_profile_schema_migration_iae_premises test_iae_local_records test_iae_row_admission (61 passed, commit 79cf6612c9)` -> `pass`
- `S02` `A` `src/cadrumo/domain/contribuyente/iae_local_facts.py`
- `S02` `A` `src/cadrumo/domain/contribuyente/iae_local_record.py`
- `S02` `M` `src/cadrumo/domain/user_profile/schema_migration.py`
- `S02` `A` `src/cadrumo/adapters/persistence/profile/tests/test_iae_local_custody.py`
- `S02` `A` `src/cadrumo/domain/contribuyente/tests/test_iae_local_records.py`
- `S02` `verify:` `pytest test_iae_local_custody test_profile_schema_migration_iae_premises test_iae_local_records test_iae_row_admission (61 passed, commit 79cf6612c9)` -> `pass`
- `S03` `A` `src/cadrumo/application/user_profile/iae_records.py`
- `S03` `M` `src/cadrumo/application/user_profile/section_rows.py`
- `S03` `M` `src/cadrumo/locales/es/profile.yml`
- `S03` `M` `src/cadrumo/locales/en/profile.yml`
- `S03` `M` `src/cadrumo/locales/ca/profile.yml`
- `S03` `M` `src/cadrumo/locales/hu/profile.yml`
- `S03` `A` `src/cadrumo/entrypoints/tests/test_iae_row_admission.py`
- `S03` `verify:` `pytest test_iae_local_custody test_profile_schema_migration_iae_premises test_iae_local_records test_iae_row_admission (61 passed, commit 79cf6612c9)` -> `pass`
