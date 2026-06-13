---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S16'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P03.S16 add registry-loader roundtrip coverage

Scope: `src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py`.

## Description

- Add registry-loader coverage for manager-written schema-local locale TOML.
- Write an English label through `ModeloLocaleManager`.
- Load the copied real Modelo 130 registry directory through the existing registry loader.
- Assert the localized English label is available while the official Spanish schema label remains intact.

## Outcome

The registry loader test suite now proves that TOML emitted by the new locale manager is consumed by the existing runtime localization backend.

## Notes

Verification passed with `ruff check src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py`, `pytest src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py -q -m unit`, and the combined locale/registry focused test run.
