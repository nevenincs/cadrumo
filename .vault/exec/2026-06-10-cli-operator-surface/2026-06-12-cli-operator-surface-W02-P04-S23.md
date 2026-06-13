---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S23'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S23 Import Guide Restore Documentation

Scope: verify import-bank-statements documents restore and removes permanent-stash wording.

## Description

- Verified `docs/how-to/import-bank-statements.md` describes stash/archive as reversible.
- Verified the guide lists `restore` and includes a restore command example.
- Verified the old permanent-stash sentence is absent.

## Outcome

S23 is closed. Import guidance no longer overstates stash/archive permanence.

## Checks

- `rg "permanent|restore|reversible" docs/how-to/import-bank-statements.md`

