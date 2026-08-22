---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:b37b4552d45cbffb0dd563aa83b2f8430369b9dfe72e3159d78db8ddeab2bf85'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-w01-p01-phase-review-audit]]"
---
# `source-casilla-integration` audit: `W01.P01.S134 concrete connected-proof authority review`

## Scope

Reviewed commit `bfce8e8814` against the accepted source-casilla integration
ADR and plan, the blocking `W01.P01` phase audit at `07c504dbee`, the S136-S139
proof-contract reviews, and the S137 calculation-workflow review. The review
checked the concrete authority's source-disposition and resolver ownership,
workflow provenance and connection identity, public encrypted-revision read
port, exact provenance join, fingerprint requirement, repository-root digest
policy, dependency direction, facade, and absence of ambient catalogues.

Adversarial probes covered deferred and reserved source kinds, invented and
mismatched resolver owners, incomplete catalogues, independently valid workflow
cross-pairs, unknown and ambiguous revision provenance, source-reference and
fingerprint drift, traversal, absolute paths, backslashes, missing files, and a
symlink escaping the injected root. The focused authority, core connectivity,
and workflow suites pass 54 tests; Ruff passes the changed production and test
files; the commit diff passes `git diff --check`. The import-hygiene scanner was
invoked through its module entrypoint but did not finish within the review
window, so this audit makes no tree-wide import-hygiene claim. No production or
test source was modified by this review.

## Findings

### configurable-enrollment-authority | high | The live resolver catalogue can invent enrollment and contradict the canonical disposition registry

`LiveSourceResolverCatalogue` is a freely authored tuple of
`LiveSourceResolverEnrollment` rows. It is not projected from the live resolver
instances, their `owned_sources`, or
`build_binding_source_dispositions`; it requires neither complete
`BindingSourceKind` coverage nor agreement with the canonical disposition for a
member. A direct production-model probe admitted both a member of
`DEFERRED_SOURCE_KINDS` and a member of `RESERVED_SOURCE_KINDS` as `enrolled`
under the invented resolver id `invented-resolver`. A one-row catalogue is also
valid. `source_is_enrolled` consequently returns the authored claim rather than
an independently derived live fact.

The uniqueness and sorting validator prevents duplicate source-kind rows, but
does not make their contents authoritative. S135 could build an honest instance
and prove its own fixture while this production API continues to admit a
fabricated or stale owner. This is the same defect class as the phase audit's
configurable fake, now behind a production class, and it leaves deferred,
reserved, missing, newly enrolled, and resolver-renamed cases outside the
ratchet. This HIGH finding blocks S135.

### workflow-connection-cross-pair | high | Workflow admission proves existence and enrollment separately, not that the exact connection reaches that workflow

`operator_workflow_is_supported` first checks the connection against the
configurable enrollment catalogue and then calls `workflows.supports` with only
`entrypoint_id` and `command_id`. The workflow authority receives no candidate,
source reference, resolver, or calculation revision identity. Any independently
admitted source/resolver row can therefore be cross-paired with any independently
supported calculation command. Moreover,
`SupportedModeloCalculationWorkflowCatalogue` is publicly directly
constructible; the concrete authority does not require evidence that its
instance came from the reviewed reconciliation builder.

The S137 builder correctly projects the live Click reconciliation, but the S134
composition neither preserves that provenance nor proves that a command reached
the exact resolver/source/revision asserted by the connection. The core proof's
`resolver_observed=True` and connection-labelled evidence envelope are claimant
assertions; hashing the named test file does not independently establish their
semantic relation. S135 can supply the required real end-to-end bite, but the
production authority must expose a construction path or typed reviewed
projection that cannot accept an unrelated cross-pair. This HIGH finding also
blocks S135.

### repository-digest-toctou | medium | Root containment is checked before a second path traversal reads the file

`RepositoryRootEvidenceDigestVerifier.digest` resolves the candidate, checks
containment, then separately calls `is_file()` and `read_bytes()` by pathname.
Static traversal, absolute paths, backslashes, missing files, and an existing
symlink to an outside file are correctly refused. However, an intermediate
directory or leaf can be replaced by a symlink or junction after `resolve()` and
before either later pathname operation. The later operation then traverses a
different object than the one whose containment was checked. Repository evidence
is local rather than taxpayer financial data, so this is not rated HIGH, but the
documented symlink-escape refusal is not race-safe under a concurrently writable
tree.

### encrypted-revision-and-boundaries | low | Revision matching and architectural placement are fail-closed and exact

The authority consumes the public
`CalculationRevisionCatalogueRepositoryProtocol`, checks repository existence,
loads through that read port, selects the exact calculation revision id, and
requires exactly one provenance row matching canonical `binding_source` and the
byte-exact persisted `source_ref`; it then compares the persisted fingerprint
exactly. The proof model requires a non-empty fingerprint, so a persisted
`None`, unknown revision, missing row, duplicate identity row, changed reference,
or changed fingerprint is refused. Broad repository read failures fail closed.

The implementation belongs to the application registry package, imports its
domain and sibling-application dependencies through public facades, and reaches
no adapter, entrypoint, private cross-package module, process-global catalogue,
or ambient repository root. The registry facade exports all five intended
owners and the repository root is injected. These parts are sufficient pending
S135's real encrypted repository mutation and operator-path coverage.

## Recommendations

- Replace freely authored resolver enrollment with a deterministic projection
  from the actual calculate-path resolver owners plus the canonical complete
  disposition registry. Require every `BindingSourceKind` exactly once, derive
  `resolver_id` from the resolver that actually declares the matching
  `owned_sources`, and make deferred/reserved members structurally unable to
  carry an owner. Preserve explicit handling for pre-mesh and manual-input tiers
  without inventing a second enrollment authority.
- Make the proof authority consume a workflow projection whose reviewed
  reconciliation provenance is part of its construction contract, and bind
  reachability to the exact connection rather than to the Cartesian product of
  an enrolled source and a supported command. S135's real CLI/replay test must
  fail when candidate, source reference, resolver, revision, entrypoint, or
  command is cross-paired.
- Open and hash repository evidence through a race-resistant contained-file
  primitive, verifying the opened object rather than resolving one pathname and
  later reading another traversal. Add symlink, intermediate-directory swap, and
  leaf-swap bite coverage where the platform supports those attacks.
- Retain the public revision repository port, exact revision lookup, unique
  canonical-binding-source/source-reference join, non-`None` exact fingerprint
  comparison, injected repository root, public-facade imports, and fail-closed
  read behavior.
- Do not start or close S135 while either HIGH finding remains open. After the
  corrective implementation is committed and re-reviewed, S135 should use the
  real encrypted repository and real reconciled operator surface, mutate every
  identity axis, and prove the gate reds without mocks, fakes, stubs,
  monkeypatches, skips, or xfails.
