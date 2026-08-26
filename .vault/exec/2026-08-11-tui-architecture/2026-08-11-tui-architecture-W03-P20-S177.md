---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d71d1d76e68c00142e24df5b94bedab516235089f9512e8f92804ae75252c71e'
step_id: 'S177'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove aeat_nif_iva_oracle remains public with locally defined symbols and direct consumer imports

## Scope

- `src/cadrumo/domain/calculations/registry/aeat_nif_iva_oracle.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py -n0` -> `pass`

## Notes

Every exported oracle symbol is locally defined, and the sweep by symbol
confirmed every consumer already imports the defining module directly. The
proof now asserts both, so a later package binding or borrowed re-export reds.
