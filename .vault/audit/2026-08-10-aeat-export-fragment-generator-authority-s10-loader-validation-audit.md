---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:c5e16ac0d4e04e9600111efedf850f68fa97c74e6cc9f428861b5973e9a62b0f'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S10 loader validation review`

## Scope

Review the development-only S10 gate that validates one freshly generated, un-published export revision before S11 can publish it. Confirm real directory loading, validated authority selection, current provenance attestation, exact rendered semantics, and removal of legacy admission paths.

## Findings

No critical, high, or medium findings. The independent reviewer confirmed that the boundary loads the isolated directory through `load_modelo_directory`, then selects the same modelo and revision through `ValidatedRegistryAuthority.snapshot` using the declared filing context.

The review confirmed that target-only modelo and revision membership, exact generated output membership, provenance equality, direct-revision refusal, and no-legacy structural checks fail closed. The tests construct only a fresh generated export tree; they never copy an existing export fragment tree.

## Recommendations

- Keep S11 dependent on this validator and pass it a newly constructed isolated candidate registry root.
- Retain the structural no-legacy test whenever the loader or generator boundary changes.
