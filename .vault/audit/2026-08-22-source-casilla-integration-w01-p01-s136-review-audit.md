---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:5c7d63e1415c245c40e0e6998698db1482a0e5f2f7cf8c449bf087ee482caa07'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-w01-p01-phase-review-audit]]"
---

# `source-casilla-integration` audit: `W01.P01.S136 encrypted proof contract review`

## Scope

Reviewed commit `c7f82208bc` against the accepted source-casilla integration
ADR, `W01.P01.S136`, the preceding `W01.P01` phase audit, the core dependency
boundary, the application source-mesh provenance projection, and the encrypted
`CalculationRevision` persistence contract. The review specifically checked
that connected admission receives the complete encrypted proof, can name the
exact persisted provenance row and fingerprint, does not infer resolver
ownership from persistence, and remains free of application dependencies and
compatibility paths.

The focused core suite passes 36 tests, the real encrypted source-provenance
round-trip suite passes 3 tests, and Ruff passes the S136 production and test
files. Direct import inspection confirms the owner module depends only on core
siblings and Python or Pydantic libraries. No production or test source was
modified by this review.

## Findings

### persisted-source-identity | high | The proof equates two different production identity shapes

`SourceConnectivityEncryptedRevisionProof._require_strict_revision_proof`
requires `persisted_source_identity == connection.source_object_id`. The real
persisted contract does not store that raw object id: `CalculationSourceRef`
stores `source_ref`, a resolver-authored stable reference. Production resolvers
demonstrably namespace or otherwise shape that reference, including
`foreign_asset:<source_object_id>`, `invoice:<invoice_id>`,
`transaction:<transaction_id>`, and multi-component prorrata references. The
encrypted round-trip fixture likewise persists
`collectible_invoice:inv-0001`, not `inv-0001`.

Consequently a concrete authority cannot both obey the S136 model invariant
and perform the requested exact `CalculationSourceRef.source_ref` lookup for
ordinary live provenance. Stripping a prefix or reconstructing a reference
from `BindingSourceKind` would be an ambiguous compatibility heuristic because
the reference grammar is resolver-owned and is not uniformly the enum token.
The relation must instead represent the persisted reference explicitly, then
the authority must join the loaded row by the law-selected calculation
revision, canonical `binding_source`, exact `source_ref`, and exact
`fingerprint`. This is a blocking identity-contract defect for S134.

### authority-seam-coverage | medium | The fingerprint mutation bites only at the configurable core seam

The new fingerprint-drift test is not tautological with the model validator:
it constructs a changed frozen proof and fails only because
`validate_with_authority` passes that complete proof to
`encrypted_revision_matches`. Removing or bypassing that call would make the
test fail. However, `_ProofAuthority` still decides the expected fingerprint
from a test constant and never loads an encrypted revision. It therefore proves
the core dispatch and refusal behavior, not the live persisted lookup. This is
the same open fake-authority limitation recorded by the phase audit; S135 must
replace it with real encrypted-repository mutation coverage before the phase
can close.

### dependency-and-resolver-boundary | low | The core seam remains dependency-inverted and resolver ownership stays separate

The authority protocol receives the full typed encrypted-revision proof and the
core module imports no application, adapter, persistence, filesystem, or CLI
owner. Encrypted provenance is not asked to prove `resolver_id`, which is
correct because `CalculationSourceRef` deliberately persists source kind,
binding source, source reference, fingerprint, and dependency treatment but no
resolver identifier. Resolver ownership remains independently checked through
`source_is_enrolled` and its role-specific executable evidence. No shim,
fallback, or parallel resolver path was introduced.

## Recommendations

- Add a corrective prerequisite step before S137 and S134. Replace the false
  raw-object equality with an explicit persisted-source-reference relation
  matching real `CalculationSourceRef` semantics. Prove representative
  non-isomorphic identities such as raw `inv-0001` versus persisted
  `collectible_invoice:inv-0001`; a fixture where both strings are identical
  would hide this defect.
- In S134, load the exact encrypted calculation revision and require one
  provenance row whose `binding_source`, `source_ref`, and `fingerprint` match
  the asserted proof. Do not infer or normalize the resolver-owned
  `source_ref`, and do not use `source_kind` as a substitute for canonical
  `binding_source`.
- Retain the complete-proof protocol call and the independent resolver and
  operator authority checks. S135 must mutate the actual encrypted provenance
  row for reference and fingerprint drift and demonstrate a red gate without a
  fake, monkeypatch, skip, xfail, or fallback.
- Treat `persisted-source-identity` as HIGH and block S137/S134 until corrected;
  the current contract cannot be implemented faithfully against production
  revision semantics.
