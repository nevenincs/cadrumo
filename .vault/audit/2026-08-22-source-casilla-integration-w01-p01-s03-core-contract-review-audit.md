---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:260a2757f97acc3d453958ad6af33a3f03afe45cf31ab9495ef81d915c7e6116'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `W01.P01.S03 core contract review`

## Scope

Commit `6a787a4bf5` was audited against the accepted source-casilla integration
ADR, `W01.P01.S03` of the implementation plan, the canonical source-kind and
secure-storage rules, and the requirement that a `connected` census disposition
be supported by resolver ownership, encrypted `CalculationRevision`
anti-tautology, and operator reachability. The review is limited to commit-owned
changes in `src/cadrumo/core/source_connectivity.py` and its Vaultspec execution
closure. It does not review or modify concurrent worktree changes.

## Findings

### disconnected-attestations | high | The connected proof does not prove that its three components describe one production path

`SourceConnectivityConnectedProof` requires three populated models, but there is
no shared source, resolver, candidate, revision, or execution identity joining
them. `SourceConnectivityOperatorReachabilityProof` does not identify the
resolver it observed, and `SourceConnectivityEncryptedRevisionProof` does not
identify the source kind, resolver, source identity, fingerprint, or persisted
provenance channel whose round trip it claims. The `command` field accepts any
non-empty prose rather than a stable supported-command identity. A connected row
for candidate `inventory` therefore validates with `BindingSourceKind.PROFILE`,
an unrelated revision proof id, a different entrypoint id, and command `anything
at all`. Every evidence tuple may also point to the same implementation file;
the model neither distinguishes executable proof from implementation evidence
nor checks that evidence belongs to the asserted identity. This is a
non-tautology failure: three independent attestations can be assembled into a
`connected` claim without demonstrating that one enrolled resolver carried the
candidate through encrypted revision persistence and the stated operator path.

### literal-true-coercion | medium | Integer one satisfies every supposedly strict proof assertion

The proof assertions use `Literal[True]`, but Pydantic accepts integer `1` for
`strict_round_trip`, `encrypted_at_rest`, `anti_tautology_mutation`, and
`resolver_observed` even under `STRICT_FROZEN_CONFIG`. A focused runtime probe
constructed `SourceConnectivityEncryptedRevisionProof` with all three fields set
to `1` and validation succeeded. The contract therefore does not provide a
strict boolean boundary for loaded machine-checkable census data.

### stale-connected-proof-docstring | low | Census-row documentation says the S03 contract is absent after introducing it

The `SourceConnectivityCensusRow` docstring still says connected-slice proof is
intentionally absent until a separate contract is introduced. S03 introduces
that contract and adds the field immediately below, so the public model's own
documentation now contradicts its behavior.

### connected-iff-proof-presence | low | Disposition and proof presence are correctly coupled in both directions

The row validator refuses `connected` without `connected_proof` and refuses
`connected_proof` for every other disposition. Nested proof components are
required, frozen typed models with non-empty evidence tuples. This establishes
presence equivalence, but it does not close the high-severity relational finding.

### canonical-source-kind-layering | low | Resolver ownership reuses the canonical core taxonomy without introducing a parallel enum

`SourceConnectivityResolverOwnershipProof.source_kind` uses
`BindingSourceKind` from the sibling core aggregation module. Import and module
compilation probes succeed, and the change adds no registry-, application-, or
persistence-layer dependency to core. No duplicate source taxonomy or stored
token rename is introduced.

### scope-and-network-boundary | low | S03 stays within its proof-model scope and performs no HTTPS dereference

The commit changes only the core proof contract plus its plan and execution
records. It does not export the models through the core facade (S04), add the
phase's full refusal test module (S05), resolve sources, persist revisions, or
perform network I/O. `SourceConnectivityGrounding` continues to parse locator
shape only. The prior medium HTTPS trust-boundary finding therefore remains open
for any future dereferencer but is not widened by S03.

## Recommendations

- For `disconnected-attestations`, bind all proof components to one stable
  connection identity. At minimum, make operator reachability name the exact
  resolver and canonical source kind it observed, and make revision proof name
  the same source/resolver plus the persisted source identity and fingerprint or
  provenance channel. Represent the supported operator entrypoint/verb as a
  stable typed identity rather than unconstrained prose. Require
  purpose-appropriate executable evidence identities so an implementation
  locator alone cannot attest the behavior it describes.
- For `literal-true-coercion`, use a boundary that rejects numeric and textual
  truthy substitutes and prove JSON/Python inputs `1`, `"true"`, and `"1"` are
  refused while the boolean singleton `true` is accepted.
- Correct `stale-connected-proof-docstring` while addressing the blocking
  contract finding.
- Preserve the correct connected/proof bidirectional invariant, canonical
  `BindingSourceKind` ownership, S03 scope boundary, and non-dereferencing HTTPS
  behavior while correcting the findings.
- Do not begin S04 while `disconnected-attestations` remains open. Focused
  regression coverage needed to close S03 findings may accompany corrective S03
  work without broadening into S05's full planned matrix.
