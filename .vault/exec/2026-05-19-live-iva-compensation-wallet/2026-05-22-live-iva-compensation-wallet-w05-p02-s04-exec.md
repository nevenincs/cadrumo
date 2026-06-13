---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P02.S04'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s01-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s02-exec]]'
  - '[[2026-05-22-live-iva-compensation-wallet-w05-p02-s03-exec]]'
---

# `live-iva-compensation-wallet` `W05.P02.S04`

Disabled destructive quarantine for protected submission and filing-history namespaces.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`RepairNamespaceClassification` now carries `destructive_quarantine_allowed`
and `destructive_quarantine_policy`. Critical submission records, justificante
receipt metadata, remote filed-declaration evidence, local filing history, and
unknown namespaces are marked as not quarantineable without a separate engineer
override ADR.

`RepairRemediationDecision` now refuses a `quarantine` outcome for namespaces
whose classification disables destructive quarantine, even when the decision
has replacement-evidence requirements and verified evidence references. The
dry-run repair planner also surfaces the quarantine policy in text and JSON.

The plan row was closed manually because the installed plan CLI accepts only
leaf `S##` ids and rejects the L3 display path `W05.P02.S04`; plain `S04` is
ambiguous in this expanded plan.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 43 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
