---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S309'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-core-plaintext-exception-closeout-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S309`

Closed the `core.output_rendering` plaintext exception row.

## Changes

- Changed unsupported-output and JSON-rendering failures to raise registered AEAT exceptions with locale-backed messages and structured context instead of raw English exception text.
- Updated output-rendering tests to assert registered error rendering rather than raw exception strings.

## Validation

- `uv run ruff check src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py`
- `uv run pytest src/aeat/core/test_output_rendering.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`
