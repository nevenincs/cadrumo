---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m360-standardization-plan]]'
---



# `schema-hardening-m360-standardization` inventory

Modelo 360 is the largest remaining root-level single-file modelo after
the completed M309 standardization. It has one revision,
`2010-y-siguientes`, and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `360.toml`: empty.
- Existing `360/` directory: absent.
- Root-level single-file order at inventory time: `360.toml`,
  `036.toml`, `840.toml`, `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-19.
- `revisions/2010-y-siguientes/revision.toml`: lines 20-34.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 35-44.
- `casillas/0001-casillas.toml`: lines 45-68.
- `parameters/0001-refund-thresholds.toml`: lines 69-104.
- `live_cross_references/0001-live-cross-references.toml`: lines 105-148.
- `application_links/0001-application-links.toml`: lines 149-188.
- `filing_schedules/0001-filing-schedules.toml`: lines 189-196.
- `deadline_windows/0001-deadline-windows.toml`: lines 197-220.
- `bindings/0001-refund-operation-row-bindings.toml`: lines 221-286.
- `constructs/0001-constructs.toml`: lines 287-324.

Expected focused verification surface:

- `test_modelo_360_registry.py`
- `test_loader_directory_mode.py`
- `test_detail_record_row_builders.py`
- `test_detail_record_modelo_coverage.py`
- `test_row_set_assembly.py`
- `test_detail_record_round_trip.py`
