---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P01.S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
---

# `live-iva-compensation-wallet` `W05.P01.S04`

Made repair attribution summary-first for large unreadable-row sets.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`aeat config repair integrity attribution` now defaults to summary mode. The
text output reports totals, payload disclosure, namespace role, owner
semantics, timestamp range, classification counts, and replacement-evidence
requirements. It does not print one line per unreadable row unless the operator
passes `--details`.

JSON output follows the same contract: summary mode removes `unreadable_rows`
from each namespace and carries `row_detail_mode=summary` plus the details hint.
`--details` restores the full metadata-only row list. The CLI privacy contract
now proves both modes avoid active profile UUIDs, taxpayer ids, periods, wallet
amount payload text, and private natural keys.

No destructive repair command was run. No live AEAT operation was performed.

## Tests

- `uv run pytest src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 4 passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 34 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
