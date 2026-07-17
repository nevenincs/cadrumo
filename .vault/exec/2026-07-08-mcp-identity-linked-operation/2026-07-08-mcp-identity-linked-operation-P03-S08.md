---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Wire the identity gate into the pre-tool-use path byte-identically on the direct and execute paths, and name the active-profile label in the CONFIRM elicitation prompt

## Scope

- `src/aeat/entrypoints/mcp/_server.py`

## Description

## Outcome

Landed in commit 91bcc6d34b — block-first-mutation identity gate keyed off the declared risk table, byte-identical on direct+execute paths, re-armed on profile switch; harness.load counts as an identity read; CONFIRM elicitation echoes the label (I4). D7 regression from the P01 risk table fixed in 347ee6ec0d.

## Notes
