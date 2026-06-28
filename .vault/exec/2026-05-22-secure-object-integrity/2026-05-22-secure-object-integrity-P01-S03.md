---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S03'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P01.S03`

Exposed unreadable-row attribution through the config repair integrity CLI surface.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`

## Description

Added `aeat config repair integrity attribution` as a read-only sibling to the existing `objects` and `registry` integrity subverbs. The command resolves the active profile bucket, emits an explicit no-active-profile metadata-only report on a cold root, and otherwise renders the grouped attribution report from the application layer in both text and JSON formats.

The text renderer prints namespace summaries, classification counts, and row metadata already validated by the strict attribution models. It does not add payload decryption or mutation paths.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run pytest src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/test_repair_integrity.py`

The focused test run passed 34 tests, including the new bootstrap-exempt coverage for `config repair integrity attribution`.
