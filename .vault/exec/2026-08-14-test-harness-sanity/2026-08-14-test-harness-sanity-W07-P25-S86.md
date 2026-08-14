---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:a738c6f933386d0159d8ea122a66e9a2c1bce17dc2fdb53aa01158c277703228'
step_id: 'S86'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Replace stale naked-test rationale with current distributed visibility requirements

## Scope

- `src/cadrumo/conftest.py`

## Description

- Replace the retired naked-test placement rationale in the package conftest.
- Document distributed domain-local test visibility and the package-root fixture ownership boundary.
- Preserve the separate repository-root collection-policy ownership statement and executable fixture behavior.

## Outcome

The package conftest now explains the current topology: tests live under owner-local `tests/` subtrees, and the package-root conftest is the narrowest common visible owner for cross-tree AST inventory fixtures.

## Notes

The documentation skill and repository documentation rules governed the scoped prose correction. Exact topology inventory found no naked source tests and consumers across central, adapter, application, core, domain, and entrypoint subtrees. Ruff, stale-reference scan, diff integrity, and independent review passed; no executable code changed.
