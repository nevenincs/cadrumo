---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P02.S02'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s01-exec]]'
---

# `live-iva-compensation-wallet` `W05.P02.S02`

Added a dry-run preserve-first remediation planner.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`build_repair_remediation_plan` now converts unreadable-row attribution into a
metadata-only remediation plan. The plan always reports `dry_run=true`,
`planned_mutations=0`, and `mutation_allowed=false` for every namespace item.
Rows with namespace replacement-evidence requirements are presented as
`export_required`; unknown or unclassified rows remain `preserve` with engineer
review as the next action.

The CLI exposes this through `aeat config repair plan`. The command handles a
cold root with no active profile, does not write repair decisions, does not
quarantine or rebuild rows, and does not perform live AEAT operations.

The plan row was closed manually because the installed plan CLI accepts only
leaf `S##` ids and rejects the L3 display path `W05.P02.S02`; plain `S02` is
ambiguous in this expanded plan.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 41 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
