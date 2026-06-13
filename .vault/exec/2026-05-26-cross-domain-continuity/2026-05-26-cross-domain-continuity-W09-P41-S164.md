---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S164'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---




# delete dead alias _profile_binding_selectors

## Scope

- `src/aeat/domain/user_profile/_registry_contract.py`

## Description

Removed the dead alias `_profile_binding_selectors = profile_binding_selectors` from `src/aeat/domain/user_profile/_registry_contract.py:308`. The only external reference (`test_profile_binding_selectors_is_public...` in test_registry_contract.py) is a test function name that happens to share the prefix; not an actual import of the alias. All 4 tests in test_registry_contract.py continue to pass after removal.

## Outcome

Closed by direct code edit; see Description above.

## Notes

Real cleanup, not audit-based — duplicate registrations were live in the registry and the alias was unused.
