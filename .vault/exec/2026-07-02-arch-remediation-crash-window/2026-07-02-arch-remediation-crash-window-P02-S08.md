---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S08'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the mixed-key rotation crash-injection test first, interrupting rotation across envelope files, blob manifests, and the keystore and proving the probe-skip re-run recovers every partial state, using real adapters and simulating the interruption point rather than patching the primitives

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_rotation_crash_windows.py`

## Description

Authored the mixed-key rotation crash-injection test: seed real envelope files, a real EncryptedBlobStore blob, and a real keystore wrapped DEK under the old key; rotate only the envelopes to simulate the crash; prove the mixed state fails new-key-only reads for the un-rotated stores; re-run the full rotation across all three stores and prove probe-skip recovery; assert a converged re-run is a clean no-op.

## Outcome

Three tests pass with real crypto and no patched primitives; DEK value is preserved across the re-wrap and the blob payload survives byte-for-byte.

## Notes

The keystore leg's probe-skip re-wrap uses the sanctioned `wrap_dek`/`unwrap_dek` primitives; no storage primitive is mocked.
