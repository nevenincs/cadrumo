---
tags:
  - '#exec'
  - '#user-profile-lazy-import'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - "[[2026-06-03-user-profile-lazy-import-plan]]"
---

# Relocate the Pydantic command/result classes into `_commands.py`

## Scope

- `src/aeat/application/user_profile/_commands.py` (new)

## Description

- Create the sibling private module carrying the 17 Pydantic command
  and result classes previously declared at the boundary's body:
  `RegisterProfileCommand`, `EditProfileFieldCommand`,
  `EditProfileSectionCommand`, `RemoveProfileCommand`,
  `DuplicateProfileCommand`, `RenameProfileCommand`,
  `ProfileLifecycleResult`, `ProfileListing`, `ProfileListResult`,
  `ProfileValidationIssue`, `ProfileValidationReport`,
  `ProfilePreflightRequirement`, `ProfilePreflightReport`,
  `ProfileSnapshotRequest`, `ProfileSnapshot`,
  `ProfileStaleCheckReport`, `ProfileImportResult`.
- Relocate the `_PROFILE_SNAPSHOT_HASH_KWARGS` constraint kwargs that
  three of the snapshot models share.
- Import the four domain records from `aeat.domain.user_profile` at
  module scope: this is the relocation target where the cost is
  honestly paid at first reference.
- Import `ProfileId`, `_BaseSeverity`, `_PROVENANCE_SOURCE_MANUAL_CLI`,
  and `_STRICT_FROZEN` from the core layer.

## Outcome

- File landed as part of commit `e78b32be0` (atomic S04+S05+S06 per
  the symbol-relocation discipline).
- Class definitions verbatim from the boundary body; no semantic
  change.

## Notes

- `_PROFILE_SNAPSHOT_HASH_KWARGS` retains its bare-str pattern per
  the ADR Rule 7 fingerprint-not-identity carve-out.
