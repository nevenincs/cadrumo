---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S13'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the bundle-import crash-injection test proving an aborted prefix is invisible to the manifest pointer and the staging directory is cleaned up

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bundle_crash_windows.py`

## Description

Authored the bundle-import crash-injection tests: a corrupted archive is refused at the reader boundary before any bucket store is written; a near-complete truncation (built under the active master key, with an anti-tautology proof that the intact payload authenticates) is refused by the AEAD tag at import before provisioning. Both prove an aborted import leaves no manifest pointer and no partial bucket directory.

## Outcome

One test passes, pinning that validation precedes any bucket write; staging cleanup is a documented non-goal (no on-disk staging directory).

## Notes

None.
