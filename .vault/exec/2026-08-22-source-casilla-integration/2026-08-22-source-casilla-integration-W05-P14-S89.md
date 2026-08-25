---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:67fb0376f493b0014ef63db48f3b832e321154899dfcb3cc035d58fa08cc5816'
step_id: 'S89'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# preserve grouping, row index, binding identity, source identity, and fingerprint through ingress

## Scope

- `src/cadrumo/domain/modelos/_calculation_revision.py`
- `src/cadrumo/domain/calculations/_row_source_identity.py`
- `src/cadrumo/domain/modelos/tests/test_calculation_revision.py`
- `src/cadrumo/adapters/persistence/profile/tests/test_source_mesh_revision_roundtrip.py`

## Description

- Extend the existing `RowSourceIdentity` carrier with optional exact row-set grouping.
- Include a present grouping in the canonical secure revision projection and the revision identity hash.
- Rehydrate the secure domain payload and prove the real encrypted calculation-revision repository retains the grouping, coordinate, source identity, and fingerprint.

## Outcome

The established `CalculationSourceResolution` to calculation-action to
`persist_calculation_revision` handoff continues to carry the existing row
identity carrier unchanged. A worksheet-originated identity can now retain its
exact registry grouping together with its existing binding-and-row coordinate,
opaque source identity, and content fingerprint. A grouping change produces a
distinct calculation-revision id; non-worksheet identities omit the optional
axis without changing their prior canonical representation.

## Notes

No resolver, source authority, generic persistence store, hostile-row refusal,
or worksheet export/pull round trip was added. The mixed shared-worktree commit
`f769e9ff9f` captured the production and domain-test portion while this Step
was still running; this scoped follow-on records the independent encrypted
repository proof and tracking updates without rewriting that commit.

Focused real tests passed for the domain carrier and encrypted repository.
Scoped Ruff passed. Focused `ty` reported two pre-existing unsound-return
diagnostics in unchanged row-casilla validators; no type diagnostic originated
from this Step's carrier axis.
