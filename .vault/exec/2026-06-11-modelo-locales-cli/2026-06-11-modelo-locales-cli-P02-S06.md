---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S06'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S06 add modelo Typer sub-application

Scope: `src/aeat/locales/cli.py`.

## Description

- Register a nested `modelo` Typer application under `python -m aeat.locales`.
- Export the nested app for focused CLI tests.
- Keep the existing core locale commands unchanged.

## Outcome

The locale CLI now has a dedicated modelo schema-local command group that will host audit, scaffold, set, remove, and coverage verbs.

## Notes

Focused verification passed for `ruff check`, `python -m aeat.locales --help`, and `python -m aeat.locales modelo --help`.
