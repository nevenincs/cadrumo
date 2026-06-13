---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S55'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---


# W03.P09.S55 profile import/export public-output redaction

Scope: update profile export/import roundtrip tests to distinguish portable bundle identity from redacted public CLI output.

## Description

- Assert text export output uses the shared profile-id placeholder and does not emit the raw bucket UUID.
- Assert JSON export/import payloads use the shared profile-id placeholder and do not emit the raw bucket UUID.
- Assert import collision refusal output does not leak the raw bundle UUID.
- Keep the bundle and repository identity assertions intact so D5 identity preservation remains proven through storage, not stdout.

## Outcome

S55 is implemented for the current profile export/import roundtrip surface.

## Notes

Verification:

- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_profile_export_roundtrip.py` passed.
- `uv run pytest -q src/aeat/entrypoints/cli/test_profile_export_roundtrip.py` passed: 4 passed.
- Follow-up refusal-path gate passed after adding UUID leak assertions for collision outputs.
