---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S06'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Extend the PEP 562 `__getattr__` block

## Scope

- `src/aeat/application/user_profile/__init__.py`

## Description

- Add a `_COMMAND_NAMES` frozenset enumerating the 17 relocated class
  names; on a hit, lazily import `_commands` and delegate via
  `getattr`.
- Add a `_DOMAIN_RECORD_NAMES` frozenset enumerating the four domain
  records (`UserProfileFact`, `UserProfileFactValue`,
  `UserProfileRecord`, `UserProfileStatus`); on a hit, lazily import
  `aeat.domain.user_profile` and delegate via `getattr`. This is the
  re-export path that keeps the public surface unchanged.
- Preserve every pre-existing `__getattr__` branch (service classes,
  censo errors, censo sync, projections, validation, preflight,
  bundle, orchestration, repository, profile-repository).

## Outcome

- Landed as part of commit `e78b32be0` together with S04 and S05.
- All 115 tests in `src/aeat/application/user_profile` pass, including
  the new lazy-boundary probe.

## Notes

- Frozensets are preferred over per-name `if` branches: O(1) lookup,
  one allocation at module init, clearer to grep.
- Domain-record path imports the *package*, not a private submodule,
  so the package's own (eager) `__init__.py` is what executes — the
  `_registry_contract` pull is deferred to first reference, which is
  the lazy contract this fix establishes.
