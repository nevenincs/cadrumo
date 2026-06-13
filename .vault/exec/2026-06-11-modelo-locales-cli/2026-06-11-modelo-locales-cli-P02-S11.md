---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S11'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S11 add modelo coverage command

Scope: `src/aeat/locales/cli.py`.

## Description

- Add `python -m aeat.locales modelo coverage`.
- Print translated and required counts for labels and help.
- Keep coverage informational so incomplete translations do not fail the command.

## Outcome

Translation campaigns can now query per-locale, per-modelo, per-revision schema-local coverage through the locale CLI.

## Notes

Focused verification passed against committed M130 complete coverage and committed M303 partial Catalan coverage.
