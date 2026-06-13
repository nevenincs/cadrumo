---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P02.S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s01-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s02-exec]]'
---

# `live-iva-compensation-wallet` `W05.P02.S03`

Added verified replacement-evidence gates for destructive remediation outcomes.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`RepairRemediationDecision` now rejects `quarantine` and `rebuild` outcomes
unless the decision includes explicit `verified_replacement_evidence_refs`.
This is separate from replacement-evidence requirements: requirements describe
what evidence must exist, while verified references prove the operator has named
the evidence before a destructive outcome can be recorded.

`export_required` remains non-mutating and can be recorded without verified
references because its purpose is to request evidence collection. The
`mutation_authorized` field remains hard-typed to `False`, so even a
verified-evidence quarantine/rebuild decision does not execute or authorize a
storage mutation.

The plan row was closed manually because the installed plan CLI accepts only
leaf `S##` ids and rejects the L3 display path `W05.P02.S03`; plain `S03` is
ambiguous in this expanded plan.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 37 passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 42 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py` passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
