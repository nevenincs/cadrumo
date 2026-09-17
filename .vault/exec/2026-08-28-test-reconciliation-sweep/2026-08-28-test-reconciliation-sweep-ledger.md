---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-09-17'
body_schema: 'body-v2'
body_hash: 'sha256:1091ab816618ddaa7cb7ac88e9e4d14cd95235601083204d3ae6030e0bb57181'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# `test-reconciliation-sweep` ledger

## Changes

- `S01` `M` `src/cadrumo/core/tests/test_external_constants_centralisation_part1.py`
- `S01` `verify:` `pytest src/cadrumo/core/tests/test_external_constants_centralisation_part1.py` -> `pass`
- `S02` `M` `src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py`
- `S02` `verify:` `pytest src/cadrumo/adapters/outbound/google/tests/test_package_module_allowlist.py` -> `pass`
- `S03` `A` `src/cadrumo/entrypoints/cli/tests/_m303_filing_evidence_support.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_m303_filing_evidence_creation_contract.py`
- `S03` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `S03` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_m303_filing_evidence_creation_contract.py` -> `pass`
- `S04` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `S04` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `S05` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
- `S06` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `S06` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
- `S07` `M` `src/cadrumo/application/aggregation/_modelo_bindings.py`
- `S07` `M` `src/cadrumo/locales/en/common.yml`
- `S07` `M` `src/cadrumo/locales/es/common.yml`
- `S07` `M` `src/cadrumo/locales/ca/common.yml`
- `S07` `M` `src/cadrumo/locales/hu/common.yml`
- `S07` `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `S07` `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `pass`
- `S08` `M` `src/cadrumo/application/repair_integrity.py`
- `S08` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -m integration` -> `pass`
- `S09` `M` `src/cadrumo/application/repair_integrity.py`
- `S09` `M` `src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py`
- `S09` `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_repair_policy_coverage.py -m integration` -> `pass`
- `S09` `verify:` `pytest src/cadrumo/application/tests/test_repair_integrity.py` -> `pass`
- `S10` `M` `src/cadrumo/domain/user_profile/schema.py`
- `S10` `M` `src/cadrumo/application/user_profile/preflight.py`
- `S10` `M` `src/cadrumo/_data/registry/cadrumo/user_profile/schema.toml`
- `S10` `A` `src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py`
- `S10` `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_modelo_scoped_requirement.py` -> `pass`
- `S10` `verify:` `pytest src/cadrumo/application/user_profile/tests/test_preflight_reports_unassessed_axis.py` -> `pass`
- `S11` `M` `src/cadrumo/application/ledger/tests/test_public_definition_identity.py`
- `S11` `verify:` `pytest src/cadrumo/application/ledger/tests/test_public_definition_identity.py` -> `pass`
- `S12` `M` `src/cadrumo/llm/tests/test_local_text_reader_wiring.py`
- `S12` `M` `src/cadrumo/application/ledger/tests/test_checks_run_stamp.py`
- `S12` `M` `src/cadrumo/application/ledger/tests/test_establishment_ladder.py`
- `S12` `M` `src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py`
- `S12` `M` `src/cadrumo/application/ledger/tests/test_no_label_regex_reader.py`
- `S12` `M` `src/cadrumo/application/ledger/tests/test_preflight_iva_issue_mapping_totality.py`
- `S12` `verify:` `pytest <the five repointed modules>` -> `pass`
