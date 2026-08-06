---
tags: ['#exec', '#modelo-locales-cli']
date: '2026-06-11'
modified: '2026-07-17'
body_hash: 'sha256:4d5f9870ebb348db5bbf9b034a8ed33f3713e9e591a96592ab93f3267bf21a0c'
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
