---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:f2dad8c7b28fde4883716e43e3e1fc8e2ed1375ae39781a226fcdaece0f28d1b'
step_id: 'S32'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# Resolve only absent exact-anchor wire facts through the validated render profile, refuse official-content conflicts and uncovered or hash-drifting profiles, keep variable envelopes outside fixed-width output, and add the canonical profile digest and schema version to provenance

## Scope

- `dev/registry/`

## Description

- Thread the exact SHA-bound render profile and resolved source evidence through rendering, validation, publication, recovery, check mode, and provenance verification.
- Delete the ambiguous `ExportRenderProfile` surface; retain transport facts in `ExportTreeTransportProfile` and absent-wire authority in `RenderProfile`.
- Resolve only blank numeric official cells through exact validated anchors, retain present official facts, and refuse uncovered, conflicting, inapplicable, or hash-drifting authority.
- Attest the canonical order-independent profile digest and profile schema in provenance schema version 2, then verify them through every repository boundary.
- Re-verify interrupted-recovery candidates and targets against the retry's current authorities before any promotion or destructive finalization.
- Reject typed variable envelopes before render-profile validation or target creation; use the canonical core link guard for source evidence.

## Outcome

The generator has one hard-cut authority path: official coordinates and present wire facts remain source-owned, semantic meaning remains map-owned, and a reviewed hash-pinned render profile supplies only absent exact-anchor numeric wire facts. `DP200000` and every other typed variable envelope refuse fixed-width generation without truncation. The emitted manifest records the render-profile schema and complete canonical digest, and verification rejects profile, evidence, source, map, layout, file, or schema drift.

The current recovery path verifies the canonical manifest with the exact joined design, map, rendered derivations, profile, and evidence before accepting a journaled candidate or target. No legacy profile alias, fallback, defaults, or duplicate digest/inference owner remains.

Focused source, profile, provenance, publication, recovery, check, and envelope verification passed 106 tests. The full `dev/registry` unit lane passed 190 tests. Scoped Ruff, strict BasedPyright, and `git diff --check` were clean. Independent Luna review passed with no open critical, high, medium, or low findings.

## Notes

An initial default pytest command selected zero tests and was discarded. The final test commands override the repository's default selector and prove nonzero collection.

The independent review found and this Step resolved three issues: current-authority verification during interrupted recovery, variable-envelope refusal ordering, and source-link consolidation onto canonical `is_link_like`. The review and execution records were refreshed through the owning vault CLI before plan closure.
