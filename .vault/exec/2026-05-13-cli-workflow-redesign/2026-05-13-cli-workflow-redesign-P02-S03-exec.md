---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P02.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P02.S03`

Added typed contract tests covering the new `DiagnosticCheck`
validator surface and migrated the dispatch-helper tests so the
`_overall_status` fixtures comply with the always-actionable
contract.

- Modified: `src/aeat/application/test_diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics_dispatch.py`

## Description

The diagnostics test module gains seven contract assertions:

- fail row missing both fields raises `ValidationError`
- warn row missing both fields raises `ValidationError`
- row with both fields populated raises `ValidationError`
- ok row with both fields `None` constructs successfully
- ok row with `next_action` populated raises `ValidationError`
- fail row with `dead_end` only constructs successfully
- `model_dump(mode="json")` surfaces both keys explicitly

The dispatch-test fixtures that previously built `warn`/`fail` rows
without recovery information now supply a minimal `next_action` or
`dead_end`. The structural assertions (`_overall_status` priority
rollup, profile / auth branch identification) are unchanged.

## Confirmation

- `pytest src/aeat/application/test_diagnostics.py` 15 / 15 green.
- `pytest src/aeat/application/test_diagnostics_dispatch.py` 13 / 15
  green; the two failures (`test_auth_check_no_provider_*` and
  `test_auth_check_provider_configured_*`) pre-date this phase and
  are owned by P04 / P05 (a stale assertion against the old
  `aeat config auth` command string).
