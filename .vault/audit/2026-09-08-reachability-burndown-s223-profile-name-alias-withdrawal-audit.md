---
tags:
  - '#audit'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:fda5bf28a90b246701016ff1b8a8a303ca41b7f303f353905444b04b2dbe7c54'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
  - "[[2026-09-04-reachability-burndown-W05-P12-S223]]"
  - "[[2026-08-13-profile-bucket-lifecycle-successor-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
  - "[[2026-09-04-reachability-burndown-reference]]"
---

# `reachability-burndown` audit: `S223 profile name alias withdrawal review`

## Scope

Independent review of W05.P12.S223, covering deletion of the unused `ProfileName` alias and its orphaned validator-only test, retention of the profile schema-version contract and canonical `ProfileLabel`, corrected boundary-fault test commentary, accepted profile lifecycle decisions, cadence guidance, and Step Record evidence.

## Findings

No critical, high, medium, or low findings.

`ProfileName` had no production or development consumer. It duplicated the live profile-label concept while enforcing a conflicting 128-character bound; `ProfileLabel` is the actual type used by profile aggregates, custody transactions and capsule labels, workflow projections, configuration payloads, and operator surfaces, with a 160-character bound and UUID-shape refusal. Keeping both aliases would preserve two names and two incompatible validation rules for one presentation value.

The deleted constants test instantiated a private holder solely to exercise the unused alias. It did not pass a label through registration, custody, persistence, resolution, or CLI behavior and therefore offered no material product protection. Canonical `ProfileLabel` has its own focused validator tests and extensive live behavioral consumers. The accepted bucket-lifecycle decision also distinguishes mutable display label from immutable UUID identity and assigns collision-safe label resolution to the profile repository, consistent with the retained owner.

The constants module continues to own `SUPPORTED_PROFILE_SCHEMA_VERSION` and `ProfileSchemaVersion`; no unrelated profile schema contract was removed. Boundary-fault commentary now accurately names the live `ProfileLabel` contract and its grammar correction is prose-only. No compatibility alias, production/dev metastate, or replacement census was introduced.

The Step Record accurately names the implementation and documentation scope and reports clean name residue, Ruff success, 466 focused passes with four explicitly deselected tests, and exact movement to 307 unused symbols and 10 orphaned tests while the module graph remains 60 unreachable and 2029/2090 reachable. Independent narrow execution of canonical label and boundary-fault tests passed three selected tests with four integration-lane deselections clearly reported.

## Recommendations

Approve W05.P12.S223. Keep `ProfileLabel` as the sole semantic owner of operator-facing profile-label validation; add future label behavior tests at real lifecycle or custody boundaries rather than recreating an unused alias holder.
