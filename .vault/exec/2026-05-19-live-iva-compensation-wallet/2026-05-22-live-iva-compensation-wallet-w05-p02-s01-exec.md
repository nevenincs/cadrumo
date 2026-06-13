---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P02.S01'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
---

# `live-iva-compensation-wallet` `W05.P02.S01`

Added durable, profile-local, non-destructive repair decision records.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`RepairRemediationDecision` now records preserve, quarantine, rebuild, and
export-required planning outcomes without authorizing mutation. The model
records the target namespace, optional row digest, decided time, reason, likely
origin, replacement-evidence requirements, and verified evidence references.
The `mutation_authorized` field is hard-typed to `False`. Decision ids are
content-bound to the decision fields so callers cannot persist an arbitrary
sha-shaped key for a different remediation target or evidence requirement set.

`RepairRemediationDecisionRepository` persists those decisions as encrypted
AUDIT-class secure-object rows in a profile-local namespace. Object keys are
opaque SHA-256 decision ids and the repository supports save, load, and
decision-time ordered listing. The repair namespace classifier also treats the
decision namespace as preserve-first remediation context.

No destructive repair command was run. No live AEAT operation was performed.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py -q --disable-warnings` completed with 36 passed.
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 40 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
