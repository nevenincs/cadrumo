---
tags:
  - '#exec'
  - '#registry-localization-backend'
date: '2026-06-08'
modified: '2026-07-17'
body_hash: 'sha256:1b7a219736cb4ddef451b32783545e7f2b5c9987f6608dcdf7c3686e0950eb62'
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
