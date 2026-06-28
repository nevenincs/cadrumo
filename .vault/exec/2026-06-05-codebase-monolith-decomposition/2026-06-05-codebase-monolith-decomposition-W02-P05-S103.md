---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S103'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S103 Config Profile Verification

Scope: `src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py`, `src/aeat/entrypoints/cli/tests/test_cli_module_size.py`, profile export/import coverage.

## Description

- Ratchet `_config/__init__.py` module-size budget from 1464 to 1144 lines.
- Verify the extracted profile bundle command registrar with ruff.
- Run real CLI profile export/import roundtrip and idempotency tests.
- Run config boundary and module-size tests.

## Outcome

All focused checks passed. `_config/__init__.py` is now below the 1250-line production-module threshold and guarded by the tighter size budget.

## Notes

Verification commands passed for `ruff check`, `test_cli_module_size.py`, `_config/tests/test_config.py`, `test_profile_export_roundtrip.py`, and `test_profile_import_idempotency.py`.
