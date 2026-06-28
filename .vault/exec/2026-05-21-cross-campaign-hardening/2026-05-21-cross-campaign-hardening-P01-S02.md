---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P01.S02'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P01.S02`

Closed EXIM-1: `ModeloDraft` export/verify no longer drops casilla
legal/source provenance.

- Modified: `src/aeat/domain/filing/_schema.py`
- Modified: `src/aeat/domain/filing/__init__.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/application/modelo/_export.py`
- Modified: `src/aeat/application/modelo/test_export.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added `ModeloCasillaProvenance` and the `ModeloDraft.casilla_provenance`
field. Production `build_draft` now populates this tuple from the same
registry snapshot used to build the draft values.

The declaration export path carries provenance into
`DeclaracionExportResult.casilla_provenance`. The verify path carries
all checked casilla provenance into `DeclaracionVerifyResult` and
specifically grounds drift rows with
`mismatched_casilla_provenance`. The high-level
`ModeloExportResult` also carries `casilla_provenance`, so the existing
CLI JSON render path surfaces the field through `model_dump(mode="json")`.

The new tests use the real registry-backed schema provider and parser;
they do not introduce fakes, mocks, monkeypatch shortcuts, skipped tests,
or copied business logic.

While closing the row, `vaultspec-core` exposed that the new
cross-campaign plan used phase-local `S01`, `S02`, etc. identifiers and
step rows without parser-compatible scopes. Repaired the plan row format
and renumbered step ids monotonically from `S01` through `S45`, then
closed this row via the canonical `S02` id.

## Tests

`uv run ruff check src/aeat/domain/filing/_schema.py src/aeat/domain/filing/__init__.py src/aeat/application/filing/__init__.py src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py` passed.

`uv run pytest -q src/aeat/application/filing/test_export.py src/aeat/application/modelo/test_export.py::test_export_result_json_surfaces_casilla_provenance` passed with 35 tests in 51.69s.

`uv run pytest -q src/aeat/domain/filing/test_secure_storage_roundtrip.py src/aeat/domain/filing/test_roundtrip_anti_tautology.py src/aeat/domain/filing/test_amendment_roundtrip.py` passed with 5 tests in 1.91s.

`uv run pytest -q src/aeat/application/modelo/test_export.py` passed with 9 tests in 21.96s.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-20-registry-authority-flow-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P01-S02.md src/aeat/domain/filing/_schema.py src/aeat/domain/filing/__init__.py src/aeat/application/filing/__init__.py src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py src/aeat/application/modelo/_export.py src/aeat/application/modelo/test_export.py` passed.
