---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S03'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Teach the lifecycle authority early-mint registration in setup-incomplete state, duplicate-tax-id refusal firing at mint, and discard-erase of an abandoned incomplete profile

## Scope

- `src/cadrumo/application/user_profile/_lifecycle.py`

## Description

- Add the `status` arm to `RegisterProfileCommand` (default ACTIVE,
  SETUP_INCOMPLETE for the early mint, tombstoned birth refused by a
  model validator).
- Stamp `command.status` on the record at `ProfileLifecycleService.register`.
- Add `CompleteSetupCommand` and the `complete_setup` service arm: load,
  domain transition (refuses non-incomplete sources), save, emit
  `PROFILE_SETUP_COMPLETED`.
- Export `CompleteSetupCommand` through the package facade (lazy import
  map, name registry, `__all__`).
- Pin with four lifecycle tests over real repositories: status persists
  and lists, tombstoned birth refused, transition activates and emits,
  active source refused.

## Outcome

Committed as `2d208f0002` (explicit pathspec). Lifecycle suite 22/22,
event-emission contract and orchestration suites 11/11.

## Notes

Discard of an abandoned incomplete profile needs no new arm: the
existing remove (soft tombstone) plus bucket-directory erase composition
covers it; the wizard door wires it in the W03 create-mode Step.
