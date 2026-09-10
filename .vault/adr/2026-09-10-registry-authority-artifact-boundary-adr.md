---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:89e85402e83fccb02ad2592c1f80766d8dca327c7f367eecc61b8d73b1bae8b7'
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

## Constraints

The artifact format must have an explicit schema version and integrity digest. It must carry every resolved datum required by normal runtime workflows. Existing developer conformance and source evidence remain stable development dependencies, but are not package runtime dependencies.

## Implementation

Development code validates a candidate source tree, serializes its complete authority into a versioned artifact, records an integrity digest, and publishes the artifact atomically. Runtime code reads only that artifact to construct `bundled_authority()`. The package excludes registry authoring trees, source-evidence parsing, record-design extraction and repairs, compiler caches, conformance, and publishing tooling. A corrupt or unavailable artifact is a deterministic runtime error before any filing or calculation output is produced.

## Rationale

This boundary turns validation into an explicit release operation and prevents a shipped command from changing authority according to local corpus contents. It preserves the existing developer validation capability while giving installed users deterministic, fail-closed authority behavior. The research establishes both the existing compiler coupling and the viable snapshot surface; `2026-09-10-registry-authority-artifact-boundary-research`.

## Consequences

Release publishing gains a serialisation compatibility obligation and must be exercised with real installed-package tests. Production becomes smaller and cannot self-heal an invalid artifact; release tooling must therefore make publication failure conspicuous. Source mutation after publication has no runtime effect until a successful republish, which is the intended authority contract.
