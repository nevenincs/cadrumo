---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S233'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s233-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S233`

Closed `AFR-131` for the modelo action orchestration surface.

## Description

- Reviewed `src/aeat/application/modelo/_actions.py` against the
  secure-storage affected-file register, prior storage audits, and the
  2026-06-03 modelo export evidence/workbook parity ADRs.
- Used vaultspec RAG semantic searches to confirm the IVA wallet gate duplicate
  implementation now has one production owner in `_iva_wallet_gate.py`, and that
  modelo secure-object persistence ownership clusters in domain runtime
  repositories.
- Preserved `_actions.py` as an orchestration layer over secure runtime
  repositories and live workflow/provider gates.
- Cross-committed the concurrent IVA-wallet gate extraction in the same action
  file because the storage/API hardening touched the same import and helper
  surface.
- Localised remaining user-facing modelo action guard errors through
  `python -m aeat.locales set`: IVA-wallet guard failures, ledger preflight
  refusal, registry snapshot/root failures, amendment/import unknown casillas,
  and duplicate external-import revision refusal.
- Closed `S233` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-131` is closed as `remote-mirror`. Local durable modelo state remains
handled by runtime-backed secure-object repositories, while the action module
coordinates live workflow/provider gates and typed modelo lifecycle transitions.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/modelo/_actions.py src/aeat/application/modelo/test_actions.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/modelo/test_actions.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/application/modelo/test_bucket_aggregation_flow.py src/aeat/application/modelo/test_import_flow.py`
- `$env:PYTHONPATH='src'; uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "modelo or s85_runtime"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

Locale catalogue leaves were updated exclusively through the canonical
`aeat.locales` CLI. No naked environment access, settings bypass, silent
exception swallowing, `noqa`, `pragma`, monkeypatch, fake, mock, skip, xfail,
or tautological test was introduced.

Residual observation for follow-up: `WorkflowRunRepository.save()` still
resolves its marker directory with a direct `Settings()` constructor in
`src/aeat/application/workflow/_persistence.py`; S233 did not change that
adjacent workflow persistence owner.
