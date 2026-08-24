---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:84420d5d9568bded3a4306f3f552fb1cf530dd4a63c6a5673d1de3c6554da93d'
step_id: 'S121'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Perform the PRE_RELEASE current-only cutover by proving zero affected nonterminal operations, refusing every superseded journal and lease shape, and deleting the v1 lease reader, acquisition migrator, retired schema dispatchers, fixtures, and migration tests without a compatibility path

## Scope

- `src/cadrumo/application/operations` and `src/cadrumo/adapters/persistence/operations`

## Description

- Used Vaultspec RAG to locate the lease migration reader, acquisition hook, journal parser, and old-schema tests, then confirmed the full inventory with exact symbol searches.
- Confirmed the PRE_RELEASE delete-and-refuse rule in the governing research and accepted ADRs.
- Ran a read-only workspace census before deletion. The sole ignored `operation-journals` artifact is a terminal user-profile handover record, not an `OperationJournalRecord` or lease record; no affected nonterminal operation invocation exists in the workspace.
- Deleted the scope-less v1 lease record model, retired path helper, acquisition migrator and call, and the redundant journal parser shim.
- Replaced the migration test with strict lease v1 and v3 refusal evidence that preserves durable bytes.
- Added real-adapter journal v1 through v5 refusal evidence that preserves durable bytes across both load and replay.

## Outcome

The canonical persistence readers accept only lease schema v2 and journal snapshot schema v6. Superseded shapes fail closed before interpretation, with persisted bytes unchanged. The exact post-edit census finds no `_OperationLeaseRecordV1`, `_legacy_path_for`, `migrate_legacy_before_acquisition`, or `_parse_operation_journal_record` declarations or call sites. Vaultspec RAG and exact searches converge on one current lease parser and one current journal-record parser.

Focused current-only persistence tests pass: 50 tests. Scoped Ruff and production type checks pass. The complete application/persistence operation lanes report 306 passes and one persistence-facade export-inventory assertion that is outside the changed S121 paths and tracks the concurrent secure-reference export work.

## Notes

No durable user data was deleted. The unrelated terminal handover artifact was left untouched. Removed source and test surfaces remain recoverable through the forthcoming S121 Git commit; no compatibility path or data rewrite was introduced.
