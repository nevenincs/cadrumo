---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:b9e93d6f51bb76e0b0c070444340669449008bcf13f3b262fb64808dfab75517'
step_id: 'S320'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the retired decimal-module and alias tombstone gate with embedded bindings

## Scope

- `decimal uniqueness tombstone`
- `focused canonical decimal grammar`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_canonical_decimal_string_uniqueness.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/inbound/financial/tests/test_decimal.py src/cadrumo/core/decimal/tests/test_grammar.py` -> `pass`
