---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S13'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P03.S13 add registry locale manager behavior tests

Scope: `src/aeat/locales/tests/test_modelo_manager.py`.

## Description

- Add real registry-backed manager tests using a temp copy of bundled Modelo 130 data.
- Cover coverage inventory, scaffold preservation, stale-key cleanup, set/remove writes, unknown-key refusal, and path-like identifier refusal.
- Fix scaffold write behavior so missing target files are created only when the target has expected translation keys.

## Outcome

`ModeloLocaleManager` now has focused tests for its core registry-local authoring contract, and scaffold no longer creates empty modelo-level locale TOML files for scopes with no expected keys.

## Notes

Verification passed with `ruff check src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/_modelo_manager.py` and `pytest src/aeat/locales/tests/test_modelo_manager.py -q`.
