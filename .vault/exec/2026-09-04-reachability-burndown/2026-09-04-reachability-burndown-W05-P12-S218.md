---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:19f9d5e811dfe959abd2d61763714a0fcae0d147fc62c2bcbe44a32b914b8a12'
step_id: 'S218'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the orphaned custody retryable-code declaration census and its hand-maintained owned-package fragments, retryable-code-to-prose map, and stale-entry checks; retain retryability decisions with their authoritative error registrations and the type/AST-derived handler-flattening gate with planted detector teeth.

## Scope

- `Custody retryability census test`
- `authoritative error-code registrations and handler-flattening gate`
- `exact orphan signal`
- `focused gates`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `D` `src/cadrumo/application/user_profile/tests/test_custody_retryable_codes_are_declared.py`
- `M` `src/cadrumo/tests/test_no_handler_flattens_a_divergent_retryability.py`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S218.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/tests/test_no_handler_flattens_a_divergent_retryability.py` -> `pass`
- `verify:` `rg -n "test_custody_retryable_codes_are_declared|_RETRYABLE_BECAUSE|_OWNED_QUALNAME_FRAGMENTS" src dev --glob '*.py'` -> `pass (no matches)`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_no_handler_flattens_a_divergent_retryability.py src/cadrumo/core/errors/tests/test_registry.py src/cadrumo/core/errors/tests/test_registry_enforcement.py` -> `fail (material retained detector found 2 live flattening handlers; 27 passed)`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (expected nonzero with live findings: 62 unreachable modules, 311 exact unused symbols, 15 orphaned tests, 2028/2091 shipped modules reachable)`
