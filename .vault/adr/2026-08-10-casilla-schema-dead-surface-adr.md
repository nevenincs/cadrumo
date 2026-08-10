---
tags:
  - '#adr'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:fb565261625be64d85b840d5c1db43631cd11469beacf3ab33c6690750647a79'
related:
  - "[[2026-08-10-casilla-schema-research]]"
---

# `casilla-schema` adr: `delete or wire the dead verification surfaces` | (**status:** `accepted`)

## Problem Statement

The three most obviously-named answers to "did this filing verify correctly" are facade-exported and dead in production; registry data even declares one of them a consumer (`2026-08-10-casilla-schema-research`, B-02). Design work stalled twice by building against them. The standing no-legacy rule mandates deletion over bridging.

## Considerations

- `application/verification` exports only `verify_declaracion`; zero production importers; its function overlaps the live reconcile flow, which consumes the same inbound declaracion parse.
- `verify_export` / `DeclaracionVerifyVerdict` are the production READ path for fichero-BOE bytes and the deserialiser the roundtrip gate drives; deleting them would leave the roundtrip gate testing a path nothing uses.
- The strict `resolve_bound_inputs_by_casilla_id` duplicates the permissive sibling production chose; unrouted-input concern is already owned by the live advisory channel.
- `_BINDING_SOURCE_TO_READINESS` mislabels 21 of 27 source kinds and is stranded in entrypoints.

## Considered options

- **Bridge or deprecate any of them** - rejected outright: forbidden by the no-legacy rule.
- **Delete everything dead uniformly** - rejected for `verify_export`: a read path with a live roundtrip gate is dead capacity one step from being a tripwire.
- **Per-surface adjudication: delete three, wire one** - chosen.

## Constraints

- The `application/verification` deletion runs only after one overlap check against the live reconcile flow; any semantics the live flow lacks move INTO a living surface - never a second surviving package.
- Owner mandate (2026-08-10): where the dead package holds semantics the live flow lacks, placement is engineered case by case at adjudication time; in EVERY case no legacy surface is maintained and all superseded code is removed. There is no standing answer to pre-empt the adjudication.
- The deletion commit sweeps the registry `application_links` TOML rows that name the package as consumer.
- Facade `__all__` baselines update in the same commits as their deletions.

## Implementation

(1) Adjudicate `verify_declaracion` against the live reconcile surface. The candidates to check are the reconcile modules in `application/modelo` that consume the same inbound declaracion parse - `_reconcile.py` with its `_pulled_filing_reconcile.py` and `_m303_m349_reconcile.py` companions. Method: enumerate what the dead function produces (discrepancy classification, coverage computation, status derivation, narrative) and confirm each is either produced by the live surface or not worth keeping; the acceptance criterion for S29 is a written per-capability disposition table in the exec record, each row marked covered, absorbed-into-reconcile, or dropped-with-reason. Then delete the `application/verification` package, its tests, and the registry `application_links` TOML rows naming it as consumer (grep the registry tree for the package path to enumerate them) in one commit, absorbing any missing semantics into the reconcile surface first. (2) Delete the strict `resolve_bound_inputs_by_casilla_id` and both of its facade exports; a future hard refusal, if ever wanted, belongs in the verify gate. (3) Wire `verify_export` into `export_draft` as a post-write self-check - write bytes, re-read through the real parser, require a MATCH verdict or raise - converting the dead export reader into a byte-drift tripwire that also keeps the roundtrip gate honest. (4) Delete `_BINDING_SOURCE_TO_READINESS`; the readiness wording derives from a total `BindingSourceKind` mapping in the application layer under the blocker-spine ADR's totality pattern, localised through the locale catalogues.

## Rationale

Dead-but-exported surfaces actively misdirect design - that is a measured cost, twice paid. Deletion follows the standing rule; the one wiring converts the only dead symbol with a live gate into enforcement. Each disposition was adjudicated per symbol rather than sweeping uniformly, which is what the architecture-boundaries rule requires for facade changes.

## Consequences

Gains: the public surface stops lying; one new export tripwire; the entrypoints readiness-dict debt clears as a side effect. Costs: one semantic overlap check before the package deletion; if it surfaces missing semantics, their placement is engineered case by case under the owner mandate above, with the invariant that the dead package is removed regardless. Pitfall: partial deletion - removing the package but leaving the registry consumer rows or facade entries reintroduces the lie in data.
