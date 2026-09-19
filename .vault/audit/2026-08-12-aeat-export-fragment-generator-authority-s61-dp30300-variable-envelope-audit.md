---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:e1dc197cb44d9ff0c56b4d7eb258e73e5911482ebcee7d939ddfee3929b2d0b5'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S61 DP30300 Variable Envelope Audit`

## Scope

Audited the typed DP30300 composition authority across the five hash-pinned Modelo 303 design epochs: thirteen exact prefix anchors, explicit product/software identity, ordered fixed-width body records, relative closer, measured total, source/revision/period binding, provenance, and pre-mutation refusal.

## Findings

### generator-handoff | high | initial byte composer was not invoked by generation

The first candidate admitted DP30300 but left its byte composer reachable only from direct tests. The generator was corrected to invoke the canonical fixed-width record codec, compose prefix, actual ordered body bytes, and closer in memory before target preparation, derive total from `len(payload)`, and bind ordered body digests, payload digest, and total in provenance. Sensitive filing bytes are never persisted in generated registry artifacts.

### source-period-binding | high | initial input period was not tied to the selected snapshot

The first remediation allowed a 2026 source design to emit a 2023/4T prefix and closer. The join now retains selected revision and typed filing period, requires the parser source to belong to that revision, and generation refuses revision or period mismatch before target creation. The five valid epoch/period pairs pass and the cross-year mutation leaves no target.

### dp30300-authority | low | final implementation satisfies the accepted envelope boundary

The final immutable candidate `d812c920b0f57a072f4a28c03d8ae583bc5a235e` with tree `ef0bdf0e618154c5fc6b48ba4c5b77dde50db39d` was formally approved with zero unresolved critical, high, or medium findings. The reviewer ran 183 focused tests; Ruff, `ty`, BasedPyright, and diff checks were clean.

## Recommendations

Keep DP30300 composition in memory, source/revision/period-bound, and derived from the one fixed-width codec. Never persist raw filing payloads in generated trees, replace product identity with a filing producer or literal, or admit DP200/DP220 through this Modelo 303 contract.
