---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:66885eabee64d13350ff021c982201c178220664a3e4bd83475445e79e6573c2'
step_id: 'S492'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Take the custody keychain lane from thirty three failures to two by diagnosing every case individually against its own locals refusal code or production log rather than the marker, guarding only those the store actually causes so the passing count never moves, and leaving the two that are not the store visible with their failing expressions recorded

## Scope

- `src/cadrumo/application/user_profile/tests`
- `src/cadrumo/entrypoints/cli/tests`
- `src/cadrumo/adapters/persistence/storage`
- `src/cadrumo/tests`

## Changes

A src/cadrumo/tests/_os_keychain_hook.py
M src/cadrumo/application/user_profile/tests/test_login_handover.py
M src/cadrumo/application/user_profile/tests/test_login_handover_sequential_registration.py
M src/cadrumo/application/user_profile/tests/test_registration_retires_displaced_profile.py
M src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py
M src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py
M src/cadrumo/adapters/persistence/storage/tests/test_test_support_runtime_context_lifecycle.py
M src/cadrumo/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py
M src/cadrumo/entrypoints/cli/tests/test_named_profile_resolution_cross_process.py
M src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py

    33 failed / 6 passed /  2 skipped   before
     2 failed / 6 passed / 33 skipped   after

31 cases call `require_os_credential_store()` as their first executable
statement, each on evidence from its own run: a probe dict reading
`refusal: 'keyring_unavailable'`, a refusal-reason comparison resolving to
`'keyring_unavailable' == 'absent'`, a missing `keystore/<id>/session.v2.json`,
production logging `no usable OS keychain`, or the typed
`AUTH_STORAGE_KEYRING_UNAVAILABLE` code in the refusal payload.

THE PASSING COUNT NEVER MOVED. It is the acceptance criterion here, not the
failure count. An earlier attempt wired the same probe as an autouse fixture over
the `os_keychain` marker and produced 41 skipped / 0 failed - a better-looking
line that silenced six cases which pass on this host by asserting the refusal
path, and buried a defect. The marker asserts "needs custody to reach its
subject", not "cannot run here".

## Notes

TWO CASES REMAIN RED BECAUSE NEITHER IS THE CREDENTIAL STORE, which is the
outcome that makes this lane worth reading.
`test_absent_session_login_action_keeps_the_executable_profile_label` reads
`error.action.action.action.action_id` while the envelope emits one level
shallower; `test_explicit_history_reads_the_requested_profile_repository` gets an
empty `BucketEventHistoryCatalogue` with nothing in the run naming the store, so
its cause is unestablished rather than assumed. Both belong to their owners.

METHOD COST WORTH RECORDING: three batch attempts failed for three different
reasons - stdin left attached to an id list hung every spawned subprocess,
stripping a `[param]` made `-k` match a whole family and yield group verdicts,
and a long run measured files being edited mid-run and scored the new skips as
"no failure". They cost roughly eleven iterations and produced nothing usable.
Single runs took about twelve seconds each and closed every case. A proven case
kept as a control is what exposed the broken instrument; without it, "15 real
defects" would have been recorded as fact.

UNPROVEN: no reachable credential store exists on this host, so the non-skip arm
rests on the probe's `None` branch rather than an end-to-end pass. A desktop
logon should run `just test-os-keychain` once and confirm the 31 execute.

NOT COMMITTED by me.
