---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
step_id: 'S69'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---
# Prove every reset phase boundary resumes honestly in a fresh child process

## Scope

- `src/cadrumo/application/tests/test_config_reset_recovery.py`

## Description

- Parameterize the recovery proof over eleven durable boundaries: `snapshotted`, `retention_approved`, `auth_clearing`, `auth_clearing_after_effect`, `auth_cleared`, `pointer_reconciling`, `pointer_reconciling_after_effect`, `pointer_reconciled`, `deleting`, `deleting_after_effect`, and `deleted`.
- Start reset in a real child interpreter with isolated settings and terminate it through `os._exit(91)` only after observing the actual journal repository return or the actual auth reset, strong logout, or bucket deletion return associated with the requested boundary.
- Load the persisted operation from the parent process and assert that its durable target phase matches the interrupted boundary without reconstructing or seeding reset state in the test.
- Assert after-effect interruptions preserve the honest external effect: the active pointer is already absent after pointer reconciliation and the bucket directory is already absent after deletion.
- Resume the interrupted operation in a second fresh child interpreter and validate its serialized result against the production reset model.
- Assert roll-forward completes the same operation idempotently with one deleted target, no active pointer, no bucket directory, and a journal equal to the child-process result.

## Outcome

- All eleven durable phase and after-effect boundaries terminated at the requested real production boundary with exit code 91.
- Every interrupted journal reloaded in the parent with the expected persisted phase.
- Every second fresh process resumed the same operation to `complete`; each result recorded one target and one deletion and ended at the `deleted` target phase.
- After-effect cases proved recovery from effects that had happened before their following completion record, rather than relying on an idealized phase-only interruption.
- The eleven parameter cases passed as part of a 14-test S68-S70 run: 14 passed in 100.87 seconds.

## Notes

- The harness observes actual production returns through `sys.settrace`; it does not replace functions, mutate modules, seed private boundary state, or reimplement reset transitions.
- Child-process argv contains only storage paths, boundary names, operation ids, and the non-secret retention reason; no credential or key material is transported on argv.
- No fake, mock, stub, patch, monkeypatch, skip, xfail, production failpoint, or mirrored business logic was introduced.
- No source, plan, user documentation, or generated documentation path was changed while curating this record.
