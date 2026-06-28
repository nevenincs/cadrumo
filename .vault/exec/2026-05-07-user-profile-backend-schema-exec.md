---
tags:
  - '#exec'
  - '#user-profile-backend-schema'
date: '2026-05-07'
modified: '2026-05-07'
related:
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-07-user-profile-schema-research]]"
---



# `user-profile-backend-schema` `Wave 1 Schema Foundation Step` `Wave 1 Schema Foundation Step`

Wave 1 schema foundation started with a narrow shared-worktree-safe slice. The
slice introduces the committed user-profile schema TOML and strict Pydantic
records/loader for schema metadata only.

- Created: `registry/aeat/user_profile/schema.toml`
- Created: `src/aeat/domain/user_profile/__init__.py`
- Created: `src/aeat/domain/user_profile/_errors.py`
- Created: `src/aeat/domain/user_profile/_loader.py`
- Created: `src/aeat/domain/user_profile/_schema.py`
- Created: `src/aeat/domain/user_profile/_values.py`
- Created: `src/aeat/domain/user_profile/test_schema.py`
- Created: `src/aeat/domain/user_profile/test_values.py`
- Modified: `2026-05-07-user-profile-backend-schema-plan.md`

## Description

Execution record:

| Field | Value |
|---|---|
| `wave` | `W1` |
| `phase` | `Schema Foundation` |
| `step_id` | `W1.P1-W1.P3` |
| `owner_scope` | User-profile schema TOML, strict schema models, schema loader, focused schema tests. |
| `entry_criteria` | Backend and CLI ADRs accepted; rollout plan available; unrelated dirty worktree state identified and avoided. |
| `work_items` | Added schema TOML with canonical sections, snapshot/remove policies, sensitivity metadata, selector metadata, export headers, and schedule predicates. Added strict frozen Pydantic schema records and read-only TOML loader. Added focused tests for committed schema loading, lookup metadata, strict/frozen/no-extra behavior, enum validation, and duplicate section rejection. |
| `verification` | `uv run --no-sync pytest src\aeat\domain\user_profile\test_schema.py -q` |
| `exit_criteria` | Committed user-profile schema loads into strict Pydantic records; canonical field lookup works; invalid schema shapes fail. |
| `dirty_worktree_policy` | No unrelated dirty files were edited or reverted. Owned slice stayed in new user-profile paths plus owned vault plan/exec files. |
| `commit_policy` | Commit-ready only as the Wave 1 schema foundation slice; do not include unrelated registry, browser, vault index, or dependency-lock changes. |
| `residual_risk` | The schema is metadata-only. Secure DB value persistence, model/revision preflight, registry validation wiring, and CLI facade remain for later waves. |

The schema is enrolled into the current strict Pydantic rollout by using
`ConfigDict(strict=True, frozen=True, extra="forbid")` on all schema records.
The loader converts TOML arrays to tuples before validation, matching existing
registry loader patterns for strict Python-mode validation.

Follow-up Wave 2 value-model increment:

| Field | Value |
|---|---|
| `wave` | `W2` |
| `phase` | `Secure Backend API` |
| `step_id` | `W2.P1` |
| `owner_scope` | Strict profile value, tombstone, snapshot, hash, and portable export records. |
| `entry_criteria` | W1 schema models and loader passed focused tests. |
| `work_items` | Added strict frozen Pydantic records for profile facts, live profile roots, tombstones, immutable snapshots, deterministic canonical hash generation, and portable export payloads. |
| `verification` | `uv run --no-sync ruff check src\aeat\domain\user_profile`; `uv run --no-sync pytest src\aeat\domain\user_profile -q` |
| `exit_criteria` | Value records enforce lifecycle constraints; tombstoned profiles cannot be snapshotted; snapshot hashes are stable regardless of fact input ordering. |
| `dirty_worktree_policy` | Continued to touch only new user-profile paths and owned vault records. |
| `commit_policy` | Commit-ready as part of the backend schema/value slice; exclude unrelated dependency lock and other agents' files. |
| `residual_risk` | Secure DB repository APIs and application lifecycle functions are not wired yet. |

## Tests

Focused schema tests passed:

`uv run --no-sync pytest src\aeat\domain\user_profile\test_schema.py -q`

Result: 5 passed.

Focused user-profile package tests passed:

`uv run --no-sync pytest src\aeat\domain\user_profile -q`

Result: 9 passed.

Ruff check passed:

`uv run --no-sync ruff check src\aeat\domain\user_profile`
