---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:f3a003ff6413e4d1f97ddbedcead0bcc5d53bb449fefc4227965d08fdfcb1c26'
step_id: 'S09'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Author the create-profile crash-injection test proving the atomic-create rollback removes partial buckets at every window including K-without-S

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_bucket_crash_windows.py`

## Description

Authored the create-profile crash-injection test: force a genuine schema-validation failure at the encrypted-record write (an incomplete fact set) after the span mints the wrapped DEK, and prove the atomic-create rollback clears the minted DEK, the manifest, and the pointer; the anti-tautology partner proves a successful create lands the DEK.

## Outcome

Two tests pass, pinning the K-without-S rollback across the keystore, manifest, and pointer.

## Notes

None.
