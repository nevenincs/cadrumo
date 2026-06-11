---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
step_id: 'S10'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S10 add modelo remove command

Scope: `src/aeat/locales/cli.py`.

## Description

- Add `python -m aeat.locales modelo remove`.
- Type the locale and translation field arguments as closed enums.
- Remove one existing schema-local translation leaf through `ModeloLocaleManager`.
- Support stale-key removal by locating existing leaves in the managed modelo and revision targets.

## Outcome

The locale CLI can now remove one schema-local translation leaf without hand-editing locale TOML.

## Notes

Focused verification passed against a temporary registry root using a revision-local casilla label.
