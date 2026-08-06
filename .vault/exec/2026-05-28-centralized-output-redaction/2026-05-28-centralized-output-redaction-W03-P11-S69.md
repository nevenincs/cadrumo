---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:46dfb2219ddfa9d342d1cebd28071a476652626fb17967a5a764cd7978c9d383'
step_id: 'S69'
related:
  - "[[2026-05-28-centralized-output-redaction-plan]]"
---

# update Windows encoding tests to preserve redacted output rendering

## Scope

- `src/aeat/entrypoints/cli/test_windows_encoding.py`

## Description

- Validate Windows encoding tests so redacted output rendering remains stable across console encodings.

## Outcome

- `uv run pytest -q src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/entrypoints/cli/test_windows_encoding.py` passed: 13 passed.

## Notes

- Reviewer noted `test_write_stderr_redacts_sensitive_canaries` still asserts the literal placeholder `profile=<profile-id>`. This remains compatible with the current central vocabulary and should be revisited only if the placeholder vocabulary changes.
