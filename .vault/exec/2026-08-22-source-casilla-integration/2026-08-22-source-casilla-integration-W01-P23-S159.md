---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:e8d47a281d393ad59aeaba351306f53f50db46301855d968a86a75bb7f7ec8f7'
step_id: 'S159'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# make the census and ratchet modules clean on their intended static type-check surface

## Scope

- `dev/source_connectivity`

## Description

- Replace lazy facade imports with the concrete source-connectivity type authority.
- Type census manifests at governance, locator, and assignment boundaries.
- Narrow AST nodes at structural invariants and retain explicit AST mapping types.
- Verify the complete development surface with `ty` and Ruff.

## Outcome

The source-connectivity development surface now passes its intended static type check with no diagnostics. The changes preserve the live census result of 448 exactly-once assignments and make malformed AST assumptions explicit at the structural-discovery boundary.

## Notes

One full-suite run overlapped a concurrent CLI migration deleting a policy module and failed while enumerating that disappearing path. A subsequent authoritative comparison completed successfully against the settled tree; the failure was filesystem churn, not a census or type defect.
