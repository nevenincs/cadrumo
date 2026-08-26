---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:959526e9b3305be96b6737462b50196a9debcdab9da79d6c32e7b76c6018e871'
step_id: 'S177'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
