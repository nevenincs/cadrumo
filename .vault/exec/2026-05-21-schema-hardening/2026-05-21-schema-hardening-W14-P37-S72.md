---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S72'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W14.P37.S72`

Generated the fresh residual singleton-warning census and candidate ranking
for Modelos 100 and 200.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W14-P37-S72.md`

## Description

The current Modelo 100 and Modelo 200 corpus has 2,262 distinct semantic
roles, 454 unmarked singletons, 28 intentional singletons, and zero emitted
singleton typo warnings. The next ranked slice is optional/numeric stripping
hardening, followed by token-group hardening, correction-axis extraction
readiness, and exact-family cadastral review.

## Tests

Ran an inline `uv run python` census using the committed registry loader and
the real singleton-warning emitter.
