---
tags:
  - '#exec'
  - '#bucket-custody-completeness'
date: '2026-06-30'
modified: '2026-07-17'
step_id: 'S16'
related:
  - "[[2026-06-30-bucket-custody-completeness-plan]]"
---

# Add a cleartext structured-only test asserting no FINANCIAL bytes are carried and the not-a-full-backup notice is emitted

## Scope

- `src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py`

## Description

- Add cleartext structured-only CLI export coverage.
- Assert the bundle carries no generic secure-object bytes.
- Assert the operator warning states the cleartext bundle is not a full backup.
- Assert the manifest records populated exclusions and row counts.

## Outcome

- Complete. The CLI test now proves the structured transport is deliberately partial rather than silently empty.
- Verified by `pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py`.

## Notes

- The filing fixture was updated to match the current `derive_filing_record_id` contract, where `filed_at` is not part of the identity.
