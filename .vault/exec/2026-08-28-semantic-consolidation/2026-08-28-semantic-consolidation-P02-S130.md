---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:5ed1e43e1e5e79a17089ca2fc3d8b3b3ffa7d7c142f9f7ae1356707c4477bcb9'
step_id: 'S130'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Route the ledger export amount check through the parser's own signed axis instead of comparing against zero beside the payload

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_payloads.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_ledger_payloads.py`
- `verify:` probed `0`, `12.34`, empty accepted; `-1`, `NaN`, `abc`, `1e3` refused

## Notes

The validator parsed the amount and then compared the result against zero. The
sign rule is the canonical parser's own `signed` axis, so it now asks
`try_parse_canonical_decimal(value, signed=False)` -- the shape the IVA wallet
payload already used for the same field family. A ledger amount is a magnitude
and direction lives on its own enum, so non-negativity is a property of the
grammar rather than a threshold a payload picks.
