---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:8643a768c58c2502ae6b2caf8e0620e8f74cca83eacf693adf2706fe79e8c432'
step_id: 'S43'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-full-repo-health-diagnostics-audit]]'
---

# W04.P13.S43 - Remove or justify unused Google API protocol variables

Scope: Close the Vulture candidate for `src/aeat/adapters/outbound/google/_api.py`
without changing Google API request execution behavior.

## Description

- Replace the `_ExecutableRequest.execute()` protocol's named optional
  parameters with a variadic structural method signature.
- Preserve `execute_request()` retry propagation through the Google client's
  supported `num_retries` keyword.
- Verify that Vulture no longer reports the Google API protocol names while
  leaving later W04.P13 dead-code candidates open.

## Outcome

The Google API executable request protocol no longer exposes dead protocol
parameter names that Vulture reports as unused. The adapter still requires an
`execute()` callable and still calls it with the configured Google client retry
count.

## Notes

Remaining Vulture findings belong to W04.P13.S44-S46 and were not changed in
this step.
