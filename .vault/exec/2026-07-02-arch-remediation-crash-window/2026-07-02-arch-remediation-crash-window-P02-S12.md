---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S12'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the bundle-export crash-injection test proving the atomic rename yields no torn archive on a truncated tmp write

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`

## Description

Authored the bundle-export crash-injection test: prove a damaged sealed archive is rejected by the reader before decryption and that the writer refuses to overwrite an existing target; the anti-tautology partner proves an intact archive reads cleanly.

## Outcome

Three tests pass, pinning read-time damage detection plus refuse-overwrite.

## Notes

After the bounded reader fix landed, the test asserts the real guarantees: 30-80% truncation raises the documented typed payload error at read, member corruption raises the typed layout error, and the writer refuses to overwrite. The near-complete truncation residual is covered by the import AEAD test in S13.

End-truncation detection is a reported production gap in the reader (raw EOFError / silent accept); the test pins mid-stream corruption detection, which holds, and documents the truncation gap.
