---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S581
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W10.P41.S581`

Created `test_w10_p41_rationale_inventory.py` — aggregate inventory test for all W10.P41 rationale markers.

- Created: `src/aeat/test_w10_p41_rationale_inventory.py`

## Description

Real-behavior AST + source walk with 27 assertions covering:
- 14 parametrized cases for S575 (profile.py field_validator markers)
- 2 parametrized cases for S576 (profile_catalogue.py catalogue-slot markers)
- 2 parametrized cases for S577 (google build-factory markers)
- 1 case for S578 asserting correct token present and superseded token absent in _borrador_100.py
- 1 case for S580 (logging.py scrub-overload marker)

No mocks, no skips, no xfail, no tautological assertions. The S578 anti-regression test would have caught the original CAST-RATIONALE token error before S578 was applied, confirming the test is non-tautological.

## Tests

27/27 passed in 0.12s. W9 inventory test also green (5 parametrized snapshot-dispatch cases including the newly added _borrador_100.py).
