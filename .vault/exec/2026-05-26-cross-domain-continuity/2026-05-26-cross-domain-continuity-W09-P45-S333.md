---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S333'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R9-ZSOFIA-F inconsistent help-text localisation within a single command  -  overview calendar --help has ONE option (--all-profiles) translated to hu but other options remain english

## Scope

- `either localise all options or none`
- `partial localisation is more confusing than uniform`
- `src/aeat/entrypoints/cli/_overview.py`

## Description

- Ground the issue with `vaultspec-rag` against overview calendar Typer help and the language-flag help-honesty tests.
- Confirm the live `overview calendar --help` path already localizes the command and custom option descriptions when invoked with Hungarian output language.
- Add a regression test that drives the real console with `--language hu app overview calendar --help` and asserts the custom overview calendar help strings are Hungarian, not English.
- Treat the generic Typer `--help` row and section chrome as the broader S332 scope rather than broadening S333 beyond the mixed custom-option defect.

## Outcome

- No production code change was required for S333.
- The regression now locks the previously mixed custom option descriptions on `overview calendar --help`.
- Runtime inspection showed the custom `--from`, `--to`, `--allow-incomplete`, `--show-suppressed`, `--all-profiles`, and command help text render in Hungarian under `--language hu`.
- The S333 plan row is closed as a focused regression/verification step.

## Notes

- Validation: `uv run --no-sync ruff check src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py`; `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_language_flag_help_honesty.py::test_hungarian_overview_calendar_help_localises_custom_options_together -q`; `uv run --no-sync aeat --language hu app overview calendar --help`.
- Residual: Typer's built-in `--help` option description still renders in English; that is tracked by S332's global help-localization scope.
