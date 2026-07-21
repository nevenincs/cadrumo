---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
step_id: 'S464'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Correct stale `config unlock` claims in secure-storage rollout and review audits

## Scope

- `.vault/audit`

## Description

- Re-read the W20 custody API, rollout, guidance, and code-review audit findings against D1 and the live CLI.
- Replaced present-tense `config unlock` assertions with the canonical `config switch` contract.
- Preserved every historical `unlock` reference only where it explicitly explains the D1 hard retirement.

## Outcome

The relevant W20 audit trail no longer directs an operator to a command that the
current CLI rejects. It records the hard rename, the no-alias rule, and the
continuing internal session-unlock mechanics accurately.

## Notes

No production code changed. W22.P44.S465-S468 retain the contract, real-entrypoint,
locale, and user-guidance gates that prevent this audit drift from returning.
