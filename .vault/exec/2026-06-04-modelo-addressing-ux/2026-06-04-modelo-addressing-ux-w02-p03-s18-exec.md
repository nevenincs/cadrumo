---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:dbb19ca33f87ea0217341df68d32038395af3fc0abb8f349c65ddb0edae84ca1'
step_id: 'S18'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P03.S18 discovery output coverage

Scope:
- `src/aeat/entrypoints/cli/test_modelo_work_ux.py`

## Description

- Cover natural-key `work status` output.
- Cover pointer-rich `work list` output after a real calculation.
- Cover natural-key `work revisions` filtering after a real calculation.

## Outcome

The discovery UX has real-behavior regression coverage over the CLI and storage-backed modelo lifecycle.

## Notes

- Focused pytest lane passed with six CLI tests.
