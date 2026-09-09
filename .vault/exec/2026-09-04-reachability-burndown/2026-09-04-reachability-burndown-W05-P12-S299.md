---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:7daef7a0c057973d8a7bd41e1abaaa61ef3a2e93022d9ba82986f2662af56371'
step_id: 'S299'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the static test-rooted symbol-use graph, its dynamic-dispatch exemption ledger, copied reachability engine, and self-tests; retain executed coverage and the canonical production reachability audit as the owning signals.

## Scope

- `test-exercise static proxy`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_every_module_has_test_coverage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S299.md`
- `verify:` `rg -n "test_every_module_has_test_coverage|_DYNAMIC_DISPATCH_EXEMPTIONS|test_every_production_module_is_exercised_by_a_test" pyproject.toml justfile dev .github src -g "!dev/.logs/**"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact detector remains red on the campaign's production findings; this test-only deletion does not classify, exempt, or suppress them.
