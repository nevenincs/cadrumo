---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:0c8dae5ff5b0c7c9236d6aee4acc071151e0e1322a566c40063ad89fcf038e97'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-research]]"
---

# `registry-authority-artifact-boundary` adr: immutable runtime publication | (**status:** `accepted`)

## Problem Statement

Establish one publish boundary so production consumes only a validated immutable authority and authoring remains a development responsibility. The boundary must also break the identifier bootstrap cycle and eliminate parallel operative-value loaders without creating a second closed registry in Python. See `2026-09-10-registry-authority-artifact-boundary-research`.

## Considerations

- Published authority must be complete enough for every shipped calculation and filing workflow; `2026-09-10-registry-authority-artifact-boundary-research`.
- Missing, malformed, or tampered publication must not trigger source compilation or repair; `2026-09-10-registry-authority-artifact-boundary-research`.
- Identifier syntax is stable code-level structure, while membership and scope are authority facts; `2026-09-10-registry-authority-artifact-boundary-research`.
- Operative values require typed projections; embedding source bytes for runtime reparsing would preserve a parallel management lane; `2026-09-10-registry-authority-artifact-boundary-research`.
- Development publication must retain corpus conformance and transactional candidate handling; `2026-09-10-registry-authority-artifact-boundary-research`.

## Considered options

- Retain runtime source compilation: rejected because it couples production to mutable authoring inputs.
- Ship the compiler cache unchanged: rejected because source-root identity and recompilation semantics preserve the boundary leak.
- Publish a versioned, digest-checked authority artifact and deserialize it at runtime: accepted.
- Fall back to raw sources when publication fails: rejected because an invalid release would silently become a development runtime.
- Keep closed identifiers generated from raw facts: rejected because schema imports would still consume compiler inputs.
- Hardcode closed identifier enums: rejected because Python would become a second authority.
- Generate closed enums from the artifact: rejected because compilation and schema import would depend on the generated output.
- Use open syntax-validated identifier values with authority-backed membership: accepted.
- Reparse embedded source documents for operative values: rejected because it retains consumer-specific schemas and caches.
- Sign the artifact with a repository-held release key: rejected because same-repository signing and verification adds custody without a distinct trust boundary.

## Constraints

The artifact format has an explicit schema version and integrity digest and carries every resolved datum required by normal runtime workflows. It is a generated, tracked build output, not a signed document. Identifier constructors perform no registry I/O and validate lexical form only. Membership, revision scope, and relationships require a canonical authority view. Existing developer conformance and source evidence remain development dependencies, not package runtime dependencies.

## Implementation

Development code validates a candidate source tree, materializes authored revision deltas into canonical typed definitions, serializes the complete authority into a versioned artifact, records its digest and candidate identity, and publishes atomically. Period selectors remain canonical data; runtime does not implement the authoring delta language. The artifact may omit only schema-declared defaults that the typed decoder restores exactly.

Replace fact-derived closed identifier enums with open string value types that preserve construction, equality, hashing, serialization, value access, and type distinction while validating only stable syntax. Valid-member enumeration, membership, revision scope, and relationships are authority-backed operations.

Runtime code constructs `bundled_authority()` only from the artifact. Regulated IVA, territory, deadline, authorization, and other operative tables are compiled into typed authority catalogues and consumed through one provider/cache identity. Runtime consumers do not parse authoring TOML or embedded source documents. A corrupt or unavailable artifact fails before filing or calculation output.

The package excludes registry authoring trees, source-evidence parsing, record-design extraction and repairs, compiler caches, conformance, and publishing tooling.

## Rationale

Syntax is a stable property of representation; membership and scope are mutable authority facts. Separating them removes the bootstrap cycle without duplicating a closed universe. Typed publication prevents independent consumers from acquiring different physical inputs or cache lifecycles. The artifact boundary therefore supplies deterministic installed behavior while preserving the development compiler and validation workflow described by `2026-09-10-registry-authority-artifact-boundary-research`.

## Consequences

Production becomes smaller, deterministic, and unable to self-heal an invalid artifact. Adding a well-formed identifier no longer requires a Python enum edit, but callers that treated construction as an existence check must use an authority-backed validator. Enum iteration and exhaustiveness become authority queries. Publication owns serialization compatibility and typed catalogue completeness. Installed-package tests must prove artifact-only execution, corruption refusal, centralized temporal admission, and absence of raw operative-value loaders.
