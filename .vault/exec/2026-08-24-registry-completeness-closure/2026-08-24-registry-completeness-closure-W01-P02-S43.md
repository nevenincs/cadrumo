---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:c8394e384a7d4049f9e9c4701b10b9192824cc2d3fc943e75e11a9201d4f7b8e'
step_id: 'S43'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Reject resolved owner dispositions on active closure refusals and prove the contradiction fails validation

## Scope

- `src/cadrumo/application/registry/`

## Description

- Validate non-satisfied closure limbs against their owner-disposition state.
- Reject a `resolved` disposition whenever the selected limb remains refused or unmeasured.
- Add a parameterized regression covering both active fail-closed outcomes.

## Outcome

An unresolved release capability can no longer be presented as resolved by its
owner metadata. The parent `RegistryClosureLimb` validates the nested
disposition after associating it with an active outcome, so the invariant holds
for both direct construction and a nested record that was copied without
revalidation.

Focused verification passed:

- `uv run --no-sync ruff check src/cadrumo/application/registry/_closure.py src/cadrumo/application/registry/tests/test_closure_models.py`
- `uv run --no-sync pytest -x src/cadrumo/application/registry/tests/test_closure_models.py` -- 7 passed.
- `git diff --check`

## Notes

No incidents or skipped scope.
