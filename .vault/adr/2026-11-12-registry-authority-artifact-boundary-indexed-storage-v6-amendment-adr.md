---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:9e75c802bc62e0d4566c4c0864950f134b87260626809030b9f0263037684cce'
related:
  - "[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr]]"
  - "[[2026-11-12-registry-authority-artifact-boundary-snapshot-proof-dateless-amendment-adr]]"
  - '[[2026-09-14-registry-authority-artifact-boundary-indexed-storage-research]]'
  - '[[2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-reference]]'
---

# `registry-authority-artifact-boundary` adr: `authority database format v6 admitting v5 without proofs (amendment proposal)` | (**status:** `proposed`)

This record proposes an amendment to the accepted `2026-09-14-registry-authority-artifact-boundary-indexed-storage-adr`, whose 2026-10-24 amendment set the store format to `cadrumo-authority-sqlite-v5` and admitted v4 without proofs. The accepted body stays unchanged until this amendment is accepted; on acceptance, that amendment's format sentence is replaced as stated under Implementation and this proposal is retired.

## Problem Statement

The companion proposal `2026-11-12-registry-authority-artifact-boundary-snapshot-proof-dateless-amendment-adr` removes the fact-date window from the snapshot proof contract. The window lives in two columns of the `snapshot_proof_contract` table, so the published database layout changes and needs a new format identity.

## Considerations

- The format identity is checked at admission (`src/cadrumo/domain/calculations/registry/authority_store.py`); a reader expecting the old columns cannot read the new table, and the reverse holds too.
- A v5 database carries the same components and proof rows, but its proofs were established under a run-date window the new reader no longer evaluates.
- The logical generation digest does not change: only the proof tables differ, and they are covered by the physical digest.

## Considered options

- **Keep v5 and leave the window columns unused.** Rejected: a stored field nothing reads is dead layout, and a v5 reader would still apply the window to a new database.
- **Advance to v6 and admit v4 and v5 without proofs.** Rejected: admitting two predecessors extends a compatibility window nobody requested; the accepted decision admits exactly the preceding format.
- **Advance to v6, admit v5 without proofs, refuse v4.** Chosen.

## Constraints

- The store format is `cadrumo-authority-sqlite-v6`. Its `snapshot_proof_contract` table records the validator digest only.
- Runtime admits v6 and the preceding v5. A v5 database is read as a database without proofs, so every request takes full validation until the operator republishes. Anything older, v4 included, is refused rather than read.
- The descriptor format and the logical generation digest are unchanged; the physical digest changes because the proof tables change.

## Implementation

We will advance the format to v6, drop the window columns from the proof table definition, the publisher and the reader, and admit v5 as the proofless predecessor. On acceptance, the accepted record's 2026-10-24 amendment sentence ("store format `cadrumo-authority-sqlite-v5` ... v4 still admitted without proofs") is annotated with: amended 2026-11-12, store format `cadrumo-authority-sqlite-v6`, v5 admitted without proofs, v4 refused. The root authority is republished from the merged tree after the change lands.

## Rationale

The layout change is real, so the format identity must change with it. Admitting exactly the preceding format keeps the accepted one-predecessor policy, and reading it without proofs is always correct because full validation is the floor.

## Consequences

- An installation holding a v5 authority keeps working at full-validation speed until republication; one holding v4 must republish.
- Publication output changes physical digest without a new logical generation.
