---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:b1b3c81dd0d22a00121fe0807848046996ec09eb1ad2512f26df65661090cad5'
step_id: 'S07'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh make the profile repository and aggregate project only committed UUID capsules through sole lifecycle writers

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Replace retired profile lifecycle authority with committed UUID capsules and the authenticated current-record repository.
- Bind revision-one record staging, encrypted secure-object persistence, append-only event history, and later fact mutations to one transaction and lineage chain.
- Restrict discovery and label projection to anchored committed capsules; remove retired writers, removal-state semantics, and manifest-backed fact authority.
- Authenticate restore contents before publication and refuse missing, duplicate, malformed, or provenance-mismatched current records.
- Migrate projection, capability, preflight, presence, overview, wizard, CLI, TUI, and custody tests to the strict current record contract.

## Outcome

The only fact authority is the encrypted, session-bound `UserProfileRecord` in a committed capsule. Profile labels remain non-authoritative projections. Creation, restore, setup completion, and fact changes validate UUID, envelope, DEK epoch, revision, predecessor digest, and content digest before publishing a current record.

Focused migration coverage passed 102 tests; full custody adapter and record transaction coverage passed 75 tests. The full `application/user_profile` suite passed 237 tests; its only two failures are the pre-existing Modelo 202 filing-grade legal-review refusal, whose five cited legal references remain `agent_reviewed` rather than `operator_reviewed`. Scoped Ruff, Ty, and basedpyright checks passed with no findings. Independent Sol review passed with no attributable critical or high finding.

## Notes

No data was deleted and no compatibility bridge was retained. The current-suite Modelo 202 legal-review failures are outside this step's custody and lifecycle authority and were left unchanged.
