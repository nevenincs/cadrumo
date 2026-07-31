---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:3f0558b39d0cac0c0360d7cd62dab02173796606cb1acb4f887e243ca5c2d032'
step_id: 'S32'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---

# Repair the two failing tests in the P04.S23 carried evidence file that a same-day peer commit turned red by retiring the active-profile environment override, so the carried-forward completeness claim rests on green evidence, coordinating with the owner of the environment severance rather than re-implementing the retired mechanism, gated on the module passing in the integration lane

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`

## Description

- Coordinate rather than re-implement, as the step names: the environment-severance owner
  (the concurrently-landing `profile-login-session` campaign) closed the two failing
  tests as their own step `W03.P06.S15`, commit `ac8f242f6d` ("test(profile): retire the
  env precedence claim in the custody lifecycle gate").
- That commit renamed `test_profile_selection_precedence_uses_explicit_env_then_pointer`
  to `test_profile_selection_precedence_uses_explicit_flag_then_pointer`, inverting the
  assertion to match the two-writer selection model `e75322d8cc` established (`--profile`
  and the on-disk pointer; the `CADRUMO_ACTIVE_PROFILE` override is severed). The write-side
  block now proves the exported env var cannot redirect a write away from the pointer's
  profile while `--profile` still can, and the mounted-verb check walks
  login/logout/passphrase/recover/recovery, asserting `switch` is absent — coverage
  strengthened rather than merely restored.
- Independently re-run against HEAD for this record rather than trusted from the sibling
  commit's own claim: `test_config_custody_profile_lifecycle.py -m integration`, `6
  passed` (two separate runs, `200.12s` and `208.98s`).

## Outcome

The carried-forward completeness claim for `P04.S23` again rests on green evidence. No
code change was authored under this step; the fix landed as the environment-severance
owner's own step, exactly as `P04.S32`'s text asked ("coordinating with the owner of the
environment severance rather than re-implementing the retired mechanism"). This record
exists so the coordination outcome — and the real commit and test it produced — is
locally evidenced under this plan's own stem rather than left to a cross-campaign trace.

## Notes

This record was authored 2026-07-25, after `ac8f242f6d` had already landed, as part of
closing three items a fresh-context close-honesty review
(`2026-07-24-all-profile-reset-close-honesty-review-audit.md`) surfaced against this
plan.
