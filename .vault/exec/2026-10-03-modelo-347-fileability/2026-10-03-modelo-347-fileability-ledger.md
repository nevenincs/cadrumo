---
tags:
  - '#exec'
  - '#modelo-347-fileability'
date: '2026-10-03'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:9e788b6fc25954e21cb9fda8ac890acd14429bf7a97f26090af5a79069a4ba8d'
related:
  - "[[2026-10-03-modelo-347-fileability-plan]]"
---

# `modelo-347-fileability` ledger

## Changes

- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/operaciones-terceros.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/legal/iva-flow.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml`
- `S01` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/bindings/0001-declarations.toml`
- `S01` `verify:` `inspect_authoring_candidate` -> `pass`
- `S02` `A` `src/cadrumo/_data/registry/aeat/facts/0148-m347-clave-threshold-buckets.toml`
- `S02` `M` `src/cadrumo/domain/calculations/registry/m347_threshold.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `S02` `M` `src/cadrumo/domain/calculations/registry/_invoice_row_materialization.py`
- `S02` `A` `src/cadrumo/domain/calculations/registry/tests/test_m347_threshold_buckets.py`
- `S02` `A` `dev/registry/tests/test_m347_threshold_buckets_authored.py`
- `S02` `M` `src/cadrumo/adapters/persistence/profile/tests/test_source_resolver.py`
- `S02` `M` `src/cadrumo/application/filing/tests/test_modelo_347_contraparte_export_parity.py`
- `S02` `verify:` `pytest test_m347_threshold_buckets` -> `pass`
- `S02` `verify:` `ruff check` -> `pass`
- `S02` `verify:` `ty check` -> `pass`
- `S10` `M` `src/cadrumo/domain/calculations/registry/schema_revision_members.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S10` `M` `src/cadrumo/domain/calculations/registry/applicability_payer_facts.py`
- `S10` `M` `dev/registry/compiler/validate_applicability_section.py`
- `S10` `M` `src/cadrumo/_data/registry/aeat/facts/0139-modelo-payer-applicability-facts.toml`
- `S10` `M` `src/cadrumo/_data/registry/aeat/modelos/347/revisions/2011-2024/applicability/0001-declarations.toml`
- `S10` `A` `dev/registry/tests/test_applicability_exclusions.py`
- `S10` `M` `dev/registry/tests/test_payer_fact_declarations.py`
- `S10` `M` `dev/registry/tests/test_modelo_applicability.py`
- `S10` `M` `src/cadrumo/application/overview/tests/test_applicability.py`
- `S10` `verify:` `pytest applicability suites` -> `pass`
- `S10` `verify:` `inspect_authoring_candidate` -> `pass`
- `S10` `verify:` `ruff check` -> `pass`
- `S03` `M` `docs/how-to/review-calculation-values.md`
- `S03` `M` `pyproject.toml`
- `S03` `M` `src/cadrumo/_data/registry/aeat/facts/0080-detail-m349-m210-catalogues.toml`
- `S03` `M` `src/cadrumo/application/invoices/source_resolver.py`
- `S03` `M` `src/cadrumo/application/invoices/tests/test_source_resolver.py`
- `S03` `M` `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`
- `S03` `M` `src/cadrumo/application/modelo/calculate_input.py`
- `S03` `M` `src/cadrumo/application/modelo/edit_models.py`
- `S03` `M` `src/cadrumo/application/modelo/edit_services.py`
- `S03` `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_amend_request_detail_rows.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_amendment_detail_rows.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_calculation_modelo_adjustments.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_detail_row_modelo_membership.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_edit_detail_row_reconstruction.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py`
- `S03` `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `S03` `M` `src/cadrumo/domain/modelos/row_models.py`
- `S03` `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_observations.py`
- `S03` `D` `src/cadrumo/domain/modelos/tests/test_row_models_m347_revision.py`
- `S03` `A` `src/cadrumo/domain/modelos/tests/test_row_models_revision_ids.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/_modelo_cli_support.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_amend_detail_row_argv.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_work_calculate_row_flag.py`
- `S03` `A` `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_347_declarado_rows.py`
- `S03` `M` `src/cadrumo/locales/ca/application.yml`
- `S03` `M` `src/cadrumo/locales/ca/cli.yml`
- `S03` `M` `src/cadrumo/locales/ca/errors.yml`
- `S03` `M` `src/cadrumo/locales/en/application.yml`
- `S03` `M` `src/cadrumo/locales/en/cli.yml`
- `S03` `M` `src/cadrumo/locales/en/errors.yml`
- `S03` `M` `src/cadrumo/locales/es/application.yml`
- `S03` `M` `src/cadrumo/locales/es/cli.yml`
- `S03` `M` `src/cadrumo/locales/es/errors.yml`
- `S03` `M` `src/cadrumo/locales/hu/application.yml`
- `S03` `M` `src/cadrumo/locales/hu/cli.yml`
- `S03` `M` `src/cadrumo/locales/hu/errors.yml`
- `S03` `verify:` `pytest focused S03 suite` -> `pass`
- `S03` `verify:` `ruff check` -> `pass`
- `S12` `M` `src/cadrumo/application/overview/explain.py`
- `S12` `M` `src/cadrumo/application/overview/tests/test_explain.py`
- `S12` `M` `src/cadrumo/domain/calculations/registry/applicability_payer_facts.py`
- `S12` `M` `src/cadrumo/locales/ca/profile.yml`
- `S12` `M` `src/cadrumo/locales/ca/wizard.yml`
- `S12` `M` `src/cadrumo/locales/en/profile.yml`
- `S12` `M` `src/cadrumo/locales/en/wizard.yml`
- `S12` `M` `src/cadrumo/locales/es/profile.yml`
- `S12` `M` `src/cadrumo/locales/es/wizard.yml`
- `S12` `M` `src/cadrumo/locales/hu/profile.yml`
- `S12` `M` `src/cadrumo/locales/hu/wizard.yml`
- `S12` `verify:` `pytest explain and applicability suites` -> `pass`
- `S12` `verify:` `dev.locales status --check` -> `pass`
- `S11` `M` `src/cadrumo/application/overview/agenda.py`
- `S11` `A` `src/cadrumo/application/overview/applicability_evidence.py`
- `S11` `M` `src/cadrumo/application/overview/backlog.py`
- `S11` `M` `src/cadrumo/application/overview/calendar.py`
- `S11` `M` `src/cadrumo/application/overview/calendar_warnings.py`
- `S11` `A` `src/cadrumo/application/overview/tests/test_applicability_evidence.py`
- `S11` `M` `src/cadrumo/application/user_profile/projections.py`
- `S11` `M` `src/cadrumo/application/user_profile/tests/test_projections.py`
- `S11` `M` `src/cadrumo/domain/calculations/registry/applicability.py`
- `S11` `M` `src/cadrumo/domain/deadlines/models.py`
- `S11` `M` `src/cadrumo/entrypoints/overview_read_composition.py`
- `S11` `M` `src/cadrumo/locales/ca/cli.yml`
- `S11` `M` `src/cadrumo/locales/ca/common.yml`
- `S11` `M` `src/cadrumo/locales/en/cli.yml`
- `S11` `M` `src/cadrumo/locales/en/common.yml`
- `S11` `M` `src/cadrumo/locales/es/cli.yml`
- `S11` `M` `src/cadrumo/locales/es/common.yml`
- `S11` `M` `src/cadrumo/locales/hu/cli.yml`
- `S11` `M` `src/cadrumo/locales/hu/common.yml`
- `S11` `verify:` `pytest overview applicability projections suites` -> `pass`
- `S11` `verify:` `ruff check` -> `pass`

## Notes

- `S01` stand-in rd-1065-2007-art-31.html and its sidecars are unreferenced and await deletion at Phase close
- `S02` 44 tests that read the published authority await the P01 Phase-close publication
- `S10` `applicability_payer_facts.py` includes another writer's helper split of the new code; published-authority tests await Phase publication
- `S03` two known failures: one awaits publication of fact 0080, one is the pre-existing dead 349 summary loop (operator 349 rows do not reach type 1 totals), recorded as follow-up
- `S12` census adoption not implemented: no census source Cadrumo reads carries SII, IVA regime, criterio de caja or estimation regime; needs a certificate or 036 read-back reader (new scope)
- `S11` Step stays open: TUI reader wiring waits for another writer's uncommitted workbench calendar split, and overview explain must receive the per-year evidence; `_DECLARED_RECORD_COUNT_SOURCES` is a one-entry Python table that should move to registry data
