---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:8c19ef9cac61e66aee8219526446c540fd22e9e579dfa986b719e9536f3196ce'
related: []
---

# `registry-authority-artifact-boundary` audit: `artifact contract`

## Scope

The initial W01.P01.S01 artifact reader, writer, and behavioral tests were audited against the accepted immutable-publication decision before runtime adoption.

## Findings

### artifact-contract | critical | Self-recorded digest does not authenticate executable payload

`authority_artifact.py` stores a SHA-256 digest beside a pickle payload and then deserializes the payload. A modifier can replace both bytes and digest, so the check does not establish publisher authenticity and `pickle.loads` can execute altered content before type validation. The current flip-one-byte test establishes accidental-corruption refusal only.

### artifact-contract | high | Frozen wrapper does not make the authority graph immutable

`AuthorityArtifact` is frozen, but its nested catalogue and modelo structures remain mutable. A caller can alter a consumed graph and thereby change a cached runtime authority after it has passed publication checks.

### artifact-contract | medium | Failure gates do not cover the stated contract

The tests cover round trip, absent file, and accidental byte corruption, but omit malformed frames, unsupported versions, invalid shape, and a deliberately recomputed replacement frame. The test suite must exercise each refusal through artifact inputs rather than implementation inspection.

## Recommendations

- Replace executable deserialization with a non-executable, versioned payload schema and verify its digest before decoding.
- Reconstruct or represent consumed authority with immutable nested collections, then prove a consumer cannot mutate an authority that affects a later read.
- Add artifact-input scenarios for every documented failure class, including a recomputed replacement frame.

### artifact-contract | medium | Trusted-key and typed-payload refusal still need direct proof

The corrected reader receives a trusted verification key and reconstructs typed objects after signature verification, but the suite has not yet supplied a complete alternate authority signed by another key or a correctly signed frame whose typed payload is invalid. Both are release-boundary behaviors that should be exercised before runtime adoption.

- Add artifact-input tests for alternate-key refusal and authenticated invalid-payload refusal, then retain the cache-ownership requirement for W02.
