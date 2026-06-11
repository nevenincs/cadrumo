---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S14'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P03.S14 add modelo CLI integration tests

Scope: `src/aeat/locales/tests/test_modelo_cli.py`.

## Description

- Add Typer integration tests for modelo coverage, audit, scaffold check, scaffold write, set, remove, and invalid-key refusal.
- Run the commands against a temp registry root populated with real bundled Modelo 130 data.
- Assert check mode is non-writing and scaffold avoids empty modelo-scope files.

## Outcome

The `python -m aeat.locales modelo` command surface now has focused integration coverage for its primary campaign workflows.

## Notes

Verification passed with `ruff check` for the touched locale CLI, manager, and tests; `pytest src/aeat/locales/tests/test_modelo_cli.py -q -m integration`; and `pytest src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/tests/test_modelo_cli.py -q -m "unit or integration"`.
