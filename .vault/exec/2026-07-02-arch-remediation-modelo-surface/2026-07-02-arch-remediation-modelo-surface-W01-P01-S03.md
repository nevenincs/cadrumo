---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:a021723ed6fcc8a55dcd9be9ca695ebf04c41c4599b9a9a57f60e3112df7004c'
step_id: 'S03'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Delete the M210 sentinel rate constants from the domain formula runtime in the same atomic change that lands the typed outcome, leaving no tolerance window in which both channels exist

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Delete the M210 negative Decimal sentinel constants and public aliases from the formula runtime.
- Remove sentinel exports from the registry package surface.
- Sweep M210 sentinel wording from the touched runtime and M210 helper/test comments.

## Outcome

No `M210_*_SENTINEL`, `M210_RATE_SENTINELS`, or `_rewrite_m210_sentinels` symbols remain under `src`.

## Notes

The sentinel deletion landed in the same patch set as the typed outcome channel.
