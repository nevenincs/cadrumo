---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S47'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S47 Resume Projection Guidance

Scope: project resumable workflow runs back to visible filing targets and short exact identifiers for operator guidance.

## Description

- Add work-unit projection fields to resume target resolution output.
- Include short and full work-unit identifiers in ambiguity candidate lines.
- Include calculation-revision projection fields when resume resolution is selector-driven.
- Emit resolved source, visible filing year, registry period, and exact identifiers in CLI resume output.
- Verify semantic discovery over the workflow resolver, CLI resume command, and revision selector surfaces with `vaultspec-rag`.

## Outcome

Ambiguous resume flows now provide actionable operator guidance tied back to the visible modelo filing target and exact identifiers, without requiring private implementation knowledge.

## Notes

RAG searches initially timed out because the service writer lock was held. After a clean service restart and serialized queries, semantic discovery succeeded for the workflow resolver, CLI resume command, and revision selector implementation.
