---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:292de0f9a01e29fe205fe79a96c874e4e38eef8bc696127c9c672ed7e3b65d46'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-W01-P01-S140]]"
---

# `source-casilla-integration` audit: `W01.P01.S140 Calculation Route Review`

## Scope

Reviewed commit `e36fb8146d` against the accepted connectivity ADR, the S140
execution record, and the production modelo calculation path. The review traced
pre-mesh profile, borrador, and IVA-wallet resolution; the ordinary mesh;
conditional Modelo 303 annual-summary composition; post-mesh prorrata and bienes
de inversión composition; the manual-input pseudo-owner; source-kind
dispositions; public exports; and the replacement reflective resolver census.

Verification comprised 18 focused route/enrollment/parity tests, five live
missing-source-mesh tests, Ruff over every touched Python path, a production
import-boundary run, direct exported-class enumeration, and adversarial ownership
mutations. The focused tests and Ruff passed. Import Linter kept nine contracts;
its one broken layered-architecture contract consists of pre-existing paths
outside the S140 diff.

## Findings

### ownership-identity-validation | high | The canonical validator accepts renamed and invented resolver owners

`validate_calculation_route_resolver_ownership` validates unique resolver ids,
unique source owners, and the enrolled/deferred/reserved partition, but it never
validates a typed row against its `resolver_type` contract and never restricts a
`resolver_type=None` pseudo-owner to the one canonical manual-input row. Direct
mutation probes proved that all three of the following are accepted: replacing
the profile resolver id with `renamed-profile`, replacing its resolver type with
`None`, and moving it from `pre_mesh` to `mesh`. The first two contradict the
S140 outcome that resolver identity is class-owned and that manual input is the
sole pseudo-owner. The third is eventually refused only if that production path
executes; the declaration validator itself accepts the invalid stage identity.

The current-state assertions do not close this hole. They compare the present
constant to class attributes and assert the present manual row, but the explicit
adversarial test covers only duplicate ids, duplicate sources, removal of the
last row, and adding a deferred source. It contains no renamed-id, class-contract,
additional-pseudo-owner, or wrong-stage mutation. S145 would persist resolver
identity on top of a declaration API that currently certifies these invalid
identities, so this is release-blocking for S145.

### production-route-consumption | low | Runtime composition asserts every declared resolver stage

The canonical declaration is not a passive parallel census. Profile and
borrador resolution and the IVA-wallet gate call
`require_calculation_route_resolver` at `pre_mesh`; every ordinary resolver in
`_resolve_bucket_source_mesh` passes through the guarded `resolve_declared`
closure; the conditional Modelo 303 annual-summary resolver explicitly uses the
`conditional` stage; and prorrata plus bienes de inversión are guarded at
`post_mesh`. Source policy and unhandled-source diagnostics also project their
enrolled and pre-mesh sets from this declaration. The focused live-path tests
passed without a calculation-result delta.

### resolver-and-disposition-coverage | low | Current production classes and every BindingSourceKind are represented exactly

Independent enumeration of public `resolve`-bearing classes found the 21 typed
production resolver classes plus the protocol and no unclassified non-mesh
resolver. The route additionally owns manual input through exactly one present
pseudo-row. `CALCULATION_ROUTE_SOURCE_DISPOSITIONS` covers every
`BindingSourceKind`; enrolled ownership is duplicate-free, while deferred and
reserved kinds have no present owner. The previously omitted conditional Modelo
303 annual-summary resolver is represented explicitly.

### reflective-gate-independence | low | The replacement reflective test remains non-tautological

The expected resolver set is projected from the runtime-consumed route, while
the observed set is discovered independently from four package `__all__`
surfaces and checked structurally for `resolver_id`, `owned_sources`, and
`resolve`. An omitted export, a newly exported resolver, a removed class, or a
protocol-shape drift therefore changes only one side and fails. The reflective
test is not merely comparing two projections of the route declaration.

### public-boundaries-and-baseline | low | S140 introduces no new forbidden import edge

The application modelo facade intentionally exports the route authority and its
read-only projections, matching the execution record's public-authority claim.
All new dependencies remain between application peers or point inward to core.
The repository import-linter baseline remains broken by unrelated existing
application-to-adapter edges, none introduced or touched by `e36fb8146d`.

## Recommendations

Before S145 starts, make `validate_calculation_route_resolver_ownership` fail
closed on all declaration identity dimensions:

- a typed row's `resolver_id` and `owned_sources` must equal the referenced
  resolver class attributes;
- `resolver_type=None` must be accepted only for the exact manual-input owner;
- the manual-input owner must remain unique and must not carry a resolver class;
- stage ownership must be constrained so a resolver cannot be relabelled without
  refusal at declaration validation time.

Add adversarial tests for renamed resolver id, mismatched resolver class/source
contract, invented pseudo-owner, typed manual owner, and wrong-stage movement.
Retain the existing independent reflective-export tests and focused live-path
tests. Re-review the remediation before allowing S145 to persist resolver
identity.
