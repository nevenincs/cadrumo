---
tags:
  - '#adr'
  - '#registry-authority-artifact-boundary'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:7bc419278bb8d9177f465159694628c50963a2c98915581084e2fbed6fd71e2a'
related:
  - "[[2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-adr]]"
  - '[[2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-reference]]'
  - '[[2026-11-12-registry-authority-artifact-boundary-indexed-storage-v6-amendment-adr]]'
---

# `registry-authority-artifact-boundary` adr: `snapshot proofs without a run-date window (amendment proposal)` | (**status:** `deprecated`)

Retired 2026-11-12: accepted by the coordinator on 2026-11-12 and applied into `2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-adr`, which now carries the decision. This record is kept as the proposal's provenance and holds no authority of its own.

This record proposes an amendment to the accepted `2026-10-24-registry-authority-artifact-boundary-snapshot-publication-proof-adr`. The accepted body stays unchanged until the amendment is accepted; on acceptance, the passages named under Implementation are applied to it and this proposal is retired.

## Problem Statement

The accepted decision kept two governed-fact lookups at today's Madrid date (its ruling 3) and made a proof usable only while the run date lies inside the fact-date window derived from them. A proof, and the snapshot cache keyed by the validation date, therefore held or lapsed with the day the program ran. The coordinator's 2026-11-12 rulings (12:52: no registry lookup may substitute the run date; 14:50: this unit) require results that do not depend on the run day. Ruling 3 named a change to those lookups a separate decision; this is that decision.

## Considerations

- A full publication sweep over the published authority recorded exactly one governed-fact query dated at the run date: the legal-reference schema vocabulary, read without a date by `src/cadrumo/domain/calculations/registry/setup_profile_bindings.py:99`. The window was (2022-01-01, open).
- Dateless registry reads already resolve across the support envelope (`StringMappingFact.resolve_support_envelope_entries`, `src/cadrumo/domain/calculations/registry/facts/string_mapping.py`); the setup and legal-reference declarations carry no date of their own.
- After that read became an envelope read, the sweep recorded zero run-date queries over 3421 proofs, and a probe counting every `today_madrid()` call by module found zero calls in the sweep and in 6688 dated snapshot builds of the proven cells.
- The registry clock guard (`src/cadrumo/domain/calculations/registry/tests/test_registry_reads_no_clock.py`) is shrink-only, so a new clock read in the registry package fails the suite.

## Considered options

- **Keep the window, with an always-open bound.** Rejected: it retains a trust condition and a run-date read that no longer protect anything, and every request still reads the clock.
- **Move the lookups to the filing coordinate.** Rejected: the declarations are vocabularies with no filing date of their own, and a dated read would make one snapshot depend on a second coordinate.
- **Read the declarations across the support envelope and drop the window.** Chosen.

## Constraints

- Ruling 3 of the accepted decision ("the two wall-clock fact lookups stay at today's Madrid date") is superseded on 2026-11-12 by the coordinator's rulings of that date. The other rulings stand unchanged.
- No snapshot cross-check reads the run date. A governed-fact read without a date resolves across every edition inside the supported filing years, never at the run date.
- A proof is used when the database was admitted by physical digest, the request is in the proven set and selects the recorded revision, and the runtime's validator digest equals the recorded one. There is no date condition. Otherwise the same function runs every check (ruling 2).
- The proof contract records the validator closure and its digest only. The pinned snapshot cache is keyed by generation and the full request coordinate, without a validation date.
- The registry clock guard stays shrink-only; adding a clock read to the validator closure is a defect, not a reason to restore the window.

## Implementation

We will read the setup and legal-reference declarations across the support envelope, remove the run-date recorder and the window from publication and from the proof contract, remove the date condition from proof use and the validation date from the snapshot cache key, and record the format change in the companion amendment `2026-11-12-registry-authority-artifact-boundary-indexed-storage-v6-amendment-adr`. On acceptance, the accepted record's ruling 3 is annotated as superseded on 2026-11-12, and its Constraints bullets on proof use, the fact-date window and the v5 store format are replaced with the Constraints above and the companion amendment's format statement.

## Rationale

The only run-date query was a dateless vocabulary read; making it an envelope read removes the dependency at its source, so the window protects nothing and its run-date read is the remaining day dependency. Dropping both keeps one canonical validator route and makes a proof's validity a function of generation content and validator code alone.

## Consequences

- Proofs and shared snapshots hold on every run day; results no longer change with the clock.
- The proof table layout changes, so the store format advances (companion amendment); a v5 database is read without proofs until republished.
- If a future check needs a dated governed fact, it must take the date from the request coordinate; reintroducing a run-date read would need a new decision.
