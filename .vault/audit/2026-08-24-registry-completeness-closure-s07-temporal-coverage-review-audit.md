---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d932e67b4c5b6c8dc6fd3737b2fadc386e21324bf5feec69090324188be69832'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# `registry-completeness-closure` audit: `S07 temporal coverage review`

## Scope

Independent review of `ff7c870d3d` for the S07 temporal coverage composer, its
public application-registry facade, its strict data contract, authority-grade
selection, and focused tests. The live bundled authority produced 102 rows and
no refusals; a controlled real-authority mutation produced the declared
ungraded refusal.

## Findings

### temporal-evidence-identity-is-untyped | medium | Public validated evidence accepts fabricated registry coordinates

`TemporalRevisionCoverage` exposes `modelo`, `revision`, and `period` as
minimum-length strings and accepts every filing year from 1 upward. As a result,
a public `validated` row with `modelo="not a modelo"`, a revision containing
spaces, a non-registry period, and filing year 1 is accepted. This bypasses the
registry identifier and selector grammar at the application boundary while the
row is described as validated evidence. The S07 contract must retain the
registry's typed modelo, revision, period, and filing-year semantics.

### composer-refusals-are-unproven | medium | The explicit refusal contract has no composer-level regression proof

The composer declares five refusal outcomes but the focused tests exercise only
the successful Modelo 036 path and an isolated row-model validation failure.
They do not make an ungraded revision, a selection failure or mismatch, or a
declared-grade snapshot refusal reach `compose_temporal_coverage`. The runtime
probe showed an ungraded row can be preserved after a controlled real-authority
mutation, but no committed regression test would fail if that handling, the
failure code, or its preserved denominator row regressed. The release predicate
depends on loud, per-revision refusal evidence, so each composer refusal branch
needs a mutation-backed proof.

## Recommendations

- Complete `W01.P02.S42`: constrain temporal evidence coordinates with the
  canonical registry identifier, period, and filing-year types, then prove both
  invalid-coordinate rejection and every composer refusal outcome with real
  authority mutations.
- Keep S07 open for review closure until the S42 implementation and its own
  independent review pass.
