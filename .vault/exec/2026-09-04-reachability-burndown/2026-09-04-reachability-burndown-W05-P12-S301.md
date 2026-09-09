---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3bdb51ccb0a5bf06002377b750ec2c374433898b1000d1d254ef981a8a13a8b2'
step_id: 'S301'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the decimal parsing and coercion AST enrollment census, its private call-shape engine, production path/function adjudication ledger, copied source fixtures, and residual-backlog prose; retain direct decimal behavior at canonical grammar and live input boundaries.

## Scope

- `decimal enrollment inventory cluster`
- `stale test references`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_decimal_enrollment_inventory.py`
- `D` `src/cadrumo/tests/_decimal_parse_inventory.py`
- `M` `src/cadrumo/tests/test_text_fold_enrollment_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S301.md`
- `verify:` `rg -n "test_decimal_enrollment_inventory|_decimal_parse_inventory|_STRING_PARSE_EXEMPTIONS|string_parse_decimal_violations" pyproject.toml justfile dev .github src -g "!dev/.logs/**"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact production detector remains red on the campaign's live findings; deleting this test-only detector cluster does not classify, exempt, or suppress them.
