---
step_id: S148
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P05-S147]]"
---

# codebase-solidification W01.P05.S148 — real-behavior tests for `_parse_bool`

## Outcome

`src/aeat/core/parsing/test_utils.py` added with `pytestmark = [pytest.mark.unit, pytest.mark.domain_core]`.

## Coverage

- Parametrized truthy tokens: `true`, `True`, `TRUE`, `1`, `yes`, `YES`, `y`, `Y`, `si`, `sí`, `SI`, `SÍ` → `True`
- Parametrized falsy tokens: `false`, `False`, `FALSE`, `0`, `no`, `NO`, `n`, `N` → `False`
- Absent/unknown tokens: `None`, `""`, `"maybe"`, `"MAYBE"`, `"2"`, `"yes please"`, `" "`, `"\t"` → `None`
- Standalone assertions: `None` input returns `None` (not `False`), empty string returns `None`, whitespace-only returns `None`
- Round-trip parametrize blocks confirming truthy and falsy sets are exhaustive

## Test outcomes

51 passed, 0 failed, 0 skipped.
