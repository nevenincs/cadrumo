---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W04.P13.S44'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P13.S44 - Remove unused secure SQL CursorResult import

Scope: Close the Vulture candidate for
`src/aeat/adapters/persistence/storage/sql/secure_objects.py` while preserving
secure-object repository behavior.

## Description

- Remove the unused `CursorResult` runtime import from the secure-object SQL
  repository.
- Replace the concrete `CursorResult` casts with a local structural
  `_RowcountResult` protocol for SQLAlchemy DML rowcount checks.
- Verify that Vulture no longer reports the secure-object import while leaving
  later W04.P13 dead-code candidates open.

## Outcome

The secure-object SQL repository no longer imports `CursorResult` at runtime.
The repository still casts DML execution results to a rowcount-bearing shape at
the two rowcount use sites, and no storage behavior changed.

## Notes

The worktree already contained an unrelated docstring edit in
`src/aeat/adapters/persistence/storage/sql/secure_objects.py`; this step leaves
that edit uncommitted and commits only the rowcount protocol change plus Vault
tracking. Ruff was run against the exact commit-candidate blob because the live
worktree copy still includes that unrelated line-length issue. Remaining Vulture
findings belong to W04.P13.S45-S46.
