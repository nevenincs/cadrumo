---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:c9ede2bb598b36aa92e746fd0f5a3ed453a64f5b1d09fd5d9eba8cf59ebdd9ed'
step_id: 'S273'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the uncomposed review-only workspace layer and its synthetic audit event because no command opens or consumes that workspace; retain the live recipient encryption/decryption and collaboration event paths, remove dormant errors/locales, run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `review-only workspace module and tests`
- `collaboration audit event`
- `bucket event enum`
- `error registry`
- `locales`

## Changes

- `D` `src/cadrumo/application/modelo/_review_package_review_only_workspace.py`
- `D` `src/cadrumo/application/modelo/tests/test_review_package_review_only_workspace.py`
- `M` `src/cadrumo/application/modelo/review_package_collab_audit.py`
- `M` `src/cadrumo/application/modelo/tests/test_review_package_collab_audit.py`
- `M` `src/cadrumo/domain/buckets/event.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `src/cadrumo/locales/{ca,en,es,hu}/application.yml`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused encrypted collaboration and error-registry tests -> `3 passed, 12 deselected`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail (live findings remain)`

## Notes

No product command constructed or consumed the deleted workspace; only its own tests and its synthetic audit-event helper referenced it. The live recipient encryption/decryption CLI and the remaining encrypted collaboration events are unchanged and passed their real storage roundtrips. Exact reachability improved from 274 to 268 unused symbols and from 2059 to 2058 shipped modules, with 31 unreachable modules and zero orphaned tests unchanged.
