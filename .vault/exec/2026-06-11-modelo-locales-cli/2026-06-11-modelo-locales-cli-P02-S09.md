---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S09'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S09 add modelo set command

Scope: `src/aeat/locales/cli.py`.

## Description

- Add `python -m aeat.locales modelo set`.
- Type the locale and translation field arguments as closed enums.
- Validate the schema key against registry-backed inventory before writing.
- Route all TOML mutation through `ModeloLocaleManager`.

## Outcome

The locale CLI can now set one validated modelo schema-local translation leaf without hand-editing locale TOML.

## Notes

Focused verification passed against a temporary registry root using a revision-local casilla label.
