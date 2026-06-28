---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m036-standardization-plan]]'
---



# `schema-hardening-m036-standardization` inventory

Modelo 036 is the largest remaining root-level single-file modelo after
the completed M360 standardization. It has one revision,
`2025-02-03-y-siguientes`, and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `036.toml`: empty.
- Existing `036/` directory: absent.
- Root-level single-file order at inventory time: `036.toml`,
  `840.toml`, `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-22.
- `revisions/2025-02-03-y-siguientes/revision.toml`: lines 23-40.
- `bindings/0001-profile-census-status.toml`: lines 41-61.
- `casillas/0001-casillas.toml`: lines 62-98.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 99-114.
- `verification_expectations/0001-verification-expectations.toml`: lines 115-133.
- `application_links/0001-application-links.toml`: lines 134-193.
- `filing_schedules/0001-filing-schedules.toml`: lines 194-207.
- `extraction_profiles/0001-declaracion-pdf.toml`: lines 208-253.
- `constructs/0001-constructs.toml`: lines 254-282.
- `completeness_manifest/0001-completeness-manifest.toml`: lines 283-301.

Expected focused verification surface:

- `test_modelo_036_registry.py`
- `test_census_modelo_registry_data.py`
- `test_census_modelo_foundation.py`
- `test_queries.py`
- `test_loader_directory_mode.py`
- `test_parser_boundary.py::test_parser_extracts_modelo_036_synthetic_fixture_targets`
