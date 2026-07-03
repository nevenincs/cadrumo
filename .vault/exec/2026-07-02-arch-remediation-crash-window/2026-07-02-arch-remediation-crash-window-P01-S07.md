---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Confirm the master-key rotation ordering at HEAD and resolve the mixed-key window across envelope files, blob manifests, and the keystore, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the master-key rotation ordering at HEAD across the two rotation primitives and the keystore DEK; recorded per-store probe-skip idempotency and the absence of a single orchestrator. Resolved the mixed-key window across envelope files, blob manifests, and the keystore in the reference body.

## Outcome

Confirmed guarantee: per-store probe-skip idempotent recovery of the mixed-key window; the keystore DEK re-wrap is value-preserving and custody-owned, and secure_objects is intentionally not rotated.

## Notes

No application-layer orchestrator wires the two ciphertext rotation primitives together; the mixed-key recovery is a re-run of both.
