---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:d7f88dea7727fcbfbd815d88420155ab11482200aebcaeb744ac01e06524a452'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `test-reconciliation-sweep` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
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

