---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3f5a01dbe0d1a47a5258d667a843dc4a5d654e8456c31ea89136ab82b45d63ae'
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

Commit `088e3255a8` adds `CasillaCoverageCensus` and `compute_casilla_coverage_census`. The census makes the important distinction explicit: exact target derivation is measured independently of inbound RAG relevance, and it deliberately makes no claim about Pagefind or generated HTML parity.

## Tracking

- Projected casilla denominator: complete.
- Deterministic target derivation: complete.
- Spanish definition and non-Spanish locale axes: complete.
- Sparse relevance join retained as a separate axis: complete.
- Generated-index and browser parity: pending P06.S24/P04.S11; not run in this step.

## Notes

The implementation agent ran RAG discovery, owned-file history/diff checks, and `git diff --check`. Tests, builds, Pagefind compilation, deployment, and live probes were not run. The mandatory code-review pass is still pending; the step must not be marked closed until that review returns.
