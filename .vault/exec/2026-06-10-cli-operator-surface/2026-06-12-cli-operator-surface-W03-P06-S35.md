---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S35'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P06.S35 Switch Behavior Tests

Scope: verify real behavior for the switch hard rename and no-alias retirement.

## Description

- Ran real CLI/profile lifecycle tests proving `config switch` activates an existing profile.
- Ran the no-alias test proving `config unlock` is no longer a command.
- Ran the profile-activation event test proving switch still performs the underlying session activation mechanics.
- Ran the config custody lifecycle subprocess test covering lock/switch behavior.

## Outcome

S35 is closed. Focused tests prove `switch` performs the intended profile activation behavior and `unlock` remains unavailable.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_switch_activates_existing_profile ... test_config_unlock_is_no_longer_a_command ... test_config_switch_emits_profile_activated_event src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py::test_config_lock_switch_drive_profile_lifecycle`.
