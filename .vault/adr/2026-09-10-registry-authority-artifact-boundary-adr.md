---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:97b0b7467c2d0d997f80c38409f531999660daf5a49c84a51acc3927433a1a76'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-research]]"
---

# `registry-authority-artifact-boundary` adr: immutable runtime publication | (**status:** `accepted`)

## Problem Statement

The shipped authority is presently built from registry authoring inputs at runtime. Establish one publish boundary so production consumes only a validated immutable authority and authoring remains a development responsibility. See `2026-09-10-registry-authority-artifact-boundary-research`.

## Considerations

- Published authority must be complete enough for every shipped calculation and filing workflow; `2026-09-10-registry-authority-artifact-boundary-research`.
- Missing, malformed, or tampered publication must not trigger source compilation or a repair path; `2026-09-10-registry-authority-artifact-boundary-research`.
- Development publication must retain corpus conformance and transactional candidate handling; `2026-09-10-registry-authority-artifact-boundary-research`.

## Considered options

- Retain runtime source compilation: rejected because it leaves production coupled to mutable authoring inputs.
- Ship the existing compiler cache unchanged: rejected because its source-root identity and recompilation semantics preserve the same boundary leak.
- Publish a versioned, digest-checked authority artifact and deserialize it at runtime: accepted.
- Publish an artifact but fall back to raw sources when it fails: rejected because an invalid release would silently become a development runtime.
- Sign the artifact with a release key verified against a compiled-in public key: rejected because the same repository would sign and verify it, making it self-signed. It adds a release-secret dependency and blocks generation on key custody, without protecting against anything the digest and the staleness gate do not already catch.

## Constraints

The artifact format must have an explicit schema version and integrity digest. It must carry every resolved datum required by normal runtime workflows. The artifact is a generated, tracked build output, not a signed document: it carries no signature, certificate, key, or trust anchor, and publication needs no release secret. The digest detects corruption, and the recorded candidate identity detects staleness against the current source tree. A signature produced and verified by the same repository would be self-signing, and so would add ceremony and a secret-custody obligation without adding trust. Existing developer conformance and source evidence remain stable development dependencies, but are not package runtime dependencies.

## Implementation

Development code validates a candidate source tree, serializes its complete authority into a versioned artifact, records an integrity digest and the identity of the candidate it was compiled from, and publishes the artifact atomically as a tracked file. A development gate compiles the current candidate and fails when the tracked artifact's recorded candidate identity differs, so a stale artifact is visible before release rather than at runtime. Runtime code reads only that artifact to construct `bundled_authority()`. The package excludes registry authoring trees, source-evidence parsing, record-design extraction and repairs, compiler caches, conformance, and publishing tooling. A corrupt or unavailable artifact is a deterministic runtime error before any filing or calculation output is produced.

## Rationale

This boundary turns validation into an explicit release operation and prevents a shipped command from changing authority according to local corpus contents. It preserves the existing developer validation capability while giving installed users deterministic, fail-closed authority behavior. The research establishes both the existing compiler coupling and the viable snapshot surface; `2026-09-10-registry-authority-artifact-boundary-research`.

## Consequences

Release publishing gains a serialisation compatibility obligation and must be exercised with real installed-package tests. Production becomes smaller and cannot self-heal an invalid artifact; release tooling must therefore make publication failure conspicuous. Source mutation after publication has no runtime effect until a successful republish, which is the intended authority contract.
