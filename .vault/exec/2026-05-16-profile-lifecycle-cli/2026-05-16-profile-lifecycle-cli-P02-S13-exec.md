---
tags:
  - "#exec"
  - "#profile-lifecycle-cli"
date: "2026-05-16"
modified: '2026-05-16'
step_id: S13
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---

# `profile-lifecycle-cli` `P02.S13`

Introduced the active-profile precedence-chain resolver and routed
the two `WorkflowState` accessor methods and the
`active_bucket_id_or_raise` helper through it. The chicken-and-egg
defect that required `WorkflowState` to be unlocked before learning
which profile to unlock is closed: the resolver reads from
environment variable, then plaintext pointer file, then falls back
to `state.active_profile` during the cutover. Rung three is removed
in the same plan when the field deletes.

- Modified: `src/aeat/application/workflow/_models.py`

## Description

New module-level function `resolve_active_bucket_id(state)` reads
`AEAT_ACTIVE_PROFILE` first, then `read_pointer(settings.aeat_local_storage_root)`
via `load_settings()`, then `state.active_profile`. The CLI
`--profile` flag is not a fourth rung; per-invocation operator
overrides set `AEAT_ACTIVE_PROFILE` so rung one carries them.

`WorkflowState.active_profile_record()` and
`WorkflowState.active_profile_bucket_id()` are now thin
delegations to the resolver. The bucket id and profile name are 1:1
by orchestration convention, so the resolved id is the
lifecycle-service read key.

`active_bucket_id_or_raise(state)` keeps its single-argument
signature so no caller signature cascade is needed; the resolver
threads through `load_settings()` internally.

## Tests

`uv run --no-sync pytest src/aeat/application/workflow/test_bucket_pointer_io.py
src/aeat/application/workflow/test_bucket_pointer.py
src/aeat/application/workflow/test_state_persistence_roundtrip.py
src/aeat/application/user_profile/ -q` → 49 passed. Pre-existing
unrelated failure in `test_models.py::test_details_dict_str_str_accepted`
(WorkflowStep.details typed-model coverage) is unaffected by this
change.

The dedicated precedence-chain test lands in P02.S23.
