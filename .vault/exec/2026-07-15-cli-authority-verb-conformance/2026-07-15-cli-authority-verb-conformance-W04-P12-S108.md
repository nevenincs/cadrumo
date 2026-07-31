---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:e40a8146b8b4c782c27f969ce75ed72275c5735929fc0349ba0d468400b1209f'
step_id: 'S108'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Write create and rotate candidates directly to the controlling terminal and require full no-echo retype before commit

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

`config recovery create`/`rotate` had to write the candidate mnemonic directly to the
controlling terminal device (never stdout, a log, or the JSON envelope) and require the
operator to fully retype it with echo suppressed before the new envelope is committed.

## Outcome

`_confirm_candidate_on_terminal` (`src/cadrumo/entrypoints/cli/_config/_custody_secret.py:220-239`)
calls `write_to_controlling_terminal` to display the mnemonic and then
`prompt_secret_no_echo` to collect the retype, returning that retyped value as the
`confirm` callback passed to `create_recovery_code`/`rotate_recovery_code`
(`_run_recovery_enrollment`, lines 404-456); a mismatch raises
`RecoveryVerificationError` -> a translated `retype_mismatch` refusal, leaving the prior
envelope untouched. `_run_recovery_enrollment` also refuses outright before any custody
read when `sys.stdin.isatty()` is false (lines 416-419), so create/rotate categorically
require an interactive controlling terminal.
`test_recovery_lifecycle_round_trips_without_serialized_mnemonic`
(`src/cadrumo/entrypoints/cli/tests/test_config_recovery_lifecycle.py:207-313`) proves the
mnemonic never lands in the persisted envelope file or any CLI stdout/stderr, and
`test_recovery_create_and_rotate_refuse_without_interactive_terminal` (lines 315-343)
proves a captured (non-TTY) `create`/`rotate` refuses cleanly and leaves the envelope
bytes unchanged.

## Notes

Verified by direct reads of `_custody_secret.py` and
`test_config_recovery_lifecycle.py`. Cited the coordinator's gate run (all certificate and
recovery tests passed in both parallel and serial lanes per the coordinator's summary)
rather than re-executing. RAG code index remains degraded/truncated; verification relied on
`rg` and direct file reads.
