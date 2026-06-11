---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S01'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P01.S01 define registry-local locale manager models

Scope: `src/aeat/locales/_modelo_manager.py`.

## Description

- Add typed schema-local locale scopes, field kinds, and drift kinds.
- Add pydantic records for locale file targets, parsed translation files, inventory keys, drift rows, and coverage rows.
- Export the contract types through the `aeat.locales` package boundary.

## Outcome

The modelo localization CLI now has a typed contract for registry-local TOML targets and coverage reporting. The contract preserves the runtime split between modelo-level continuity-key translations and revision-level casilla-key translations.

## Notes

Focused verification passed with `ruff check` and an import probe. A first attempt to subclass the registered project error base failed because new registered errors require central error-code enrollment; this step kept the manager-local error as `ValueError` pending a later CLI error-shaping decision.
