---
tags:
  - '#exec'
  - '#agent-harness-refoundation'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-07-02-agent-harness-refoundation-plan]]"
---

# Add per-verb handoff deny rules over the family-granular persona scope

## Scope

- `src/aeat/entrypoints/mcp/_persona_scope.py`

## Description

- Promote the filing-handoff leaf set to ONE public declaration
  (`HANDOFF_LEAVES` + `is_handoff_command` in `_hitl.py`) and consume it
  from `_elicitation.py` (removing its private duplicate) — single
  declaration per the terminology discipline; three copies would drift.
- Add `PERSONA_HANDOFF_DENIALS` to `_persona_scope.py`: within the shared
  modelo family, only the VERIFIER may call the export/record-marker verbs;
  the preparer and reconciler are structurally denied, with an instructive
  refusal naming the owning persona. Closes the 2026-07-01 ADR's D3
  family-granularity caveat at exactly the boundary whose breach is
  irreversible (refoundation ADR R6(iii)); non-handoff verb discipline stays
  prose-level as decided.
- `is_handoff_denied` is designed for BOTH list-time filtering (a denied
  tool is not advertised) and call-time refusal — S20/S23 wire it.

## Outcome

Authored by the coordinator. Full MCP suite green (84 passed) including the
W02 executor's new harness-delivery tests; deny-semantics probe verified
(preparer/reconciler denied export+file, verifier allowed, calculate
unaffected). Commit `765def92d3`, three cohesive files.

## Notes

None.
