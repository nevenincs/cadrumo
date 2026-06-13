---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S07'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
---

# P02.S07 add modelo audit command

Scope: `src/aeat/locales/cli.py`.

## Description

- Add `python -m aeat.locales modelo audit`.
- Print coverage for one locale, modelo, and revision.
- Print missing and stale drift rows.
- Exit nonzero when coverage is incomplete or drift exists.

## Outcome

The locale CLI can now enforce schema-local modelo translation drift checks through the manager contract.

## Notes

Focused verification passed against committed M130, where audit exits cleanly for complete English coverage.
