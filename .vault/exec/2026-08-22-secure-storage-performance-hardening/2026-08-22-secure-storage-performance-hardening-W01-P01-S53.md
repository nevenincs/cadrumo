---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:cf7bac216716749bb4f8e7a8aab797476d590de86524aade217dc0ddf48dd600'
step_id: 'S53'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Migrate profile-bound write routing to execution-policy scope and delete the verb-path catalogue

## Scope

- `src/cadrumo/application/storage_write_policy.py and src/cadrumo/entrypoints/cli/_common.py`

## Description

- Replace root path-prefix classification with selected-callback execution
  policy resolution and conditionally import the application route query only
  for `profile-bound` callbacks.
- Delete the 99-row verb-path catalogue, prefix matcher, argv/option heuristic,
  legacy exports, consumers, stale quality metadata, and catalogue-specific
  tests without an alias or fallback.
- Reconcile operator-surface projections through the public live-policy
  authority and preserve explicit bootstrap-root semantics for session and
  recovery doors.
- Add live exact-set, planted-unclassified, downgrade, rename-invariance,
  proportional-import, bootstrap-justification, and real-dispatch gates.
- Resolve every independent review finding and rerun focused lint, typing,
  behavior, and exhaustive absence checks.

## Outcome

The live callback is now the sole storage write-route authority. All 288 live
leaves carry policy; 125 declare profile-bound routing and the bootstrap-root
set is explicit. Unknown policy fails closed. A fresh real-process `config
profile list` does not import `application.storage_write_policy`, while real
profile-bound dispatch refuses root-fallback and explicit database routes
before database creation. Login and recovery doors reach their own handlers.

Focused storage-policy, root-guard, typed-projection, operator-surface, and MCP
review coverage passed with 31 tests. The root-focused correction suite passed
24 tests. Ruff and scoped `ty` passed. Exhaustive active-source searches return
no retired catalogue, matcher, or delegation symbol. The mandatory independent
review approved after its high and medium findings were fixed and verified.

## Notes

The owning modelo branch-classification gate remains red on eight unclassified
and five stale M303 rows from concurrent shared-tree work; direct reconciliation
shows zero broken citations and no S53 storage-write-policy residue. A broader
joined operator-surface run likewise observed four concurrently registered
profile result schemas whose live commands are absent. Neither failure was
used to claim a broad green gate; both are recorded separately from S53's
passing scoped evidence. Initial implementation landed in `980605f15a`; review
artifacts landed in `bc45a52152`, with the review corrections committed as an
exact-path follow-up.
