---
tags:
  - '#exec'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S02'
related:
  - "[[2026-07-02-arch-remediation-data-budget-plan]]"
---

# Add a packaging content-boundary gate that builds the wheel and asserts no tests member is present

## Scope

- `src/aeat/tests/test_wheel_content_boundary.py`

## Description

- Author `test_wheel_content_boundary.py`: build the real wheel via `uv build --wheel` and assert no member lives under any `tests/` package.

## Outcome

The wheel-content boundary is an executable contract: the tests exclude is proven to take effect (3-test module, green; wheel builds in ~20s).

## Notes
