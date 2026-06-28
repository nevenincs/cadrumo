---
tags: ["#exec", "#user-profile-backend-schema"]
date: 2026-05-08
modified: '2026-05-08'
related:
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-07-user-profile-schema-research]]"
---



# `user-profile-backend-schema` `W3.P1` `Registry Contract`

W3.P1 adds backend-owned registry contract validation against the committed
user-profile schema metadata. The new contract validator builds selector
namespaces from the schema and validates registry profile bindings, filing
schedules, deadline windows, and export layouts against those namespaces.

- Created: `src/aeat/domain/user_profile/_registry_contract.py`
- Created: `src/aeat/domain/user_profile/test_registry_contract.py`
- Modified: `src/aeat/domain/user_profile/__init__.py`
- Modified: `registry/aeat/user_profile/schema.toml`

## Description

| Field | Value |
|---|---|
| `wave` | `W3` |
| `phase` | `Registry And Calculation Integration` |
| `step_id` | `W3.P1` |
| `owner_scope` | User-profile schema selector metadata, registry contract models, committed-registry coverage tests, and package exports. |
| `entry_criteria` | W1 schema metadata and W2 value-model records exist; committed modelo registry profile bindings and schedule predicates are available for cross-reference. |
| `work_items` | Added typed contract report, issue, severity, and selector-index records. Added validation for profile bindings, filing schedule predicates, deadline applicability predicates, `profile_tax_id` draft export usage, and non-blocking export-header coverage warnings. Expanded schema selector coverage for Modelo 100, Modelo 111, and Modelo 349. |
| `verification` | `uv run --no-sync pytest src\aeat\domain\user_profile -q`; `uv run --no-sync ruff check src\aeat\domain\user_profile`; focused broader profile/modelo registry tests. |
| `exit_criteria` | The committed registry tree can be checked against the user-profile schema with 0 blocking profile-selector contract errors. |
| `dirty_worktree_policy` | Stage and commit only user-profile schema/backend files plus owned VaultSpec records. Leave unrelated staged, modified, deleted, and untracked files untouched. |
| `commit_policy` | Commit-ready as a backend hardening slice after focused tests and review. |
| `residual_risk` | The general registry validator does not yet call the user-profile contract validator. Runtime schedule evaluation still resolves dotted fields directly. Filing/export CLI behavior still reads active profile headers from current profile state. |

The step checked 25 committed modelos. The report returned 0 blocking
profile-selector errors and 35 export-header warnings. The warnings are mostly
Modelo 202 `datos_adicionales_*` fields plus one Modelo 111 school flag; those
are retained as export-context follow-up rather than taxpayer profile facts.

## Tests

Focused user-profile package tests passed:

`uv run --no-sync pytest src\aeat\domain\user_profile -q`

Result: 12 passed.

Focused Ruff check passed:

`uv run --no-sync ruff check src\aeat\domain\user_profile`

Broader profile and modelo registry tests passed:

`uv run --no-sync pytest src\aeat\application\profile src\aeat\domain\profile src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_111_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py -q`

Result: 122 passed.

A broader Ruff pass over existing registry tests found pre-existing unused
imports in `test_modelo_111_registry.py`. That file is outside this slice and
was not modified.

The code review found no HIGH or CRITICAL issues. Two MEDIUM findings and one
LOW finding were fixed before commit: schedule predicates now require explicit
TOML predicate metadata, snapshot fact sorting uses a canonical fact tie-breaker,
and the expected export-header warning surface is pinned in tests.
