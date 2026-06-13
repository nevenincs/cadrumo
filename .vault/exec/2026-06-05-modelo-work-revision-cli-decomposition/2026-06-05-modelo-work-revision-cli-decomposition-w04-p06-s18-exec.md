---
tags: ['#exec', '#modelo-work-revision-cli-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S18'
related:
  - '[[2026-06-05-modelo-work-revision-cli-decomposition-plan]]'
---

# W04.P06.S18 Execution

Verified the ledger residual extraction.

Passed:
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_cli_surface.py::test_app_ledger_lifecycle_attach_records_purchase_invoice_evidence -q`
- Real CLI diagnostic: isolated profile plus `aeat --format json app ledger evidence list` returned `count: 0`.
- `uv run --no-sync ruff check ... _ledger.py _ledger_evidence_cli.py ...`
- `uv run --no-sync python -m compileall -q ... _ledger.py _ledger_evidence_cli.py ...`

Additional test-topology fix:
- Corrected stale relative imports in `test_cli_surface.py` exposed by the moved `entrypoints/cli/tests` package.
