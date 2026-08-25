---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:2f001ae8b3b279e7f6b2456a8c490e7acb362221102085ebcf61610fd3c45fc9'
step_id: 'S168'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Replace the strict active-profile pointer record and IO owner with one atomic absent-or-selected observation/current-coordinate contract that persists its monotonic transition revision under the canonical custody-root lock, promote the core record/coordinate surface and sole user-profile transaction through their canonical facades, atomically migrate every exact direct reader and transaction consumer, and prove idempotence, cross-process A -> B -> A, restore/clear lineage, and zero dual reader/writer, compatibility reader, shim, alias, fallback, or re-export bridge

## Scope

- `src/cadrumo/core/_bucket_pointer.py`
- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/config.py`
- `src/cadrumo/application/storage_write_policy.py`
- `src/cadrumo/application/config_reset.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/user_profile/_profile_pointer_transaction.py`
- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/application/workflow/_profile_health.py`
- `src/cadrumo/application/user_profile/_login_session.py`
- `src/cadrumo/application/user_profile/_lifecycle.py`
- `src/cadrumo/application/user_profile/_custody_service.py`
- `src/cadrumo/application/user_profile/_custody_repository.py`
- `src/cadrumo/entrypoints/cli/_config/_profile_delete.py`
- Focused pointer-record, facade, direct-reader, transaction, reset, and handover tests.

## Description

- Replace the selected-only payload with a strict v2 absent-or-selected record carrying `transition_revision`.
- Make the custody-root transaction the sole production mutation authority; clear writes an absent tombstone and idempotent states retain their coordinate.
- Move direct readers, durable reset witnesses, custody journals, login handovers, Settings cache identity, and public facades to the canonical observation.
- Delete duplicate custody snapshot IO, byte-CAS facade, exact-byte restore, unlink clear, and compatibility-reader paths.
- Prove strict v1 rejection, no-follow pointer refusal, idempotence, clear and restore lineage, real spawned A-to-B-to-A succession, stale-coordinate refusal, facade ownership, and sole-writer source ownership.

## Outcome

`d64845fbf1a` delivered the implementation. During shared-history advance, concurrent commit `03d2b3caef1` accidentally swept the five independently verified closure corrections into its operations-relocation change. This closure records their verification without rewriting shared history: it removes an unused import, makes the ABA reset fixture unambiguous, expects the public transaction error, uses public facade imports, and asserts failed-login rollback as A/r to B/r+1 to A/r+2.

Focused verification passed: core pointer and authority coverage, 35 custody/authority unit tests with 3 correctly marker-deselected, 22 reset tests, and 26 non-keychain handover integration tests. Collection found 71 requested tests and 38 marker deselections. Scoped Ruff passed for the full pointer surface and every closure correction; scoped basedpyright passed for all changed pointer sources without inherited diagnostics and for every correction file. Vault feature validation completed without errors. RAG and exact source census found one production low-level writer, the canonical transaction, and no retired capture, restore, clear, byte-CAS, duplicate-snapshot, or raw-byte handover paths.

Reopened-review remediation hard-moved the public definitions to
`core.bucket_pointer` and `application.user_profile.profile_pointer`, then
removed every pointer binding from both package facades. A deterministic
Settings test forces an A-to-B switch after the single pointer read and proves
the cache coordinate and derived database route remain A. A reset recovery
test forces a later select-and-clear tombstone and proves resume pauses rather
than accepting that unrelated successor.

## Notes

`d64845fbf1a` landed before its final verification pass. Concurrent `03d2b3caef1` then swept the five resulting test/static corrections during a shared-worktree operations relocation. This closure is deliberately limited to the execution record and CLI plan check; shared commits are not rewritten or restaged.

The `filing/_review.py` and `flows/_definition.py` changes bundled in `d64845fbf1a` are unrelated `content_hash_hex` refactors rather than pointer-coordinate consumers. They are an accidental scope sweep for separate review and are neither extended nor reverted here.

Repository-wide import hygiene reached 77 passing checks before two external failures: a transient TUI test syntax error and dangling imports during the concurrent operations-module relocation. Neither diagnostic named an S168 path. Later focused collection completed after the registry/auth worktree settled. Full basedpyright still reports inherited, pre-S168 diagnostics in `core/config.py`, `workflow/_profile_health.py`, and `_lifecycle.py`; the S168-specific subset is clean.

Shared-history remediation tuple: `d64845fbf1a` initial contract,
`56dea1fa90` public core move, `5975b39f3b` public transaction move,
`25259e7249` concurrent sweep, and
`85ab2a53657209aa70c8e4cc821f400e8d9b1bea` direct defining-module consumer
migration. The final reset collection was blocked only by the unrelated missing
`WorkflowInputMismatchError` workflow-facade symbol during concurrent relocation.
