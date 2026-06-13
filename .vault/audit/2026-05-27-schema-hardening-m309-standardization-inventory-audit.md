---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m309-standardization-plan]]'
---



# `schema-hardening-m309-standardization` inventory

Modelo 309 is the largest remaining root-level single-file modelo after
the completed M347 standardization. It has one revision,
`2004-y-siguientes`, and no existing directory-form registry source.

Pre-edit target checks:

- Scoped diff for `309.toml`: empty.
- Existing `309/` directory: absent.
- Root-level single-file order at inventory time: `309.toml`,
  `360.toml`, `036.toml`, `840.toml`, `308.toml`.

Mechanical split map:

- `manifest.toml`: lines 1-18.
- `revisions/2004-y-siguientes/revision.toml`: lines 19-32.
- `workbook_parity_refs/0001-workbook-parity-refs.toml`: lines 33-42.
- `verification_expectations/0001-verification-expectations.toml`: lines 43-57.
- `bindings/0001-iva-ledger-bindings.toml`: lines 58-87.
- `casillas/0001-iva-casillas.toml`: lines 88-126.
- `formulas/0001-formulas.toml`: lines 127-141.
- `casillas/0002-declarante-casillas.toml`: lines 142-165.
- `live_cross_references/0001-live-cross-references.toml`: lines 166-209.
- `application_links/0001-application-links.toml`: lines 210-289.
- `filing_schedules/0001-filing-schedules.toml`: lines 290-297.
- `constructs/0001-constructs.toml`: lines 298-344.
- `completeness_manifest/0001-completeness-manifest.toml`: lines 345-363.

The two casilla ranges stay in separate ordered fragments so the mechanical
reconstruction preserves the original source order around the formula block.

Expected focused verification surface:

- `test_modelo_309_registry.py`
- `test_loader_directory_mode.py`
- `test_ledger_iva_aggregation_binding.py`
- `test_iva_ledger.py` targeted Modelo 309 binding tests.
