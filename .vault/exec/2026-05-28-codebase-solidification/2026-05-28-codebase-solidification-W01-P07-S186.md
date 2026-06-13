---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S186'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P07.S186

Add real-behavior test asserting `FilingStatus.FILED` is the sole source for `"filed"` in the affected code paths.

- Modified: `src/aeat/application/operator_surface/test_contract.py`

## Description

Extended `test_contract.py` with `test_filing_status_filed_is_sole_source_for_filed_token`.  The test:

1. Asserts `FilingStatus.FILED == "filed"` (enum value correctness).
2. Asserts `FilingStatus.FILED in live_family.commands` via the live `get_operator_surface_contract()` call
   (confirms the enum member propagates through the contract, not a bare string).
3. Scans `inspect.getsource(operator_surface._contract)` for bare `'"filed"'` literal occurrences and
   asserts zero are present — any regression that replaces `FilingStatus.FILED` with a bare string will
   fail this test immediately.

No mocks, no skips, no tautological assertions.  145 tests pass; 1 pre-existing locale-regex failure
in `test_require_accepted_root_uses_registered_application_error` is unrelated to this step.

Commit: `e9ed05094`
