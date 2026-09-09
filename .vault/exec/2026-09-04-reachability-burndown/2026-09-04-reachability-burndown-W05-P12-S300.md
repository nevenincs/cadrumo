---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f63e9a27ac57f64072d785174dc0f5d22f6457441a3ca8181ffcffb57b2ff2de'
step_id: 'S300'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the classification-comparison AST enrollment census, its production function/path exemptions, copied source fixtures, and exported detector vocabulary; retain the canonical runtime predicate and storage-boundary behavior.

## Scope

- `classification enrollment inventory`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_classification_enrollment_inventory.py`
- `M` `src/cadrumo/adapters/persistence/storage/schema_lineage.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S300.md`
- `verify:` `rg -n "test_classification_enrollment_inventory|_CLASSIFICATION_COMPARE_EXEMPTIONS|classification_compare_violations" pyproject.toml justfile dev .github src -g "!dev/.logs/**"` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact production detector remains the owning campaign signal; deleting this test-only census does not classify, exempt, or suppress its findings.
