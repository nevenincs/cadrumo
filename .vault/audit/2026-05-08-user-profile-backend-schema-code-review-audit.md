---
tags: ["#audit", "#user-profile-backend-schema"]
date: 2026-05-08
modified: '2026-05-08'
related:
  - "[[2026-05-07-user-profile-backend-schema-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-08-user-profile-backend-schema-w3-p1-registry-contract-exec]]"
---



# `user-profile-backend-schema` Code Review

USER-PROFILE-001 | MEDIUM | Schedule and deadline selector namespace was over-permissive.

The registry contract initially added every `model_selectors` value into
`schedule_predicates`, allowing a schedule or deadline predicate such as
`tax.id` to pass even when the TOML schema had not explicitly authorized it as
a scheduling predicate.

Resolution: fixed. `build_user_profile_selector_index` now accepts only
explicit `schedule_predicates` for schedule/deadline validation. The contract
test asserts `tax.id` is not a schedule predicate while
`enrollment.large_company` remains present.

USER-PROFILE-002 | MEDIUM | Snapshot canonical hash needed a duplicate-window tie-breaker.

The snapshot fact sort key used only `path`, `valid_from`, and `valid_to`.
Duplicate facts with the same path/window but different values could retain
input ordering and produce different canonical hashes for the same fact
multiset.

Resolution: fixed. Snapshot fact sorting now includes each fact's canonical
JSON payload as a deterministic tie-breaker. A focused test covers reversed
duplicate same-window facts and verifies equal snapshot hashes.

USER-PROFILE-003 | LOW | Registry contract warnings were not pinned.

The contract test asserted no blocking errors but did not assert the expected
rollout warning surface, even though the execution record documents 35
export-header warnings as intentional export-context follow-up.

Resolution: fixed. The contract test now pins the warning count at 35 and
checks representative warning selectors for Modelo 111 and Modelo 202 export
context gaps.

## Verification

Focused user-profile package tests passed:

`uv run --no-sync pytest src\aeat\domain\user_profile -q`

Result: 12 passed.

Focused Ruff check passed:

`uv run --no-sync ruff check src\aeat\domain\user_profile`

USER-PROFILE-004 | HIGH | Validator integration introduced an import-order cycle.

The first validator-integration attempt imported user-profile contract symbols
from `src/aeat/domain/calculations/registry/_validate.py` at module import time,
while `src/aeat/domain/user_profile/_registry_contract.py` imported registry
schema types at runtime. Importing `aeat.domain.user_profile` before the
registry package could hit a partially initialized module.

Resolution: fixed. Registry schema types in `_registry_contract.py` are now
type-checking only, and `_validate.py` imports the user-profile loader and
contract validator lazily inside `_validate_user_profile_contract`. A subprocess
test proves `aeat.domain.user_profile` can import before
`aeat.domain.calculations.registry`.

Follow-up verification passed:

`uv run --no-sync pytest src\aeat\domain\user_profile src\aeat\domain\calculations\registry\test_registry_schema.py::test_validator_rejects_profile_binding_selector_missing_from_user_profile_schema -q`

Result: 14 passed.

Focused Ruff and ty checks passed on the touched paths.
