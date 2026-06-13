---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S271'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s271-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S271`

Closed `AFR-169` for the user-profile test registration helper.

## Description

- Audited `src/aeat/application/user_profile/_testing.py` as a test helper over canonical profile orchestration.
- Verified it calls real `register_active_profile`, `select_profile`, and `set_active_fields` surfaces instead of introducing fake or monkeypatched storage.
- Verified it uses `nif_check_letter`, `PROVENANCE_SOURCE_MANUAL_CLI`, and `IVARegime.GENERAL` rather than local duplicate constants.
- Ran focused helper usage tests for pointer integration and output-language behavior.
- Closed `S271` through `vaultspec-core vault plan step check` and manually aligned `AFR-169`.

## Outcome

`AFR-169` is closed as `runtime-default`. The helper remains an approved test-facing
fact seeding layer over runtime-backed profile registration, with no alternate storage
backend or duplicated domain vocabulary.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/user_profile/_testing.py src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/tests/test_output_language.py`

## Notes

The broader plan check still reports only the existing `PLAN022` monotonic-order warning.
