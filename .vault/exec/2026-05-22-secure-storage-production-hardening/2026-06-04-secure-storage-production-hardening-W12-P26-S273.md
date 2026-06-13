---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S273'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s273-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S273`

Closed `AFR-171` for the wizard command factory.

## Description

- Audited `src/aeat/application/wizard/_commands.py` for active-profile, manifest-bucket, and master-key custody concerns.
- Verified create/edit persistence enters profile storage spans rather than constructing repositories or master-key providers locally.
- Verified edit target resolution uses profile-bucket manifest discovery before opening a profile storage session.
- Verified settings and AEAT exception conventions are already used for output language and wizard refusals.
- Ran focused wizard command and pointer-atomicity gates.

## Outcome

`AFR-171` is closed as `manifest-discovery`. No code change was required: the command
factory is an orchestration layer over manifest-backed profile lookup and runtime-owned
storage spans.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py src/aeat/application/wizard/test_create_pointer_atomicity.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_create_pointer_atomicity.py src/aeat/application/wizard/test_commands_helpers.py`
- `uv run --no-sync vaultspec-rag search "wizard _commands profile_create_storage_span profile_storage_session read_profile_bucket manifest discovery master key" --type code --port 8766 --max-results 8`

## Notes

The broader plan check still reports only the existing `PLAN022` monotonic-order warning.
