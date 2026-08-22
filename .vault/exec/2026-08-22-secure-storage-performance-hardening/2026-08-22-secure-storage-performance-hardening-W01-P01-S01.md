---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:376b73baf2e5de5988adefd287278fe7e51f74afaec56a7466b1323e4f8bf253'
step_id: 'S01'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Extend the live command walker to emit stable command paths, node kind, loader owner, and handler owner for every reachable node

## Scope

- `src/cadrumo/entrypoints/cli/_command_suggestions.py`

## Description

Add an immutable live-command census record with canonical operator paths,
root/group/leaf kind, lazy-loader ownership, and callback ownership.

Walk the runtime tree through vendored Click contexts and duck-typed group
protocols, resolving lazy descendants exactly as dispatch does.

Distinguish eager registration from real loader ownership and preserve repeated
path aliases while terminating cyclic command graphs.

Exercise the complete installed command tree and a focused real Typer eager/lazy
ownership specimen in `src/cadrumo/entrypoints/cli/tests/test_command_suggestions.py`.

## Outcome

`walk_live_command_tree` now emits a deterministic immutable tuple covering the
root and every reachable command path. Lazy nodes identify the owning factory;
eager and root nodes truthfully carry no loader owner. Handler identity is
reported independently as a stable module-qualified callable name.

The installed-tree gate reaches deep config and modelo leaves, proves repeated
walk stability and unique paths, and validates serialisable ownership. Focused
lint and all five scoped integration tests pass. The mandatory review found one
high-severity eager-attribution defect in the initial implementation; it was
resolved and the re-review found no remaining issue.

## Notes

The first installed-tree run exposed the committed password-strength/TUI drift
at HEAD `63617870cb`. Peer-owned corrective edits became visible without any
change to this Step's scope; the exact full-tree test was rerun against those
live corrections and passed. No test was skipped or weakened.
