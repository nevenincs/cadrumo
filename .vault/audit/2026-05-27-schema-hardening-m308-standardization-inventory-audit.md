---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
---



# `schema-hardening-m308-standardization` inventory

Modelo 308 is the final remaining root-level single-file modelo after the
completed M840 standardization. It has one revision, `2009-y-siguientes`,
and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `308.toml`: empty.
- Existing `308/` directory: absent.
- Root-level single-file order at inventory time: `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-21.
- `revisions/2009-y-siguientes/revision.toml`: lines 22-38.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 39-48.
- `casillas/0001-casillas.toml`: lines 49-72.
- `live_cross_references/0001-live-cross-references.toml`: lines 73-116.
- `application_links/0001-application-links.toml`: lines 117-156.
- `filing_schedules/0001-filing-schedules.toml`: lines 157-164.
- `constructs/0001-constructs.toml`: lines 165-194.

Expected focused verification surface:

- `test_modelo_308_registry.py`
- `test_loader_directory_mode.py`
