---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-07-17'
body_hash: 'sha256:2246a15ee4f52e88da5a570eaa27cfab0c6fc80636fc388757142b378dc07b3a'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step3-exec]]'
---

# `calculation-truth-registry` Code Review

Resolved findings:

- STEP3-001 | LOW | Import-contract gate used source text rather than real
  package imports. The gate now imports `aeat.domain.schema` and
  `aeat.domain.casillas`, then asserts the disabled writer names are absent
  from both package attributes and `__all__`.

Verification:

- Focused reviewer verification: 36 passed.
- Post-fix targeted `ruff check`: passed.
- Post-fix targeted `ty check`: passed.
- Post-fix focused test slice: 36 passed.

Residual risk:

- Full project tests were not run for this narrow public-export slice. The
  changed public APIs were covered by import-contract and domain package tests.
