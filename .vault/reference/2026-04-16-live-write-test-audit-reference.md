---
tags:
  - "#reference"
  - "#live-write-test-audit"
date: "2026-04-16"
modified: '2026-04-16'
related:
  - "[[2026-04-16-live-write-test-audit-research]]"
  - "[[2026-04-12-submission-engine-adr]]"
---

# `live-write-test-audit` reference: `suite-safety-surfaces`

This reference captures the concrete code and config surfaces that govern whether the test suite can cross into a live AEAT write.

## Canonical safety surfaces

- `pyproject.toml`
  - Declares the only local suite markers: `unit` and `live`.
  - Defaults pytest to `-m 'not live'`, which keeps live tests out of the standard run.
- `env/.env.example`
  - Declares `AEAT_LIVE_TESTS_ENABLED=false` as the canonical live-test opt-in.
  - Declares `AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION=true` for submission safety.
  - Does not declare `AEAT_LIVE_SUBMIT_ENABLED`.
- `tests/conftest.py`
  - Empty beyond a module docstring; no global env mutation or fixture-side submission override exists here.

## Live AEAT-facing test modules

- `src/aeat/adapters/outbound/aeat/export/test_live_submission.py`
  - Builds a real `SubmissionEngine`.
  - Calls `submit_draft()` without `dry_run=False`, so it remains on the dry-run path.
  - The embedded submitter implementation raises if `submit()` is ever reached.
- `src/aeat/application/filing/test_live_complementaria.py`
  - Calls `submit_amendment(..., dry_run=True)` explicitly.
- `src/aeat/application/workflow/test_live.py`
  - Does not construct a submission engine; it asserts adapter absence handling only.
- `src/aeat/application/sync/test_live_sync.py`
  - Exercises a read-only sync smoke path and currently hard-fails after dependency gates instead of driving a submission.

## Submission-boundary drift worth tracking

- `src/aeat/adapters/outbound/aeat/export/test_engine.py`
  - Uses `_RecordingSubmitter`, `_Session`, and related doubles to cover the live gate in unit tests.
- `src/aeat/application/workflow/test_engine.py`
  - Uses `_FakeSubmissionEngine` and sibling doubles to model submission outcomes.
- `src/aeat/entrypoints/cli/submission/_helpers.py`
  - Contains `_Stub*` helper classes to wire an in-process submission engine for CLI flows.

## Reference conclusions

- The enforced live gate is currently a combination of pytest marker exclusion, the `AEAT_LIVE_TESTS_ENABLED` opt-in, and the submission engine’s own `dry_run=False` plus confirmation requirements.
- No tested live path references `AEAT_LIVE_SUBMIT_ENABLED`.
- The suite’s real safety problem is not accidental live submission; it is the continued presence of submission-boundary doubles in unit tests, which weakens confidence in the hardening around `aeat.adapters.outbound.aeat.export`.
