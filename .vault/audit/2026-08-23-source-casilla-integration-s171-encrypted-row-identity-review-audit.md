---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:864673aee4aa1b4374071b0e8f2a54b0403a807b5e3d9e10bb4b74f48e36adf5'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `s171 encrypted row identity review`

## Scope

Independent review of inward type ownership, revision identity hashing, encrypted schema-v3 persistence, M720 empty-map continuity, malformed-state refusal, and raw-identity confidentiality.

## Findings

### s171-encrypted-row-identity-review | high | resolved namespace version pin lagged the hard cutover

The secure calculation-revision catalogue and its deliberate namespace-address test now agree on schema version 3. Older persisted envelope versions are refused; no compatibility reader was added.

### s171-encrypted-row-identity-review | medium | resolved confidentiality proof omitted physical and error-chain surfaces

The positive encrypted proof scans the database and WAL for opaque identity, fingerprint, provenance-reference, and amount canaries. Corruption proofs inspect formatted traceback, logs, diagnostic context, cause, and context while missing, orphaned, and duplicate identity mutations traverse the real encrypted load boundary.

### s171-encrypted-row-identity-review | pass | final persistence contract is coherent

The source mesh and revision domain reuse one inward value object. Revision hashing and deterministic secure serialization preserve exact coordinates, source kind, identity, and fingerprint; ordinary serialization remains redacted. Final independent review reported zero findings.

## Recommendations

Proceed to S172 and later propagation steps using the canonical domain value object. Keep secure-v3 presence validation at the repository boundary and do not reintroduce an old-envelope reader.
