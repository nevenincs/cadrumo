---
tags:
  - '#exec'
  - '#release-pipeline-full-automation'
date: '2026-08-02'
modified: '2026-08-02'
body_schema: 'body-v1'
body_hash: 'sha256:c2635ac09d7b432f1c86d5f73de32e47a21039738956f1c45652968db00eae41'
step_id: 'S29'
related:
  - "[[2026-08-02-release-pipeline-full-automation-plan]]"
---
# Build the failure-alert emitter reporting a failed or refused release-path run to a channel the operator actually reads, defaulting to opening a labelled repository issue carrying the workflow, the run URL, the stage, and the refusal text so alerting works before OP-10 nominates a channel, with an optional operator-nominated webhook variable overriding the default once set, gate: uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q passes covering the default issue path, the webhook path once the variable is set, and idempotent re-alerting that updates an open alert rather than opening a duplicate per attempt

## Scope

- `dev/release/alerting.py`
- `dev/release/tests/test_release_alerting.py`

## Description

- Add the emitter with a typed `ReleaseAlert`, a pure `alert_payload` projection, and one side-effecting `emit_alert`.
- Default to a labelled repository issue, keyed on a per-run fingerprint so a re-run comments on the open alert instead of opening another.
- Override with an operator-nominated webhook once `CADRUMO_ALERT_WEBHOOK` is set.
- Never raise out of the CLI entry point.
- Add the S603 per-file exemption alongside the sibling release modules.

## Outcome

`uv run --no-sync pytest dev/release/tests/test_release_alerting.py -q` reports 12 passed; the wider `dev/release/tests`, `dev/deploy/tests`, `dev/ci/tests` run reports 425 passed. Lint and `ty check` clean.

## Notes

The default target is a labelled issue rather than a webhook, and that is the substantive choice. A webhook default would make alerting depend on OP-10 being decided, so the pipeline would run with the approval click removed and no alerting at all for exactly the window between the two - which is the one period where the new failure mode is live and unmitigated. An issue needs no secret, no variable, and no decision.

Deduplication is keyed on the RUN, not the workflow. Too broad a key collapses every future failure into one stale thread, and that failure looks identical to correct behaviour unless a test asserts the opposite direction, so `test_a_different_run_gets_its_own_alert` exists as the control for `test_a_second_alert_...`.

The webhook REPLACES the issue rather than supplementing it: two channels for one event trains the operator to read whichever is quieter, which is the same attention failure that flooding produces by a different route.

## Two real defects found by the tests

`_run_gh` did not catch `OSError`. An absent or unrunnable `gh` raises `FileNotFoundError` from subprocess, which would escape as a foreign exception type and defeat the caller's `except AlertError` - so the alert path would have crashed the failure handler it lives inside, replacing the original failure with its own. That is the exact inversion of this module's purpose, and the test that caught it is the one asserting the transport never replaces the original failure.

`main()` had no `--gh` flag, so the same test invoked the REAL `gh` on the developer's PATH and could have filed an issue against the live repository. Confirmed by query that none was created (`gh issue list --label release-alert --state all` returned empty), but the exposure was real and the fix is a `--gh` flag the test now passes explicitly. A test that reaches live infrastructure by omission is a hazard regardless of whether it fired this time.
