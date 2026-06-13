---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m840-standardization-plan]]'
---



# `schema-hardening-m840-standardization` inventory

Modelo 840 is the largest remaining root-level single-file modelo after
the completed M036 standardization. It has one revision,
`2003-y-siguientes`, and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `840.toml`: empty.
- Existing `840/` directory: absent.
- Root-level single-file order at inventory time: `840.toml`,
  `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-20.
- `revisions/2003-y-siguientes/revision.toml`: lines 21-36.
- `casillas/0001-casillas.toml`: lines 37-60.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 61-71.
- `live_cross_references/0001-live-cross-references.toml`: lines 72-115.
- `application_links/0001-application-links.toml`: lines 116-148.
- `filing_schedules/0001-filing-schedules.toml`: lines 149-156.
- `extraction_profiles/0001-declaracion-pdf.toml`: lines 157-183.
- `constructs/0001-constructs.toml`: lines 184-211.

Expected focused verification surface:

- `test_modelo_840_registry.py`
- `test_loader_directory_mode.py`
- `test_parser_boundary.py::test_parser_extracts_modelo_840_synthetic_fixture_targets`
