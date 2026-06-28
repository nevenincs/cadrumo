---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m347-standardization-plan]]'
---



# `schema-hardening-m347-standardization` inventory

Modelo 347 is the largest remaining root-level single-file modelo after
the completed M193 standardization. It has one revision,
`2008-y-siguientes`, and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `347.toml`: empty.
- Existing `347/` directory: absent.
- Root-level single-file order at inventory time: `347.toml`,
  `309.toml`, `360.toml`, `036.toml`, `840.toml`, `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-22.
- `revisions/2008-y-siguientes/revision.toml`: lines 23-40.
- `casillas/0001-casillas.toml`: lines 41-64.
- `parameters/0001-threshold.toml`: lines 65-87.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 88-107.
- `live_cross_references/0001-live-cross-references.toml`: lines 109-152.
- `application_links/0001-application-links.toml`: lines 153-192.
- `filing_schedules/0001-filing-schedules.toml`: lines 194-200.
- `deadline_windows/0001-deadline-windows.toml`: lines 202-290.
- `extraction_profiles/0001-declaracion-pdf.toml`: lines 292-331.
- `constructs/0001-constructs.toml`: lines 333-374.

Expected focused verification surface:

- `test_modelo_347_registry.py`
- `test_loader_directory_mode.py`
- `test_parser_boundary.py::test_parser_extracts_modelo_347_synthetic_fixture_targets`
- Application aggregation/applicability tests that reference Modelo 347 can be
  used as follow-up smoke coverage if the registry-focused gate stays green.
