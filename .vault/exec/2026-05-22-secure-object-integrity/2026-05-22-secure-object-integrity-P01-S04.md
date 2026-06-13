---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S04'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P01.S04`

Added real-behavior disclosure coverage for unreadable-row attribution output.

- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

Added a regression test that writes a real encrypted wallet observation row whose natural key and payload contain deliberately sensitive markers. The test rotates the master key, builds the attribution report through the real repository path, and verifies that report JSON excludes the private payload content, taxpayer id, period token, expediente marker, and active bucket id while retaining redacted attribution context.

The test uses the existing real SQLite and real `EphemeralMasterKeyProvider` pattern in the repair integrity suite. It adds no fakes, stubs, mocks, monkeypatching, skips, or xfails.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/application/test_repair_integrity.py src/aeat/application/repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`

The focused test run passed 35 tests.
