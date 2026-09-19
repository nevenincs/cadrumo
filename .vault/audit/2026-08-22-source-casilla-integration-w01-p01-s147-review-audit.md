---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:256d0d817a592cec580450c49336023895d32d5728179d9454f04a3379afda93'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `source-casilla-integration` audit: `W01 P01 S147 provenance identity correction review`

## Scope

Formal no-edit review of the final S147 tree using source commit `03177b3da8`,
closure commit `e4a0d69445`, and the five findings recorded by S145 review
`755f67b935`. The source review was restricted to the S147-owned paths named in
its execution record. The unrelated registry-record-design and Modelo 036
registry/locale content sharing `03177b3da8` was inspected only for interaction
risk. The audit covered source-kind/binding-source coherence, explicit
non-binding semantics, complete and order-independent provenance identity,
first-write collision avoidance, exact encrypted-authority axes, rival-row
refusal, closed composite owners, persisted-read strictness, the local
cross-period composition regression, and source-commit traceability.

## Findings

### whole-provenance-default | high | A missing persisted provenance field still silently becomes an empty trace

`CalculationRevision.source_provenance` retains `default_factory=tuple`, and
`persist_calculation_revision`, `calculation_revision_identity_inputs`, and
`derive_calculation_revision_id` also retain an implicit empty default for the
same newly identity-bearing axis. An adversarial current-shape serialization
with the entire `source_provenance` key deleted passes
`CalculationRevision.model_validate_json` and reconstructs an empty tuple when
its identity was derived for an explicitly empty trace. This is read tolerance
for an older application-written shape, not an explicit non-binding assertion.
It contradicts the repository's zero-legacy rule and leaves both writers and the
persisted carrier on precisely the default/shim path that S147 removed from each
`CalculationSourceRef.binding_source` row. The new missing-row-field tests reject
omitted `resolver_id` and `binding_source`, but do not probe omission of the
whole provenance collection. S141 remains blocked while current empty provenance
and an absent provenance declaration are indistinguishable at the application
and encrypted-read boundaries.

### persistence-contract-docstring | medium | Persistence documentation states the opposite provenance identity policy

`persist_calculation_revision` now passes `source_provenance` into the sole
revision-id builder, but its production docstring still says the trace is
additive and does not participate in `derive_calculation_revision_id`. The same
docstring's earlier identity-field list omits source provenance. The
implementation and tests correctly make the full sorted trace identity-bearing;
the stale contract text can cause a future caller or reviewer to restore the
first-write-wins collision S147 is meant to close.

### mixed-source-commit | low | S147 source ownership is documented but not isolated in one Step commit

The S147-owned source changes landed in `03177b3da8` beside unrelated
registry-record-design and Modelo 036 registry/locale work, violating the
one-Step/one-source-commit execution contract. The execution record names the
exact owned paths and the separate closure commit records the incident without
claiming topology compliance. `git show --check` passes for both commits, and no
runtime or import interaction was found between the unrelated paths and the
source-connectivity surface, so this is a traceability deviation rather than a
code-integrity blocker. It cannot be repaired without rewriting shared history.

## Recommendations

- Block S141 acceptance until `source_provenance` is required on the persisted
  `CalculationRevision` shape and on the persistence and sole identity-builder
  APIs, every caller explicitly supplies either a real trace or `()`, and
  encrypted-load coverage proves deleting the whole key is refused. Do not add
  an upgrader, fallback, or pre-validation hydration path.
- Correct the `persist_calculation_revision` docstring in the blocking repair so
  it names complete canonical source provenance as a calculation-revision
  identity axis and explains why distinct traces cannot collide under catalogue
  idempotency.
- Retain the truthful concurrency incident in the S147 execution record and use
  exact-path review evidence for this historical mixed commit; do not rewrite,
  split, or recommit another agent's shared history.

Verification evidence: `git show --check` passed for `03177b3da8` and
`e4a0d69445`; Ruff passed across all S147-owned Python paths; the union of the
S145 and S147 selected changed-test surface passed `200 passed`; the local
cross-period module was included in that green run. Direct adversarial probes
proved both application and persisted rows reject missing, null, or contradictory
binding axes for canonical sources, accept only explicit `binding_source=None`
for non-binding kinds, and reject a non-binding kind claiming a binding source.
Both reserved raw composite strings were refused while canonical merge output
carried `CompositeSourceResolverId`. Mutating resolver, binding source, source
kind, source reference, fingerprint, or dependency treatment changed the
revision id; reversing provenance order did not. Exact authority probes rejected
wrong resolver, source kind, source reference, fingerprint, revision id, rival
resolver rows, and rival fingerprint rows. The sole failing adversarial
expectation was whole-field omission: `missing_whole_field_accepted=True`.
