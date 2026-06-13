---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S01'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Capture the current red set from the lazy-loading discipline gate

## Scope

- `src/aeat/entrypoints/cli/test_lazy_command_tree.py`

## Description

- Run the gate in red-baseline mode against `chore/eliminate-shims` HEAD.
- Record the 5-test red set: `test_version_cold_start_completes_under_budget`,
  `test_importing_cli_package_does_not_import_registry`, and the three
  parameterised instances of `test_state_free_surface_does_not_import_registry`
  (argv `["--version"]`, `["--help"]`, `[]`).
- Confirm `test_dispatching_a_subcommand_loads_its_module` stays green
  to anchor the on-demand contract.

## Outcome

- 5 failed, 1 passed in 22.7s.
- Cold-start budget overshoot recorded at 3.19s (budget 2.0s).
- Registry-leak count consistent at 69 `aeat.domain.calculations.registry*`
  submodules across the four state-free invocations.
- Subcommand-dispatch test green: lazy loader still wires.

## Notes

- Baseline captured to `.tmp_lazy_red_baseline.log` (gitignored).
- The registry-leak signature (69 modules, deterministic order) makes the
  before / after diff trivial for the producer-side probe authored in
  P01.S03.
