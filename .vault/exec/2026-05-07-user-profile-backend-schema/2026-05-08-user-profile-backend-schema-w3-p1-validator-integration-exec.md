---
tags: ["#exec", "#user-profile-backend-schema"]
date: 2026-05-08
modified: '2026-05-08'
related:
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-08-user-profile-backend-schema-w3-p1-registry-contract-exec]]"
---



# `user-profile-backend-schema` `W3.P1` `Validator Integration`

This follow-up hardens W3.P1 by wiring the user-profile registry contract into
the general registry validation path.

- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/user_profile/_registry_contract.py`
- Modified: `src/aeat/domain/user_profile/test_registry_contract.py`

## Description

| Field | Value |
|---|---|
| `wave` | `W3` |
| `phase` | `Registry And Calculation Integration` |
| `step_id` | `W3.P1-validator-integration` |
| `owner_scope` | Registry validator integration, import-cycle boundary, and selector-rejection regression tests. |
| `entry_criteria` | W3.P1 package-level user-profile registry contract exists and passes focused tests. |
| `work_items` | Added `RegistryValidator` integration for blocking user-profile contract errors. Added optional schema injection for typed tests and future controlled validation. Added a Modelo 100 negative test proving an unknown profile binding selector fails registry validation. Removed runtime registry imports from the user-profile contract module and moved user-profile imports in the registry validator to the validation method to preserve import order. |
| `verification` | Focused user-profile and registry selector tests; Ruff and ty checks on touched paths. |
| `exit_criteria` | `RegistryValidator.validate_modelo` rejects unknown user-profile selectors, and `aeat.domain.user_profile` can import before `aeat.domain.calculations.registry`. |
| `dirty_worktree_policy` | Touch only the registry validator, one registry schema test, user-profile contract import boundary, one user-profile contract test, and owned VaultSpec records. |
| `commit_policy` | Commit separately from the schema/backend foundation commit. |
| `residual_risk` | Full `test_registry_schema.py` is currently blocked by unrelated dirty corpus byte-count mismatch for `aeat-groi-spanish-roi-procedure`; that corpus/source slice was not modified. Runtime schedule projection and export-context migration remain future waves. |

## Tests

Focused verification passed:

`uv run --no-sync pytest src\aeat\domain\user_profile src\aeat\domain\calculations\registry\test_registry_schema.py::test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema -q`

Result: 14 passed.

Focused Ruff check passed:

`uv run --no-sync ruff check src\aeat\domain\user_profile src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_registry_schema.py`

Focused ty check passed:

`uv run --no-sync ty check src\aeat\domain\user_profile src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_registry_schema.py`

Scoped code re-review passed after the import-cycle fix. No new HIGH or
CRITICAL issues were found.
