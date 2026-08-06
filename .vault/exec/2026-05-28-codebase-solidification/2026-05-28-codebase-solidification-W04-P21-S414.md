---
step_id: "S414"
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-07-17'
body_hash: 'sha256:f751b0ceafa368d2e5e3cf187a30e66b4db1a51fa35e99cb1e77c65212dd4f67'
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
