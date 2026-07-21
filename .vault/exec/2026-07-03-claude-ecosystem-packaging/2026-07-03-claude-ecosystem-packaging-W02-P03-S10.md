---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S10'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Add a wheel-content test asserting the aeat wheel ships zero corpus pdf/xls/xlsx members while keeping the extracted-text, normative-html, registry and agent payload

## Scope

- `src/aeat/tests/test_wheel_content_boundary.py`

## Description

- Add `test_wheel_content_boundary.py` asserting a real built `aeat` wheel ships zero corpus `.pdf`/`.xls`/`.xlsx` members.
- Assert the extracted-text, normative-html, registry, and agent payload all survive the exclude introduced in `S08`.
- Commit `9036753743`.

## Outcome

- 6/6 tests passed against a real `uv build` wheel artifact.

## Notes

No incidents. No skipped work.
