---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-12'
modified: '2026-07-12'
body_hash: 'sha256:fb3107b74760725030c7fb94342263cafcdf7251e94882dd862c3d5f09a3b9f1'
step_id: 'S443'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# Refresh the stale Modelo 100 annual deadline explanatory prose to describe the tax-year registry key and following-year campaign dates, using the required documentation workflow.

## Scope

- `src/cadrumo/domain/deadlines/_plazo.py src/cadrumo/domain/deadlines/`

## Description

- Ground the deadline lookup and Modelo 100 campaign behavior with vaultspec-rag and live source inspection.
- Explain the exact tax-year and period-token match, including the following-year annual campaign date.
- State the no-future-window rule and the caller behavior when deadline data is absent.
- Run isolated drafting, technical review, editorial review, focused tests, and formal code review.

## Outcome

The public docstring now explains that annual Modelo 100 uses a tax-year registry
key even when its filing close date falls in the following calendar year. It
also documents the exact-match refusal of later windows.

## Notes

Focused annual-campaign and deadline coverage passed. The full documentation
gate remains separately blocked by generated API cross-reference warnings in
registry modules, not by this docstring.
