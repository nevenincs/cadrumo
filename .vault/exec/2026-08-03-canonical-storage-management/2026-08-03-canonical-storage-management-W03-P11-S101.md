---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:11951afb570a4b928898b40cce46fcadd14b0e79f929584accd5f324078ae8a4'
step_id: 'S101'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Confirm the peer's lifecycle-gate fix has landed and the gate is green at committed HEAD, then rewrite the five hand-maintained frozensets onto the taxonomy while keeping the gate enumerating path-typed settings fields rather than taxonomy members, retaining the two structural checks the taxonomy cannot itself express

## Scope

- `src/cadrumo/core/tests/test_settings_lifecycle_gate.py`

## Description

- Confirm the peer's lifecycle-gate fix landed and the gate is green at committed HEAD.
- Rewrite the five hand-maintained frozensets onto the taxonomy while keeping the gate enumerating path-typed settings fields, not taxonomy members (per ADR R4).
- Retain the two structural checks the taxonomy cannot itself express.

## Outcome

Landed in commit `88c9faac4e` ("retire the hand-curated lifecycle classes and the shipped table"), confirmed an ancestor of HEAD. Deleted five hand-maintained frozensets from `test_settings_lifecycle_gate.py` (`_ROTATION`, `_TTL`, `_RETENTION`, `_UNBOUNDED_BY_DESIGN`, `_EXEMPT_INPUT`) plus the local `_path_typed_fields()` discovery helper and the test that classified fields against them. Classification now reads off `_storage_taxonomy.py` directly: each `StorageCategory` member's own `StorageLifecycle` field, and each escaped path setting's own `ExternalPathRole` via `EXTERNAL_PATH_SETTINGS_FIELDS` plus `STORAGE_ROOT_SETTINGS_FIELD` for the root itself. Discovery moved to a shared `path_typed_settings_fields(Settings)` helper (`core/tests/_settings_path_fields.py`). Two properties the taxonomy cannot itself express are retained structurally: every non-exempt output dir must derive its default from the root or be an opt-in override, never a concrete anchored default; and no shipped module builds a path from the taxonomy's own vocabulary as a literal.

## Notes

Landed but untracked — found and backfilled on a fresh-context honesty review that flagged this Phase as having zero Steps despite the work being done.
