---
step_id: S32
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S32 — real-behavior test for unexpected exception propagation

## Outcome

Added `src/aeat/entrypoints/cli/test_ledger_exception_propagation.py`
with two real-behavior tests exercising the production CLI surface via
`invoke_cached_cli`:

- `test_no_pointer_produces_profile_create_guidance`: no pointer file
  present → `NoActiveProfileError` is caught by the narrowed except →
  refusal output contains "profile create". Confirms the narrow except
  still handles the expected case.

- `test_corrupt_pointer_does_not_produce_profile_create_guidance`:
  `active-profile` pointer file present but missing `bucket_id` field →
  `pydantic.ValidationError` is raised → propagates past the narrowed
  except → top-level CLI boundary wraps it as `CliValidationBoundaryError`
  → output contains "validation" / "repair", NOT "profile create".

Anti-tautology proof: if S31 were reverted (broad `except Exception`
restored), the second test would fail because the `ValidationError` would
be swallowed and "profile create" would appear in the output, violating
the `assert _PROFILE_CREATE_GUIDANCE not in result.output` assertion.

No monkeypatching of production code. The corrupt-pointer scenario is
triggered by writing a real file to the real `tmp_path` storage root via
`isolated_sessionless_storage_root`.

## Files touched

- `src/aeat/entrypoints/cli/test_ledger_exception_propagation.py` (new)

## Verification

`pytest src/aeat/entrypoints/cli/test_ledger_exception_propagation.py -x` — 2 passed.
Commit: `761bc3129`.
