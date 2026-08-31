---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:e0e9aec22b62df6a4ae9cc332929471cd098b4499e14a322252495b97e9ca42f'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

# `ci-lane-deconflation` audit: `P05 S123 code review`

## Scope

Independent review of P05.S123 at `dbf6981efc216c9b286b943e2ea8d61635d4d77c` and the verified predecessor `0b578b3458c40279cd68ee765ccdc1b0b997a93a`: the typed-record, payload-projection and coverage extraction; every direct consumer move; Sede declaration observer reference; package allowlist; and size evidence. `calc_sheets_pull.py` owns only the live adapter and imports the moved records as private aliases, with no facade or re-export. Direct runtime and test consumers name the records or coverage defining modules. Identity checks passed, the pull target measures 1,228 against the 1,250 default, and no size baseline changed. `test_verify_pull_coverage.py` plus `test_package_module_allowlist.py` passed 8 tests.

## Findings

### stale-record-doc-targets | low | Record docstrings still resolve through the removed defining path

The record extraction updates runtime consumers and the Sede observer's coverage link, but leaves eight Sphinx targets naming record types under `calc_sheets_pull.py`: three in `application/calculations/row_set_assembly.py` for `RowSetEdit` or `RowSetCellEdit`, and five in `calc_sheets_pull.py` for `OperatorEdit`, `BindingEdit`, or `RelationEdit`. The adapter deliberately has no public re-export, so those targets are stale after the move and should name `calc_sheets_pull_records` directly.

## Recommendations

- For `stale-record-doc-targets`, update the eight record links to the canonical `calc_sheets_pull_records` module and rerun the affected documentation reference gate when S53 performs its sweep.

