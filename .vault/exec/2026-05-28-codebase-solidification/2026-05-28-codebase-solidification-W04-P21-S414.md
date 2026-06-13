---
step_id: "S414"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P21.S414

## Outcome

`IvaCompensationYearRangeError(AeatError, ValueError)` and
`IvaCompensationDecimalParseError(AeatError, ValueError)` introduced in
`src/aeat/application/calculations/_iva_compensation_history.py`. Three bare
`raise ValueError(...)` at lines 102, 133, 333 replaced. Registry entries added
under `REFUSED_IVA_COMPENSATION_YEAR_RANGE` and
`REFUSED_IVA_COMPENSATION_DECIMAL_PARSE`. Plan step closed.
