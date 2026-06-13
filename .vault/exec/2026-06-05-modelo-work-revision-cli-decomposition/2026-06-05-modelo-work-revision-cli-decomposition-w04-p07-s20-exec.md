---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S20'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P07.S20 Execution

Residual broad guard and focused gates passed.

Passed:
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_cli_module_size.py -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py::TestBorrador100Subgroup -q`
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_cli_surface.py::test_app_ledger_lifecycle_attach_records_purchase_invoice_evidence -q`
- `uv run --no-sync pytest src/aeat/tests/test_marker_integrity.py -q`

Result:
- The broad production CLI monolith guard now passes with no residual offenders.
