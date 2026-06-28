---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S243'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s240-s243-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S243`

Closed `AFR-141` for the operator-surface models.

## Description

- Reviewed `src/aeat/application/operator_surface/_models.py` as strict
  Pydantic contract metadata.
- Verified it owns no durable storage, route construction, environment access,
  repository writes, or remote providers.
- Added `MountedCommandDomain.BUCKET` so the backend contract can represent the
  real `config bucket` CLI family without overloading diagnostics or profile
  lifecycle domains.
- Closed `S243` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-141` is closed as `manifest-discovery`. The models remain strict, frozen
contract records; the new enum member is used by the S240 contract enrollment
for `config bucket history`.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/_models.py src/aeat/application/operator_surface/test_contract.py`
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The coupled S240/S243 change keeps CLI architecture enrollment coherent: the
contract model gains exactly the domain enum needed by the mounted command
family, and no storage implementation is added here.
