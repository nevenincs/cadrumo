---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:a3eae640fe542970b5d8c4225e21f0b6bee0147649a8208c6042b0599bb97664'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---



# `source-casilla-integration` audit: `source-casilla-integration audit: s174 row source identity replay review`

## Scope


Independent review of row-source identity propagation, exact replay joins, content-address preservation, review redaction, and unchanged M720 behavior.

## Findings


### s174-row-source-identity-replay-review | high | resolved coordinate-only identity attachment

The initial join could attach an authentic persisted identity to a substituted value at the same coordinate and could silently replace a conflicting identity already carried by the draft. Replay now requires canonical value equality and refuses conflicting attached identities with value-free errors.

### s174-row-source-identity-replay-review | medium | resolved test-only review projection

The first fingerprint-only projector had no production consumer. The canonical work-review entrypoint now projects deterministic safe provenance from the persisted calculation revision, and a real repository-backed test proves the review contains the fingerprint but not the opaque identity.

### s174-row-source-identity-replay-review | pass | final replay and review contract is coherent

Source-resolution identities persist into calculation revisions, export and workflow draft assembly attach them to exact row values, draft content addressing includes them, M720 unidentified rows remain valid, and public review state exposes only safe fingerprints. Final independent review reported zero findings.

## Recommendations


Proceed with S175 without exposing raw identities through CLI surfaces. S176 may construct inventory cohorts only through the canonical coordinate and replay contracts established here.
