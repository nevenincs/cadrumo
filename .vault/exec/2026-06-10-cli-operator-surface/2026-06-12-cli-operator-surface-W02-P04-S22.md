---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-07-17'
body_hash: 'sha256:6b63156dd1b574cb1613a4228a626b0547b75d8b23bf039978a5e42588ca0688'
step_id: 'S22'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W02.P04.S22 Correct-Ledger Restore Documentation

Scope: verify the correct-ledger guide documents restore and removes permanent-stash wording.

## Description

- Verified `docs/how-to/correct-ledger-entries.md` says stash and archive are reversible.
- Verified the guide includes a restore section and bulk-stash recovery example.
- Verified the old "Both are permanent" limitation is absent.

## Outcome

S22 is closed. The guide now matches the restore-capable lifecycle surface.

## Checks

- `rg "Both are permanent|restore|reversible" docs/how-to/correct-ledger-entries.md`
