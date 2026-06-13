---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W09.P041.S0242'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]"
---

# `cli-workflow-redesign` `W09.P041.S0242`

Closed plan rows:

- `W09.P041.S0242`

## Description

Created `src/aeat/application/user_profile/__init__.py` as the application-layer command and result contract surface for the centralised schema-driven profile backend. The package exposes strict, frozen, ``extra="forbid"`` Pydantic records — no business logic — covering every lifecycle, validation, preflight, snapshot, and portable-bundle interaction named in the W09.P041.S0241 service ownership map.

Lifecycle commands: `RegisterProfileCommand`, `EditProfileFieldCommand`, `EditProfileSectionCommand`, `RemoveProfileCommand`, `DuplicateProfileCommand`. Lifecycle results: `ProfileLifecycleResult`, `ProfileListing`, `ProfileListResult`.

Validation surface: `ProfileValidationSeverity` (StrEnum: error, warning, info), `ProfileValidationIssue`, `ProfileValidationReport`.

Preflight surface: `ProfilePreflightRequirement`, `ProfilePreflightReport` (with `ready: bool` flag and the `(modelo, revision_id, filing_year, period)` tuple from the audit recommendation).

Filing snapshot surface: `ProfileSnapshotRequest`, `ProfileSnapshot` (carries `canonical_hash` as a 64-character lowercase hex SHA-256), `ProfileStaleCheckReport` (compares `stored_hash` vs `current_hash` with a boolean `stale` flag).

Portable bundles: `ProfileExportBundle`, `ProfileImportResult`. The export bundle is documented as "Not retained by the backend" per the ADR's "portable exports are user-directed output only" constraint.

The application contracts reuse the existing domain records `UserProfileRecord`, `UserProfileFact`, `UserProfileStatus`, and `ProfileFactValue` from `aeat.domain.user_profile`, so the application layer and the domain layer share one schema authority.

## Modified Paths

- `src/aeat/application/user_profile/__init__.py` (created)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

Smoke import of the new module passes:

```
python -c "from aeat.application.user_profile import RegisterProfileCommand, ProfileSnapshot, ProfileStaleCheckReport, ProfilePreflightReport, ProfileExportBundle"
```

Contract tests for these records land in W09.P044 (`S0259` — Add service contract tests). The records carry no logic; their strict frozen pydantic shape is the contract.
