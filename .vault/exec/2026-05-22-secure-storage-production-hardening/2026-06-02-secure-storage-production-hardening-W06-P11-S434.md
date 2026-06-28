---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S434'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S434`

## Description

- Changed live Google Drive tests to open a real active-profile storage session before building the storage provider.
- Changed enabled provider-build failures from `pytest.skip` to `pytest.fail`.
- Preserved the outer live-test gating behavior so disabled live tests still skip cleanly.

## Outcome

Closed.

Validation:

- Disabled run collected 4 live tests and skipped all 4 because `AEAT_LIVE_TESTS_ENABLED` was not `1`.
- Enabled run with `AEAT_LIVE_TESTS_ENABLED=1`, `AEAT_LIVE_TESTS_GOOGLE=1`, `AEAT_STORAGE_PROVIDER_KIND=google_drive`, and the configured Drive folder id collected 4 tests and failed all 4 on the real missing-token boundary.
- `uv run --no-sync ruff check src/aeat/adapters/outbound/storage/test_google_drive_live.py` passed.

## Notes

The live tests are now non-hypothetical. They no longer pass or skip after live gates are explicitly enabled; they fail until `W06.P11.S430` persists a repo-native OAuth token.
