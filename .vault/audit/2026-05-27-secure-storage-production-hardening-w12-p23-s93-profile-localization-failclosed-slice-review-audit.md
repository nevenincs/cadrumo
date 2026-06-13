---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w12-p23-s93-profile-localization-failclosed-slice-exec]]'
---



# `secure-storage-production-hardening` Code Review

S93-PROFILE-LOCALIZATION-001 | HIGH | Duplicate tax-id scan swallowed unreadable profile records

Initial review found `_refuse_duplicate_tax_id` catching broad exceptions and continuing through unreadable profile records. In production that could allow creation of a duplicate tax id when an existing encrypted profile record was torn, schema-drifted, or otherwise unreadable. Resolution: the scan now logs the unreadable record at debug level with exception details and raises `UserProfileValidationError` through a localized message key, blocking the create until repair.

S93-PROFILE-LOCALIZATION-002 | LOW | Fail-closed docstring lagged implementation

Re-review found the implementation fixed but the helper docstring still described skipping torn profiles. Resolution: the docstring now states that unreadable profile buckets block creation and should be diagnosed or repaired.

S93-PROFILE-LOCALIZATION-003 | INFO | Final code review found no remaining issues

The `vaultspec-code-reviewer` re-reviewed the fail-closed duplicate scan after the docstring repair and found no remaining findings.

S93-PROFILE-LOCALIZATION-004 | INFO | Intersecting stored-profile drift exception lacked registry entry

Focused tests exposed an intersecting profile-domain change where `StoredProfileDriftError` was exported but missing a central `ErrorCode` registry entry. Resolution: the typed drift exception is now registered as an integrity error with the existing stored-data validation message key and `aeat config repair` suggestion, and the roundtrip test asserts that typed boundary while preserving the original Pydantic validation error.

S93-PROFILE-LOCALIZATION-005 | INFO | Non-blocking plan and locale debt remain

Locale audit still reports the pre-existing extra `errors.calc.bound_supplied_as_input` key in all locale files. Plan check still reports duplicate W07/W08 canonical identifiers around `P14` and `S56` through `S61`. These are tracked as metadata debt outside this source hardening slice.
