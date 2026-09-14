---
tags:
  - "#adr"
  - "#registry-authority-artifact-boundary"
date: '2026-09-10'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-research]]"
  - "[[2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference]]"
superseded_by: '2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:8dc9bbe54db5ccf6a7f8a7c69fc52c5550b6fb6c5188e57dbf092404af4d6374'
---
# `registry-authority-artifact-boundary` adr: immutable runtime publication | (**status:** `superseded`)

## Problem Statement

Establish one publish boundary so production consumes only a fully validated, deeply immutable authority and authoring remains a development responsibility. The boundary must separate input, build, component, and payload identities; break the identifier bootstrap cycle; and eliminate parallel operative-value loaders without creating a second closed registry in Python. See `2026-09-10-registry-authority-artifact-boundary-research` and `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.

## Considerations

- Published authority must be complete enough for every shipped calculation and filing workflow; `2026-09-10-registry-authority-artifact-boundary-research`.
- Publication is trustworthy only when the exact captured candidate has completed registry-wide conformance and evidence-closure validation before atomic replacement; `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.
- Missing, malformed, stale, or tampered publication must fail closed without source compilation, raw-source fallback, repair, or mixed-generation reads; `2026-09-10-registry-authority-artifact-boundary-research`.
- Portable source-manifest identity, compiler and schema build identity, component dependency identity, and serialized payload digest answer different questions and must remain distinct; `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.
- Runtime snapshots and every reachable semantic value must be deeply immutable so shared typed definitions can be reused without cross-caller mutation; `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.
- Identifier syntax is stable code-level structure, while membership and scope are authority facts; `2026-09-10-registry-authority-artifact-boundary-research`.
- Operative values require typed projections; embedding source bytes for runtime reparsing would preserve a parallel management lane; `2026-09-10-registry-authority-artifact-boundary-research`.
- The logical authority generation is the architectural boundary. Eager monolithic JSON decoding is an implementation choice to measure and optimize before adopting a different storage backend; `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.

## Considered options

- Retain runtime source compilation: rejected because it couples production to mutable authoring inputs.
- Ship the compiler cache unchanged: rejected because source-root identity and recompilation semantics preserve the boundary leak.
- Publish a versioned, digest-checked authority artifact only from a fully validated captured candidate and deserialize it at runtime: accepted.
- Publish retained sections incrementally without transitive dependency receipts and clean-build equivalence: rejected because it can preserve stale semantics while claiming whole-generation currency.
- Use full canonical publication until partial dependency closure is proven: accepted.
- Fall back to raw sources when publication fails: rejected because an invalid release would silently become a development runtime.
- Keep closed identifiers generated from raw facts: rejected because schema imports would still consume compiler inputs.
- Hardcode closed identifier enums: rejected because Python would become a second authority.
- Generate closed enums from the artifact: rejected because compilation and schema import would depend on the generated output.
- Use open syntax-validated identifier values with authority-backed membership: accepted.
- Reparse embedded source documents for operative values: rejected because it retains consumer-specific schemas and caches.
- Replace the current artifact format before correcting and measuring its query path: rejected because storage changes would obscure semantic defects and reconstruction costs.
- Optimize deeply immutable typed snapshots, indexes, evidence lookup, and bounded caches in the existing format before evaluating an indexed container: accepted.
- Sign the artifact with a repository-held release key: rejected because same-repository signing and verification adds custody without a distinct trust boundary.

## Constraints

The artifact format has an explicit schema version and integrity digest and carries every resolved datum required by normal runtime workflows. It is a generated, tracked build output, not a signed document. Publication captures one immutable input generation, performs complete registry and evidence validation against that same capture, validates the encoded candidate, and only then replaces the prior artifact atomically. Grade-specific unsupported states remain explicit.

Source-manifest, build, component-dependency, and payload identities remain separate fields with separate currency semantics. Until component dependency receipts and clean full-build equivalence prove selective publication safe, every publication is a full canonical generation. Runtime never reads authoring sources as a fallback or combines components from different generations.

Identifier constructors perform no registry I/O and validate lexical form only. Membership, revision scope, and relationships require a canonical authority view. Existing developer conformance and source evidence remain development dependencies, not package runtime dependencies. Every published semantic mapping, token, snapshot, and public authority field is deeply immutable; mutable caches stay private, normalized, and bounded.

The current format is optimized and measured against representative workloads before any physical storage pivot. A future indexed container must preserve the same typed authority API, atomic generation contract, validation and refusal behavior, inspectable canonical projection, and provenance semantics, and requires an explicit architecture decision.

## Implementation

Development code captures one source generation, resolves authored revision deltas into canonical typed definitions, performs complete registry-wide and evidence-closure validation, serializes and admits the candidate, records distinct source-manifest, compiler/schema build, component-dependency, and payload identities, and publishes the complete generation atomically. Structural compilation remains available only through a type that cannot be published as validated authority. Period selectors remain canonical data; runtime does not implement the authoring delta language. The artifact may omit only schema-declared defaults that the typed decoder restores exactly.

Replace fact-derived closed identifier enums with open string value types that preserve construction, equality, hashing, serialization, value access, and type distinction while validating only stable syntax. Valid-member enumeration, membership, revision scope, and relationships are authority-backed operations.

Runtime code constructs `bundled_authority()` only from the artifact. Regulated IVA, territory, deadline, authorization, and other operative tables are compiled into typed authority catalogues and consumed through one provider and generation identity. Runtime queries reuse deeply immutable typed definitions and revision-level indexes, perform only request-dependent temporal and grade admission, index evidence by identity, and use normalized bounded caches. A corrupt, incomplete, stale, or unavailable artifact fails before filing or calculation output without consulting authoring sources.

The package excludes registry authoring trees, source-evidence parsing, record-design extraction and repairs, compiler caches, conformance, and publishing tooling. Performance work first removes full-graph copies and repeated invariant derivation from the current format, then records fresh-process latency, memory, first-snapshot, warm-query, and whole-corpus costs. Only unmet agreed budgets can trigger a separately recorded storage-format decision.

## Rationale

Syntax is a stable property of representation; membership and scope are mutable authority facts. Separating them removes the bootstrap cycle without duplicating a closed universe. Complete validation of one captured generation makes publication an honest authority transition, while separate identities prevent a section digest from impersonating whole-corpus currency. Deep immutability permits safe structural sharing and removes copying from routine reads. Full canonical publication is the only justified mode until selective dependency closure is executable and compared with a clean build. The logical generation contract can survive later storage optimization, so correcting and measuring the existing format preserves semantic confidence while keeping a future indexed backend available. See `2026-09-14-registry-authority-artifact-boundary-post-delta-architecture-review-reference`.

## Consequences

Production becomes deterministic, unable to self-heal an invalid artifact, and isolated from authoring data. Publication becomes more expensive because full validation, evidence closure, encoded admission, and stable input capture precede replacement. Adding a well-formed identifier no longer requires a Python enum edit, but callers that treated construction as an existence check must use an authority-backed validator. Enum iteration and exhaustiveness become authority queries.

Partial publication remains disabled until dependency receipts, compiler identity, concurrent-input protection, and clean-build equivalence prove retained components current. Runtime models and snapshots must reject mutation through every reachable field, which may require replacing generic deep copies with shared immutable definitions. Installed-package tests must prove fully validated publication refusal, artifact-only execution, corruption and incompleteness refusal, coherent identity, centralized temporal admission, representative Modelo workflows, and absence of raw operative-value loaders. A storage pivot remains possible only after current-format optimization and workload measurement establish that it is necessary.

Retain the v5 canonical artifact after current-format optimization. The reproducible measurements and their limitations are recorded in `2026-09-14-registry-authority-artifact-boundary-remediation-result-reference`. No product startup or memory budget has been agreed, so retention does not certify an application SLO. Publication remains full-only and canonical; selective components and equivalence are not enabled or claimed. Indexed storage remains conditional on a later concrete SLO and separate architecture decision.
