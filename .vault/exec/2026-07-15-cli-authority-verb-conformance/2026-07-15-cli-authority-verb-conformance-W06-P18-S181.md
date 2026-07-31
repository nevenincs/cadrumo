---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:d4ed81f01824c67bba6deb1424e9f72fc68f5df0cd5841e0baffa65de14728ec'
step_id: 'S181'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run application and live CLI profile-export suites across real fresh processes, target contention, schema-derived SAR categories, and every crash window

## Scope

- `src/cadrumo/application/user_profile/tests/`
- `src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py`
- `src/cadrumo/entrypoints/cli/tests/test_profile_subject_access_request.py`

## Description

- Run the profile application suite and both named CLI export suites under an explicit execution-marker selection covering both lanes.
- Confirm a non-zero collected count before reading the result line.
- Re-run the same scope under the serial selection.
- Collect the OS-keychain remainder explicitly, since this is the one scope in the phase where that remainder is non-empty and must be reported rather than implied.

## Outcome

Verdict: SATISFIED for everything the agent logon can exercise, with a named and unverifiable remainder.

Command: `uv run --no-sync pytest -q -rs -p no:cacheprovider -n auto --dist=loadfile --tb=short -m "(unit or integration) and not serial and not os_keychain and not external_tool and not perf" src/cadrumo/application/user_profile/tests src/cadrumo/entrypoints/cli/tests/test_profile_export_roundtrip.py src/cadrumo/entrypoints/cli/tests/test_profile_subject_access_request.py`.

Collected 271, passed 271, failed 0, skipped 0. Exit line: `271 passed in 117.37s (0:01:57)`, exit code 0. HEAD at run time was `82a04ead90bef5de5ae2e2970648c32aac9be03c`. The serial selection collected nothing.

The OS-keychain selection collected four cases out of 275 and they were NOT run: first login minting a resumable persisted session, the two idempotent-guard retries, and strong logout removing the keychain half of the session. Those four assert against the operating system credential store itself, which is a property of the logon session rather than of the dependency set. This agent runs under a network logon whose credential calls the real backend refuses, so no keychain-custodied session key can exist here at all. They are reported as unverified in this environment. They were not skipped by the suite, not marked expected-to-fail, and not asserted to pass; they were deselected by marker and are meaningful only in an interactive desktop session.

## Notes

The semantic code index was degraded for the whole of this wave, reporting itself healthy while carrying roughly a fifth of the tree. No conclusion in this record rests on a semantic search result.

The fresh-process, contention, and crash-window claims are carried inside the passing 271; the four unverified cases are custody cases and do not overlap those claims.
