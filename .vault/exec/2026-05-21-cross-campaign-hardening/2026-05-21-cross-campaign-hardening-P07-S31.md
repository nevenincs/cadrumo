---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P07.S31'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P07.S31`

Closed EXIM-6.

- Verified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Verified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Verified the `verify_export` path already computes
`unchecked_casillas` as draft casillas minus parser-checked casillas.
Added focused coverage for the Modelo 130 exported-layout verdict:
`saldo-negativo-fin-periodo` remains reported as unchecked while the
overall file verdict is still `MATCH` and `mismatched_casillas` stays
empty.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`uv run ruff check src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py` passed.

`uv run pytest -q src/aeat/application/filing/test_export.py::test_verify_reports_unchecked_reserved_or_derived_casillas src/aeat/application/filing/test_export.py::test_verify_matches_exported_modelo_130_layout` passed with 2 tests in 26.21s.

`uv run pytest -q src/aeat/application/filing/test_export.py` passed with 40 tests in 67.72s.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S31` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P07-S31.md src/aeat/application/filing/_export.py src/aeat/application/filing/test_export.py src/aeat/locales/ca.yml src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/hu.yml` passed.
