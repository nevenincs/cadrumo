---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Add per-session identity-read state and the block-first-mutation gate, re-armed on any profile-changing verb, refusing an unconfirmed first mutating call with an instructive localized refusal keyed off the risk table

## Scope

- `src/aeat/entrypoints/mcp/_identity_gate.py`

## Description

## Outcome

Landed in commit 91bcc6d34b — block-first-mutation identity gate keyed off the declared risk table, byte-identical on direct+execute paths, re-armed on profile switch; harness.load counts as an identity read; CONFIRM elicitation echoes the label (I4). D7 regression from the P01 risk table fixed in 347ee6ec0d.

## Notes
