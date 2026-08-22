---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:9baf4833595caa62bd601eeaa155b0e806d6efc672b223db0b3ece4b66d90623'
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

### relational-binding-correction | low | Corrective commit binds candidate, source, resolver, revision, and evidence identities

Corrective commit `995d8d391f` introduces one shared
`SourceConnectivityConnectionIdentity` and requires the resolver, encrypted
revision, operator, executable-evidence, and census-row candidate identities to
agree. Focused mutation probes independently changed candidate id, source kind,
source object id, resolver id, and calculation revision id. Every mismatch was
refused. Repository implementation files, HTTPS locators, and non-test modules
were also refused as executable evidence. This closes the cross-component
identity portion of `disconnected-attestations`.

### enrollment-evidence-remains-asserted | high | Deferred sources and nonexistent executable evidence can still claim a production connection

The correction does not establish that the shared source kind is actually
enrolled or that its executable evidence exists. A focused probe built a
`connected` row for candidate `inventory-stock` using the currently deferred
`BindingSourceKind.RELATED_PARTY_OPERATION`, resolver `resolver-a`, command id
`anything`, and locator
`src/cadrumo/fake/tests/test_does_not_exist.py:999`. The complete row validated.
`SourceConnectivityExecutableEvidence` checks only the locator string shape; it
does not establish repository existence, a test identity, or a test-to-command
and test-to-resolver relationship. Likewise, `command_id` is merely a stable
token, not an identity drawn from or checked against the supported CLI command
surface. Consequently one internally consistent but invented identity bundle
still upgrades a deferred source to `connected` without live resolver enrollment
or executable operator and persistence proof. The original
`disconnected-attestations` HIGH finding is narrowed but remains open.

### strict-true-correction | low | Corrective strict booleans reject integer and textual substitutes

The `_StrictBoolean` fields plus explicit truth validators accept only actual
boolean values and require them to be true. A focused probe confirmed integer
`1` is refused; the implementation's recorded probes also cover textual
substitutes. This closes `literal-true-coercion`.

### docstring-correction | low | Census-row documentation now describes the landed relational proof

The corrected `SourceConnectivityCensusRow` docstring describes evidence and
accountability for all dispositions and the additional relational proof required
for a connected row. This closes `stale-connected-proof-docstring`.

### live-authority-correction | low | Explicit enrollment, workflow, and digest authority closes the remaining connected-proof blocker

Corrective commit `fdaa3930ad` makes authority-backed validation mandatory for
every `connected` row. Direct model validation without authority is refused. The
core-owned `SourceConnectivityProofAuthority` protocol asks its caller to verify
live source enrollment, supported entrypoint and command membership, and the
current content digest of every executable artifact. Core imports no application
policy and reads no filesystem, network, wall clock, or process-global state, so
the protocol creates neither a circular dependency nor ambient validation.

A final probe used a review authority that admitted only
`BindingSourceKind.PROFILE`, the exact `cli.modelo` / `modelo.calculate`
workflow, and SHA-256 recomputed from an existing repository test module. The
coherent proof passed. The same authority refused the deferred
`RELATED_PARTY_OPERATION` source, command id `anything`, a nonexistent
test-shaped locator, and a mismatched digest. Validation without authority also
failed. Separate mutation probes confirmed that evidence carrying the wrong
role or a different connection remains invalid. Role-specific evidence identity,
shared candidate/source-object/resolver/revision identity, strict true booleans,
and digest equality therefore compose into one fail-closed admission contract.
This closes `enrollment-evidence-remains-asserted` and the remaining portion of
`disconnected-attestations`; S04 is unblocked.

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
- For `enrollment-evidence-remains-asserted`, ensure the production census
  builder or its mandatory ratchet gate derives resolver ownership from the live
  enrolled source-disposition authority and verifies each executable evidence
  identity against a real, allowlisted test or generated proof manifest. A
  caller-authored path-shaped string must not manufacture enrollment.
- Bind `entrypoint_id` and `command_id` to the supported operator command
  catalogue, and bind each evidence id to the exact resolver, persistence, or
  operator proof it establishes rather than accepting one generic test-shaped
  locator for every proof family.
- Retain the corrected shared-identity validators, strict booleans, executable
  locator exclusions, and updated documentation.
- S04 remains blocked until the remaining HIGH finding is closed or the same
  commit establishes a mandatory, non-bypassable live-authority validator that
  makes invented/deferred proof records impossible at census admission.
- `live-authority-correction` satisfies that condition. Proceed to S04 while
  preserving authority-backed construction as the only admission path for
  connected census rows. The later census builder and ratchet must implement the
  protocol from canonical live enrollment, command-catalogue, and repository
  digest authorities rather than caller assertions.
