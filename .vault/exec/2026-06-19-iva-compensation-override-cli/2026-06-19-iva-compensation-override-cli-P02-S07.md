---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

# Add a CLI conformance test exercising the override verb end to end and run the documented-command conformance gate

## Scope

- `src/aeat/entrypoints/cli/tests/test_iva_wallet_inspector.py`

## Description

- Add a CLI conformance test driving the override verb end to end and asserting the envelope reports the recorded override, amount, authority, divergence, reason, and evidence locator.
- Add companion tests asserting the verb refuses without `--confirm` and refuses a blank evidence locator.
- Repair a shared test-harness regression that blocked the override, seed, and correct CLI conformance tests: the profile-storing helper stored a UUID `profile_id` that no longer equalled the active bucket id, so the verb's active-bucket NIF resolver could not find the profile and every verb failed with a No-NIF refusal.
- Restore the `profile_id == bucket_id` (UUIDv4) invariant in the shared helper and align the CLI-invoking test sites plus the guidance-test bucket to that invariant.

## Outcome

- The override verb conformance test drives the verb end to end and passes; the documented-command conformance gate passes for the verb.
- The harness repair re-greened the previously-red seed, correct, override, and guidance CLI integration suites (twenty-five tests) that the profile-identity UUID change had broken at HEAD.
- Lint and format checks pass on the touched test files; tree-wide collect-only is clean.

## Notes

- The conformance tests were present at HEAD but red because a prior peer commit UUID-ified the test profile id without keeping it equal to the active bucket id. This was a pre-existing shared regression, not the override verb itself; it was absorbed and fixed because the override conformance gate could not pass without it.
- The test-support fix aligns with the working reference pattern already used by the engine-support helper, where the profile id and bucket id are the same UUID.
