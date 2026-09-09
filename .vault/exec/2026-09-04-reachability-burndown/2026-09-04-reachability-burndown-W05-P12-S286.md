---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:3057110ac91e69a589831a7b56c414bc49c5b0c6aff80a2fc0b61ba9d2239878'
step_id: 'S286'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unread workflow operation-instant context, getter, scope, export, and CAS wrapper while retaining the actual retry loop; run focused gates, classify unrelated envelope-schema reds, update cadence, and remeasure exact reachability.

## Scope

- `workflow persistence and focused persistence tests`

## Changes

- `M` `src/cadrumo/application/workflow/persistence.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for operation-instant context/getter/scope -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` workflow persistence tests -> `8 passed, 3 peer-owned envelope-schema failures`
- `verify:` exact reachability -> `253 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The focused persistence run still has three adapter-owned envelope-header validation failures: `written_at`, `payload`, and `encryption` are rejected as extra fields when loading rows written by the same suite. The removed operation-instant context does not participate in envelope serialization or validation; eight sibling persistence tests pass, and the same failures remain outside this Step's ownership.
