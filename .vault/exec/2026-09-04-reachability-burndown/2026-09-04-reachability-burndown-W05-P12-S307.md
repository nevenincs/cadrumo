---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:67180d35e62a0c7935d9f7c15bae23be63a56b7f726e95819a8cb6983cbd2f7d'
step_id: 'S307'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the date/boolean parsing AST enrollment engine, its whole-layer exclusions, seeded binding assumptions, production path/line exemptions, detector-authored token vocabulary, and embedded-code probes; retain canonical parser behavior.

## Scope

- `parsing enrollment inventory`
- `focused parsing tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_parsing_enrollment_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S307.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/parsing/tests` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Canonical parser behavior remains covered by 35 focused tests. The removed AST gate inferred provenance through exclusions and adjudications rather than exercising those boundaries; the exact production detector remains red on the wider campaign findings.
