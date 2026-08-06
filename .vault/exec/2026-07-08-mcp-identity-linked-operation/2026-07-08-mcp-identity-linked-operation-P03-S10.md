---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:ff70e654d7d6d988ebc3a5baca1f530fd2f57a9600ef7a793130e74c0fc4edf7'
step_id: 'S10'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Add identity-gate tests: unconfirmed first mutation refuses, a prior identity read clears it, a profile switch re-arms it, and the refusals are byte-identical on both call paths

## Scope

- `src/aeat/entrypoints/mcp/tests/test_identity_gate.py`

## Description

## Outcome

Landed in commit 91bcc6d34b — block-first-mutation identity gate keyed off the declared risk table, byte-identical on direct+execute paths, re-armed on profile switch; harness.load counts as an identity read; CONFIRM elicitation echoes the label (I4). D7 regression from the P01 risk table fixed in 347ee6ec0d.

## Notes
