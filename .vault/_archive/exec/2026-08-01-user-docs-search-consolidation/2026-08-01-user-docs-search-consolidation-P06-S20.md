---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:d270f6a8fc50a1192105e45b738545a65ccbe0f4bcf0efda3ef759b8856dc000'
step_id: 'S20'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

# Separate deterministic casilla enrollment from sparse semantic coverage by adding a coverage census for projected, exact-target, definition, locale, and relevance surfaces

## Scope

- `dev/docs/terminology/_coverage.py`

## Description

- Ground the coverage distinction with the accepted search ADR and the live terminology coverage implementation.
- Add typed frozen casilla coverage axes for projection, exact target derivation, definition, locale, and sparse relevance.
- Preserve the existing four-kind relevance widening report and factor its inbound-record join into one helper.

## Outcome

Commits `088e3255a8` and `a294ac35ed` add and harden `CasillaCoverageCensus` and `compute_casilla_coverage_census`. The census makes the important distinction explicit: exact target derivation is measured independently of inbound RAG relevance, and its strict models now enforce bounded counts, exact uncovered partitions, canonical surface order, and a shared projected denominator. It deliberately makes no claim about Pagefind or generated HTML parity.

## Tracking

- Projected casilla denominator: complete.
- Deterministic target derivation: complete.
- Spanish definition and non-Spanish locale axes: complete.
- Sparse relevance join retained as a separate axis: complete.
- Census value-object invariants: implemented and formally reviewed PASS.
- Generated-index and browser parity: pending P06.S24/P04.S11; not run in this step.
- Formal review of `a294ac35ed`: PASS with no CRITICAL, HIGH, MEDIUM, or LOW findings.

## Notes

The implementation agent ran RAG discovery, an AST parse, and `git diff --check`; the formal reviewer passed the invariant correction. Tests, builds, Pagefind compilation, deployment, sweeps, and live probes were not run. P06.S20 can close at the plan level, while P06.S24 remains the phase-level runtime acceptance boundary.
