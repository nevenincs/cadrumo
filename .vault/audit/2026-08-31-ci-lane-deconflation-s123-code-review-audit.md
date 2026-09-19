---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5a2f821bb0f984acdf765c3233e1de4908d032f57de22c57dd1cff712c4daf4e'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S123 code review`

## Scope

Independent review of P05.S123 at `dbf6981efc216c9b286b943e2ea8d61635d4d77c` and the verified predecessor `0b578b3458c40279cd68ee765ccdc1b0b997a93a`: the typed-record, payload-projection and coverage extraction; every direct consumer move; Sede declaration observer reference; package allowlist; and size evidence. `calc_sheets_pull.py` owns only the live adapter and imports the moved records as private aliases, with no facade or re-export. Direct runtime and test consumers name the records or coverage defining modules. Identity checks passed, the pull target measures 1,228 against the 1,250 default, and no size baseline changed. `test_verify_pull_coverage.py` plus `test_package_module_allowlist.py` passed 8 tests.

## Findings

### stale-record-doc-targets | low | Record docstrings still resolve through the removed defining path

The record extraction updates runtime consumers and the Sede observer's coverage link, but leaves eight Sphinx targets naming record types under `calc_sheets_pull.py`: three in `application/calculations/row_set_assembly.py` for `RowSetEdit` or `RowSetCellEdit`, and five in `calc_sheets_pull.py` for `OperatorEdit`, `BindingEdit`, or `RelationEdit`. The adapter deliberately has no public re-export, so those targets are stale after the move and should name `calc_sheets_pull_records` directly.

### non-reproducible-original-lint-evidence | high | The original extraction lint checks still use placeholders

The S123 execution record lines 43 and 44 retain `ruff check <S123 paths>` and `ruff format --check <S123 paths>`. The later repair records exact ruff commands for only `row_set_assembly.py` and `calc_sheets_pull.py`; it cannot establish the original extraction's full lint scope. The exact original file list must replace both placeholders before the step can claim reproducible lint evidence.

### repair-verification | low | The eight moved-record links are now canonical

Commit `cd2c75755fee6f0061a68d817deead3488c0ac1a` changes the exact five `calc_sheets_pull.py` and three `row_set_assembly.py` links, and the current stale-reference search returns no old record targets. `test_qualified_docstring_references_resolve.py` remains red only in its four unrelated assertions: unresolved user-profile/storage targets, an unrelated scan-population threshold, pydantic-field resolution, and a lazy user-profile resolver fixture. No repaired S123 target appears in that output.

### final-evidence-repair | low | The outstanding placeholder evidence is resolved

Record-only commit `924b08e4f117f7f9bb777bb3bd8b5c4c3460ba82` replaces both placeholder lint entries with the exact 19 original S123 source/test paths and their recorded passing results. No placeholder remains, and the commit changes no source, plan, or size baseline. The prior high evidence finding is resolved.

## Recommendations

- For `stale-record-doc-targets`, update the eight record links to the canonical `calc_sheets_pull_records` module and rerun the affected documentation reference gate when S53 performs its sweep.
- For `non-reproducible-original-lint-evidence`, replace both placeholder lint commands with the exact original S123 source/test path list, rerun that command set, and record its actual exit result.
