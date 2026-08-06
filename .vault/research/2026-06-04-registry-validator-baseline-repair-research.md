---
tags:
  - '#research'
  - '#registry-validator-baseline-repair'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:a2e3c02f0f1637bbc292217451753ccc1524e5bd796e0bd36fbcabcb7092317b'
related:
  - "[[2026-06-04-registry-validator-baseline-repair-plan]]"
  - "[[2026-06-04-registry-row-width-pressure-plan]]"
  - '[[2026-06-04-registry-validator-baseline-repair-adr]]'
---

# `registry-validator-baseline-repair` research: `phase two research grounding`

## Question

How should the completed validator-baseline repair be grounded so the row-width-pressure blocker record and the repair plan have an explicit evidence path?

## Findings

This note is a vault-curation grounding record for a completed documentation-only validator baseline repair. It does not approve a new registry architecture or change validator semantics.

The linked plan and row-width blocker show the repair was scoped to preserving the existing reviewability baseline rather than raising it. The authority edge is captured in frontmatter so future semantic search can distinguish the blocker, repair, and review records.

## Recommendation

Keep this research bridge with the validator-baseline repair ADR and plan. Any future registry reviewability change should create a feature-specific ADR rather than treating this closeout as a broader baseline-raising precedent.
