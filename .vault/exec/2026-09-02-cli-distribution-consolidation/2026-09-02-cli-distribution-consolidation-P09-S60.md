---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:e66ebecc23c439e8c470dd22030498976f9766be2580ef048ba074276ad55b14'
step_id: 'S60'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Teach the installed oracle the recovery enrollment the product now requires

## Scope

- `dev/packaging/installed_tax_oracle.py`

## Changes

- `A` `dev/scripted_registration_channels.py`
- `A` `dev/packaging/_recovery_enrollment.py`
- `A` `dev/packaging/tests/test_recovery_enrollment.py`
- `M` `dev/packaging/_command.py`
- `M` `dev/packaging/installed_tax_oracle.py`
- `M` `dev/packaging/tests/test_command_execution.py`
- `M` `dev/agent_eval/tests/_scripted_registration_channels.py`
- `M` `dev/agent_eval/tests/test_lifecycle_contradiction_golden.py`
- `M` `dev/agent_eval/tests/test_active_profile_confirmation_golden.py`

## Notes

The reported defect was one of four stacked in the same path. Beyond the
missing recovery channel: the declared profile facts had fallen behind the
obligation a claimed tax-regime block carries, the readiness verb was never
run so filing work refused, and ambient isolation was observed but never
established -- the development environment's own executable sat on the path,
so the record refused itself for want of isolation it had not been asked to
create.

The security control was satisfied, not bypassed. Descriptor inheritance is
unavailable on Windows, and the product already ships the handle-based
bootstrap for exactly that; the oracle now uses it there and file descriptors
elsewhere. A relay thread answers the possession proof, because the verb
writes the phrase and then blocks reading it back inside one call.

One instance of the same defect is knowingly left: a second oracle creates a
profile the same way. No operating-system lane invokes it and it has no
non-test caller, so it was left rather than changed unverified -- but the
integration test owning this path depends on it and therefore did not run.

## Scope

- `dev/packaging/installed_tax_oracle.py`

## Changes
