---
tags:
  - '#exec'
  - '#agent-harness'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-02-agent-harness-plan]]"
---

# status:done (commit 436e5c8ca) - state the verifier context-isolation invariant testably and runtime-agnostically, naming the degraded self-report fallback explicitly

## Scope

- `src/aeat/_data/agent/personas/verifier.md`

## Description

- State the verifier context-isolation invariant: the verifier's context
  must be constructible from tool-result JSON alone, never from the
  preparer's transcript.
- Document structural enforcement where the runtime supports isolated
  invocation, and name the degraded self-report fallback explicitly as
  reduced trust, never as equivalent to structural isolation.

## Outcome

Landed in commit `436e5c8ca`.

## Notes

None.
