---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P02.S08'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
---

# `cross-campaign-hardening` `P02.S08`

Closed WCLI-3 for `_modelo.py`: registered domain errors no longer
cross the Typer boundary through raw `str(exc)`.

- Modified: `src/aeat/entrypoints/cli/_modelo.py`
- Modified: `src/aeat/entrypoints/cli/test_modelo.py`
- Modified: `.vault/plan/2026-05-21-cross-campaign-hardening-plan.md`

## Description

Added `_bad_parameter_from_error`, a local `_modelo.py` helper that
constructs `typer.BadParameter(resolve_error_message(exc))`. Replaced
the exact `typer.BadParameter(str(exc))` sites in `_modelo.py` with
that helper so registered application/domain errors keep their localized
fallback text when they carry no positional message.

Added direct coverage for the helper using a registered no-argument
`WorkUnitNotFoundError`, proving it produces a non-blank
`typer.BadParameter`. While running the touched CLI module, the gate
also exposed a current output-shape drift from the existing
`input_channel` column on `bindings list`; updated that assertion to
match the current CLI surface.

No fakes, mocks, monkeypatches, skipped tests, or copied business logic
were introduced.

## Tests

`rg -n "BadParameter\\(str\\(exc\\)\\)" src/aeat/entrypoints/cli/_modelo.py` found no remaining raw `str(exc)` conversions in `_modelo.py`.

`uv run ruff check src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py` passed.

`uv run pytest -q src/aeat/entrypoints/cli/test_modelo.py::test_modelo_bad_parameter_helper_renders_registered_errors` passed with 1 test in 2.01s.

`uv run pytest -q src/aeat/entrypoints/cli/test_modelo.py` passed with 77 tests in 41.16s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S08` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P02-S08.md src/aeat/entrypoints/cli/_modelo.py src/aeat/entrypoints/cli/test_modelo.py` passed.
