---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S35'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Test the requiresUserInteraction annotation is present on every CONFIRM-tier tool and absent on read-only tools

## Scope

- `src/aeat/entrypoints/mcp/tests/test_annotations.py`

## Description

- Add proof to `test_annotations.py` that `_meta["anthropic/requiresUserInteraction"]` is present on exactly the `CONFIRM`-tier tool set built by `build_sdk_tools`.
- Assert every read-only tool carries no `_meta` entry for the flag.
- Assert the derivation is automatic for a new `CONFIRM`-tier tool (no hand-listed-tool regression), exercising the real `confirmation_for_tool` classification rather than a stubbed policy.
- Commit `118ff006d0`.

## Outcome

- `pytest src/aeat/entrypoints/mcp/tests -m integration`: 138 passed (2 new).
- `ruff check` clean.

## Notes

No incidents. No skipped work.
