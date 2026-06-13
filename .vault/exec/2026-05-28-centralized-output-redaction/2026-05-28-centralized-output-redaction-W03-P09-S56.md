---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S56'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---


# W03.P09.S56 profile import idempotency redaction expectations

Scope: update profile import idempotency tests so success and refusal output expectations align with central profile-id redaction.

## Description

- Add shared CLI privacy assertion helpers for profile-id placeholder and raw-id absence checks.
- Reuse those helpers in profile export/import roundtrip tests instead of keeping local copies.
- Assert profile import idempotency success output redacts profile identifiers in JSON mode.
- Assert duplicate, label-collision, and mutated-bundle import outputs do not leak raw profile UUIDs.
- Recover the fresh UUID minted by mutated `--label` import and assert it is absent from public output.
- Preserve storage-level identity checks by reading the encrypted profile repository after public output assertions.

## Outcome

S56 is implemented for the current profile import idempotency surface.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_test_privacy.py src/aeat/entrypoints/cli/test_profile_export_roundtrip.py src/aeat/entrypoints/cli/test_profile_import_idempotency.py` passed.
- `uv run pytest -q src/aeat/entrypoints/cli/test_profile_export_roundtrip.py src/aeat/entrypoints/cli/test_profile_import_idempotency.py` passed: 7 passed.
- Follow-up `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_profile_import_idempotency.py` passed.
- Follow-up `uv run pytest -q src/aeat/entrypoints/cli/test_profile_import_idempotency.py` passed: 3 passed.
