---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S28'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W04.P08.S28 Workflow Resume Resolution

Scope: extend the workflow application resume boundary so modelo visible selectors and exact work-unit targets resolve through the centralized modelo addressing facade before workflow-run selection.

## Description

- Export workflow resume target resolution helpers through the top-level workflow application package.
- Resolve visible modelo filing targets through public modelo addressing contracts before converting registry period tokens to workflow period tokens.
- Preserve the legacy exact work-unit resume path by resolving exact work-unit targets through the modelo facade and selecting the newest matching workflow run.
- Include visible work projection metadata in workflow-run ambiguity guidance so operators can move from a visible filing target to an exact run id without private selector knowledge.
- Cover visible target resolution, visible ambiguity refusal, exact work-unit latest-run compatibility, unified target resolution, revision selector routing, and projection guidance with real application tests.

## Outcome

The workflow layer now exposes centralized resume target helpers for natural modelo selectors and legacy exact work-unit ids. Focused Ruff, workflow resume tests, and public import smoke verification passed.

## Notes

The live worktree already contained adjacent unified resume-target code when this slice resumed; this record captures the verified application-layer state rather than claiming a narrower diff. CLI wiring remains tracked in later W04.P08 steps.
