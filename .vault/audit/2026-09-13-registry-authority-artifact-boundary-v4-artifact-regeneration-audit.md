---
tags:
  - '#audit'
  - '#registry-authority-artifact-boundary'
date: '2026-09-13'
modified: '2026-09-13'
body_schema: 'body-v2'
body_hash: 'sha256:93305a5cf6f061cd6cebd21ad9e6d2df56bd447efcfffde3af437c33ad7181b7'
related:
  - "[[2026-09-10-registry-authority-artifact-boundary-plan]]"
---
# `registry-authority-artifact-boundary` audit: `v4 artifact regeneration and compactness`

## Scope

Reviewed only the W04.P08.S16 addition to `dev/registry/tests/test_authority_artifact_round_trip.py` and the regenerated `src/cadrumo/_data/registry/authority/authority.json`, against the accepted immutable-runtime-publication ADR, its research, the approved plan, and the S12 compact-v4 execution record. The review assessed whether the gate performs a genuinely fresh publication, compares the complete typed authority rather than selected fields, imposes a meaningful independent byte ceiling, and leaves a valid/current tracked artifact despite concurrent authoring history.

The test invokes the canonical publication workflow into a disposable path from the live bundled registry and source root, then reads both that fresh artifact and the separately tracked artifact through the strict v4 decoder. Full `AuthorityArtifact` equality covers every dataclass field: all modelos and revisions, all catalogue projections including facts and typed runtime catalogues, published evidence, and the candidate identity digest. The preceding focused assertions retain useful diagnostics but do not narrow the final equality oracle.

The 64 MiB ceiling is a fixed binary release budget, not a value calculated from the observed artifact and therefore not tautological. The regenerated artifact is 62,622,097 bytes and remains below that ceiling; repository history also shows recent pre-compaction artifacts around 73-75 MB, so the threshold distinguishes the compact representation from the larger wire shape instead of merely restating the current measurement. The file is a canonical v4 frame with exactly `format`, `payload`, and `payload_sha256`; an independent canonical-JSON SHA-256 calculation matched the recorded payload digest. Its recorded candidate identity is `5e2b0b81a901d8b57b97c0dcc50136d38eec8cef047b2e4bda1c1d52d8743892`, matching the reported current candidate, and the payload contains 58 modelos and 152 governed facts.

The tracked-to-fresh typed equality is the relevant concurrency safeguard: any concurrent authored change omitted from the tracked publication, or any mixed/non-atomic generated state, makes the fresh candidate or strict equality differ. The successful isolated gate therefore establishes one coherent final publication rather than relying on earlier intermediate artifact counts.

## Findings

No findings. The S16 gate independently proves complete tracked-versus-fresh typed equality and a non-tautological compactness ceiling, and the regenerated v4 artifact is integrity-valid and current. W04.P08.S16 is closable.

## Recommendations

No corrective action is required for S16.
