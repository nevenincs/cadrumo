---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:7d31f7b223acb5cc62dc9359f1e7efb7822861669540c43be387ae446e7b4d83'
step_id: 'S491'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Guard the twelve custody cases whose own body raises the keychain unavailable error behind the shared credential store probe, pairing each failure to its test through the junit report rather than a traceback dump, and leave the opaque handover assertions and the absent session action key error red because a marker keyed skip over all of them was measured to discard six passing cases

## Scope

- `src/cadrumo/adapters/persistence/storage`
- `src/cadrumo/entrypoints/cli/tests`
- `src/cadrumo/tests`

## Changes

M src/cadrumo/adapters/persistence/storage/custody/tests/test_acceleration_receipt_roundtrip.py
M src/cadrumo/adapters/persistence/storage/custody/tests/test_unwrapped_dek_is_wipeable.py
M src/cadrumo/adapters/persistence/storage/tests/test_test_support_runtime_context_lifecycle.py
M src/cadrumo/entrypoints/cli/tests/test_profile_session_root_resume.py
M src/cadrumo/tests/_os_keychain_hook.py

    before:  33 failed,  6 passed,   2 skipped
    after:   21 failed,  6 passed,  14 skipped

Twelve cases whose own body raises the keychain-unavailable error now call
`require_os_credential_store()` as their first executable statement. Failed fell
by exactly twelve, skipped rose by exactly twelve, and THE PASSING COUNT HELD.

THE PASSING COUNT IS THE ACCEPTANCE CRITERION, not the failure count. An earlier
attempt wired the same probe as an autouse fixture over the `os_keychain` marker
and scored 41 skipped / 0 failed - a better-looking line that silenced six cases
which pass here by asserting the refusal path, and buried a defect. The marker
pins "needs custody to reach its subject", not "cannot run on this host"; those
are different propositions and only the second would justify a blanket skip.

Each guarded case was paired to its own raise through a JUnit report. A
`--tb=line` dump was tried first and rejected: its failure section carries
chained exception lines with no test headers, so cause-to-test mapping would
have been positional guesswork on the one input that decides what gets silenced.

## Notes

LEFT RED DELIBERATELY. Fourteen cases fail on `assert False is True`, which
proves nothing about cause; six more carry store-derived messages that still want
individual confirmation; and one, `test_absent_session_login_action_keeps_the_executable_profile_label`,
fails with `KeyError: 'action'` that is NOT the credential store - the verb emits
its typed refusal correctly here, and the test reads one nesting level deeper
than the envelope provides. That belongs to the envelope's owner.

UNPROVEN ON THIS HOST: no reachable credential store exists here, so the
non-skip arm rests on the probe's None branch rather than an end-to-end pass.
A desktop logon should run `just test-os-keychain` once and confirm the twelve
EXECUTE rather than skip.

NOT COMMITTED by me. Three times this session an in-flight file was swept into
another writer's commit, so what is committed here may not reflect a review.
