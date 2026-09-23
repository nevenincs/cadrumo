---
tags:
  - '#exec'
  - '#iva-workflow'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:aad78cc97212a2d92d92ad5b05631b0ff2241dd329b9dc6d2cecb84eb613d6dd'
related:
  - "[[2026-09-23-iva-workflow-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `iva-workflow` ledger

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
- `S01` `M` `src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py`
- `S01` `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `S01` `M` `src/cadrumo/application/filing/export_producer.py`
- `S01` `M` `src/cadrumo/application/filing/projection.py`
- `S01` `M` `src/cadrumo/application/modelo/m303_filing_evidence.py`
- `S01` `M` `src/cadrumo/application/filing/tests/test_producer_snapshot.py`
- `S01` `verify:` `pytest -m 'unit or integration' application/filing/tests domain/modelos/tests + M303 evidence suites: 707 passed` -> `pass`
- `S02` `M` `src/cadrumo/application/modelo/m303_ordinary_evidence_coordinate.py`
- `S02` `M` `src/cadrumo/application/modelo/m303_ordinary_filing_evidence_authoring.py`
- `S02` `M` `src/cadrumo/application/modelo/m303_exonerado_390_applicability_attestation.py`
- `S02` `M` `src/cadrumo/application/modelo/preconditions.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_ordinary_filing_evidence_authoring.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_exonerado_390_applicability_attestation.py`
- `S02` `verify:` `S02-S05 population pytest -m 'unit or integration': 2210 passed, 7 pre-existing failures (all fail at clean HEAD 1cf639c287)` -> `pass`
- `S03` `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `S03` `M` `src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py`
- `S03` `M` `src/cadrumo/adapters/persistence/storage/tests/test_m303_calculate_evidence_admission.py`
- `S03` `verify:` `conformance and calculate-admission tests incl. pending v1 and v2 refusal` -> `pass`
- `S04` `M` `src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_app_quickfile.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/modelo_work_command_specs.py`
- `S04` `M` `src/cadrumo/entrypoints/cli/_app_quickfile_command_specs.py`
- `S04` `M` `src/cadrumo/locales/en/cli.yml`
- `S04` `M` `src/cadrumo/locales/es/cli.yml`
- `S04` `M` `src/cadrumo/locales/ca/cli.yml`
- `S04` `M` `src/cadrumo/locales/hu/cli.yml`
- `S04` `verify:` `M303 CLI, quickfile and dependent CLI tests; dev.locales audit ok in four locales` -> `pass`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/m303_evidence.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/lifecycle.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/modelo/view/overview.py`
- `S05` `M` `src/cadrumo/entrypoints/tui/launcher.py`
- `S05` `M` `src/cadrumo/locales/en/common.yml`
- `S05` `M` `src/cadrumo/locales/es/common.yml`
- `S05` `M` `src/cadrumo/locales/ca/common.yml`
- `S05` `M` `src/cadrumo/locales/hu/common.yml`
- `S05` `verify:` `TUI modelo tests` -> `pass`

## Notes

- `S01` 6 failures in adapters/persistence/profile/tests/test_m303_filing_evidence_validation.py (ModeloProfileReadinessError profile_absent/inactive) reproduce identically at committed source 976971d1be before this Step; pre-existing, reported. 1 failure is the retired-token guard awaiting the error rename.
- `S02` Monthly work for a non-monthly filer was refused by no owner; the authoring now requires the period to belong to a registry filing schedule applicable to the profile (applicable_filing_schedules), grounded in the schedules' RD 1624/1992 art. 71 conditions.
- `S04` The CLI reference is generated at docs build time and has no committed output to regenerate.
- `S05` Whether a period asks the Modelo 390 exemption is a governed fact; the overview first called it outside a pinned scope, which raises in the real TUI. The lifecycle door now resolves it under the pinned authority.

