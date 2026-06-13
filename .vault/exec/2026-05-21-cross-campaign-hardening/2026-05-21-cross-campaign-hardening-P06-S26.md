---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P06.S26'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P06.S26`

Closed EXIM-5: filing export tests now cover no-layout modelos,
binding-row layouts, and computed export fields.

- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added no-layout negative coverage by deriving a real
`RegistrySchemaProvider` from the Modelo 130 fixture and replacing only
the selected subview's `export_layout_ids` / `export_layouts` with empty
tuples. `export_draft` now has a direct regression proving it refuses a
layout-less modelo without writing an output file, and `verify_export`
has a regression proving the same shape reports `MISSING` with the
`filing.export.missing_registry_layout` narrative.

Binding-row layout coverage already existed through the Modelo 131
DPA/DID export assertions. Computed export-field coverage is now
explicit: the Modelo 111 registry-layout test asserts the computed
`envelope_closing_tag` footer is rendered as `</T111020261T0000>`.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py` passed.

`uv run pytest -q src/aeat/application/filing/test_export.py::test_export_refuses_modelo_without_registry_layout src/aeat/application/filing/test_export.py::test_verify_reports_missing_for_modelo_without_registry_layout src/aeat/application/filing/test_export.py::test_export_writes_modelo_111_registry_layout src/aeat/application/filing/test_export.py::test_export_writes_modelo_131_binding_derived_layout` passed with 4 tests in 46.53s.

`uv run pytest -q src/aeat/application/filing/test_export.py` passed with 36 tests in 61.74s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S26` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P06-S26.md src/aeat/application/filing/test_export.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed with only existing CRLF normalization warnings for the plan and locale files.
