---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S142'
related:
  - '[[2026-05-20-schema-hardening-plan]]'
---



# `schema-hardening` `W09.P21.S142`

Closed the plan-format gate edge as an upstream vaultspec-core concern, not an
AEAT tax-code test.

- Modified: `.vault/plan/2026-05-20-schema-hardening-plan.md`
- Created: `.vault/exec/2026-05-20-schema-hardening/2026-05-26-schema-hardening-W09-P21-S142.md`

## Description

The missing-semicolon failure mode belongs in `vaultspec-core` because it is a
plan parser and vault-doctor convention check. The prior AEAT-side test attempt
was reverted as scope overreach, and this row now records that decision.

The actionable edge is to carry the regression request upstream to
`vaultspec-core` rather than adding another tax-project-local test.

## Tests

`uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-20-schema-hardening-plan.md`
reported 145 of 145 steps complete after closing this row.
