---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S74'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P08.S74 AEAT Sede Declarations Verification

Scope: `src/aeat/adapters/outbound/aeat/sede/tests src/aeat/entrypoints/cli/tests/test_live*`.

## Description

- Verify declarations adapter behavior after schema, listbox, and filed-observation helper extraction.
- Verify `_declarations.py` still resolves moved contract and private test-hook symbols from the new private modules.
- Verify no application, entrypoint, or adapter consumer imports `_declarations_schema`, `_declarations_listbox`, or `_declarations_observations` directly.
- Run non-live application tests adjacent to declarations register capture.
- Run ruff over touched declarations modules.

## Outcome

Verification passed for the declarations surface:

- `uv run --no-sync pytest src/aeat/adapters/outbound/aeat/sede/tests/test_declarations.py src/aeat/adapters/outbound/aeat/sede/tests/test_declarations_locale.py -q --tb=short` passed with 69 tests.
- `uv run --no-sync pytest src/aeat/application/live/tests/test_expedientes.py src/aeat/application/live/tests/test_filed_bulk_capture.py -q --tb=short` passed with 17 tests.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_declarations_observations.py src/aeat/adapters/outbound/aeat/sede/_declarations_listbox.py src/aeat/adapters/outbound/aeat/sede/_declarations_schema.py` completed cleanly.
- Smoke import confirmed `Declaracion` resolves from `_declarations_schema`, `_parse_listbox` resolves from `_declarations_listbox`, and `_temporary_sensitive_pdf_path` resolves from `_declarations_observations`.
- `rg` found no application, entrypoint, or adapter imports into `_declarations_schema`, `_declarations_listbox`, or `_declarations_observations`.
- `_declarations.py` is 1243 lines after the split; `_declarations_observations.py` is 522 lines; `_declarations_listbox.py` is 137 lines; `_declarations_schema.py` is 29 lines.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-05-codebase-monolith-decomposition-plan.md` completed with only existing warning `PLAN022`.

## Notes

The plan warning `PLAN022` remains the known canonical-id monotonicity warning from earlier plan structure, not a declarations decomposition failure.
