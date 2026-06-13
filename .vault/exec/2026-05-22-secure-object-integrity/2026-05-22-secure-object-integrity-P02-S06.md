---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S06'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P02.S06`

Classified every hygiene violation surfaced by the ephemeral-key guard.

- Modified: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

## Description

Converted the guard's pending file list into an explicit path-to-classification inventory. Every current file-level hygiene exception is classified as requiring explicit repository injection or an autouse temporary database fixture. The guard still fails on any new unclassified file, and an additional test proves every pending classification is allowed and points to an existing source file.

This step classifies the backlog without broad repairs across unrelated feature surfaces. Follow-on work can burn down the inventory by converting individual files to explicit repository injection or shared isolation helpers.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

The focused guard run passed 2 tests.
