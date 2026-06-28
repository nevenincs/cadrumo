---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-06-08'
related:
  - '[[2026-06-08-registry-localization-backend-plan]]'
---

# `registry-localization-backend` `P07.S17` execution record

Write integration tests asserting reference validation failures on invalid citations under `src/aeat/domain/calculations/registry/tests/`.

## Action

Created and integrated validation tests inside `test_catalogue_verification.py`:
- `test_verify_source_file_checks_manual_structure`
- `test_verify_legal_reference_checks_manual_section_json`
These tests assert that validation fails with the expected error when structures or section files are corrupt/missing.

## Verification

Tests run sequentially and pass successfully.
