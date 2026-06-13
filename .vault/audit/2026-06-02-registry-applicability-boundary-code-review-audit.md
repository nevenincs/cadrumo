---
tags:
  - '#audit'
  - '#registry-applicability-boundary'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
  - "[[2026-06-02-registry-applicability-boundary-audit]]"
---

# `registry-applicability-boundary` Code Review

## APPLICABILITY-S23-001 | PASS | Audit-only slice preserves applicability code

No issue found. The slice-owned diff records the extraction assessment
and closes P04.S23 while leaving
`src/aeat/domain/calculations/registry/_applicability.py` untouched
despite active peer formatting WIP.

## APPLICABILITY-S23-002 | PASS | Canonical rule-table ownership is preserved

No issue found. The audit keeps `_MODELO_APPLICABILITY_RULES` as a
single canonical definition and does not propose duplicating or relocating
the rule table without an ADR and canonical-test change.

## APPLICABILITY-S23-003 | PASS | Public facade compatibility is preserved

No issue found. The recommendation preserves both
`aeat.domain.calculations.registry` and
`aeat.domain.calculations.registry.applicability` public surfaces, and
sets focused tests for future extraction commits.
