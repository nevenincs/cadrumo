---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:70bebc4bffa44735be9dc0769e4a4cad18db54517b92ba1e79f8d5e09299a3ad'
step_id: 'S08'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
  - "[[2026-08-05-modelo-parity-rollup-five-domain-contract-adr]]"
  - "[[2026-08-05-modelo-parity-rollup-s08-review-audit]]"
---
## Scope

- `src/cadrumo/application/registry/_conformance.py`
- `src/cadrumo/application/registry/__init__.py`
- `src/cadrumo/application/registry/tests/test_conformance_provenance_projection.py`

## Description

- Project the S07 construct evidence audit into each validated conformance revision row.
- Keep revision `model_law_coverage` as the evidence floor and expose construct evidence as a separate typed axis.
- Project lossless S06 casilla producer traces, including relation-specific ids and provenance, without flattening multiplicity.
- Preserve schema-derived traces on degraded reads while withholding authority-dependent construct and coverage axes.
- Add real bundled-registry assertions for exact construct coordinates, producer traces, relation multiplicity, and degraded-read boundaries.

## Outcome

S08 application-level conformance projection is implemented and verified. Every validated revision row carries both the revision evidence floor and a distinct construct ledger; every row carries the typed per-casilla producer trace. Degraded profiles carry schema traces with `registry_validated=false` and leave validated construct evidence unmeasured.

## Notes

The dev-side flattened renderer still needs a follow-up consumer projection and remains peer-owned in this shared worktree. A scoped basedpyright run over the existing application module retains 45 pre-existing dictionary-comparator type errors at the existing comparison constructors; the new projection test reports zero errors. No registry data, unrelated peer work, staging, or commits were changed.

Verification: 25 existing conformance-profile tests passed; 2 S08 projection tests passed; Ruff and formatting passed on all S08-owned source and test files; basedpyright passed on the new S08 test; `git diff --check` passed.
