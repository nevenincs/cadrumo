---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

# Confirm the create-profile write ordering at HEAD and resolve the rollback-covers-every-window-including-K-without-S cell, updating the reference body with the finding

## Scope

- `.vault/reference/2026-07-02-arch-remediation-crash-window-reference.md`

## Description

Read the create-profile write ordering at HEAD across the create storage span and the profile repository; recorded that the wrapped DEK (K) is minted by the span before the encrypted record (S), and that create sequences dirs then manifest then pointer then record. Resolved the rollback-covers-every-window-including-K-without-S cell in the reference body.

## Outcome

Confirmed guarantee: the two-layer rollback (span DEK/keystore cleanup plus repository dir/manifest/pointer rollback) covers every window including K-without-S.

## Notes

The matrix ordering `dirs, then K, then S, then M` was wrong; the HEAD order is K (span), dirs, M, pointer, S. Recorded in the reference.
