---
tags:
  - '#exec'
  - '#core-authority'
step_id: S24
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P07.S24 — DELETE-007/008 ripgrep gate: BLOCKED

## Blocking Condition

The plan's own execution gate "after ripgrep confirms zero callers" was not
satisfied. All three filename constants have active callers:

- `ASSETS_LEDGER_FILENAME`: defined at line 26 and used at line 111 of
  `adapters/persistence/profile/assets.py`.
- `ASSETS_AMORTIZATION_LEDGER_FILENAME`: defined at line 27 and used at
  line 212 of `adapters/persistence/profile/assets.py`.
- `INVENTORY_LEDGER_FILENAME`: defined at line 26 and used at line 127 of
  `adapters/persistence/profile/inventory.py`.

## Resolution

Step left unchecked. No code changes made. These constants are referenced
within their own persistence adapter modules and are not dead code. The
tracker's "zero consumer" claim was incorrect. Deferred to a future campaign.
