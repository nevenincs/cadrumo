---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S561'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-adr]]'
---

# `codebase-solidification` `W09.P38.S561`

Added real-behavior inventory test at `src/aeat/test_w09_p38_rationale_inventory.py`.

- Created: `src/aeat/test_w09_p38_rationale_inventory.py`

## Description

Three test functions cover the three marker families:

- `test_financial_provider_teardown_broad_except_carry_rationale`: walks `_pdf_n26.py`, `_xlsx.py`, `_ofx.py` source text and asserts the mandated `BROAD-EXCEPT-RATIONALE-*` tokens are present.
- `test_profile_lazy_module_helpers_carry_any_return_rationale`: locates `_m`, `_p`, `_ccaa` def lines in `profile.py` via string scan and asserts `ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE` on each.
- `test_snapshot_dispatch_hooks_carry_kwargs_any_rationale`: parametrised over four files, walks lines using a 10-line pre-definition window to allow block-comment style markers.

All tests use `pytestmark = [pytest.mark.unit, pytest.mark.domain_core]`. No mocks, no skips, no AST-only execution — the checks read real source files from disk.

## Tests

6 passed, 0 failed. Commit: `1c2b02e82`.
