---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S49'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

# `centralized-output-redaction` `W03.P09.S49`

Extended repair privacy coverage to assert the central output-redaction contract.

- Modified: `src/aeat/core/redaction/__init__.py`
- Modified: `src/aeat/core/test_redaction.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Created: `.vault/exec/2026-05-28-centralized-output-redaction/2026-05-28-centralized-output-redaction-W03-P09-S49.md`

## Description

`active_profile` is now enrolled in the central CLI profile-id key vocabulary. Repair-profile JSON shaping uses `redact_structured_for_cli_output` instead of a bespoke payload redactor, and profile-record status output now distinguishes `profile_id` from `bucket_id` using the shared placeholders. Repair privacy tests assert the central placeholders and hash form observed through real CLI output rather than command-local helper behavior.

## Tests

- `uv run ruff check src/aeat/core/redaction/__init__.py src/aeat/core/test_redaction.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- `uv run pytest -q src/aeat/core/test_redaction.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
