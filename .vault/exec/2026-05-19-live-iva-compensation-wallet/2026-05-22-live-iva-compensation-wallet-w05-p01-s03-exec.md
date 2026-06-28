---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'W05.P01.S03'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-21-secure-object-database-drift-research]]'
  - '[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]'
---

# `live-iva-compensation-wallet` `W05.P01.S03`

Added namespace-level replacement-evidence requirements to repair namespace
classification.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `.vault/plan/2026-05-19-live-iva-compensation-wallet-plan.md`

## Description

`RepairNamespaceClassification` now carries metadata-only replacement evidence
requirements. The requirements are derived from the namespace role, IVA
relevance, and destructive repair risk so remediation planning has explicit
preserve-first prerequisites before any row can be treated as remediable.

Wallet evidence requires a fresh read-only AEAT wallet observation or exported
existing observation plus replayed wallet reconciliation. Critical receipt and
submission namespaces require verified AEAT Sede or justificante evidence and
remain destructive-quarantine disabled without a later override ADR. Unknown
namespaces require repository-owner identification, encrypted backup, and
engineer preserve-first review.

The CLI text render now prints one `replacement_evidence_required` row for each
requirement so the default operator surface does not hide the preserve-first
requirements in JSON only.

No destructive repair command was run. No live AEAT operation was performed.

## Tests

- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q --disable-warnings` completed with 34 passed.
- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py` passed.
