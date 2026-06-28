---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S240'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s240-s243-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S240`

Closed `AFR-138` for the operator-surface contract.

## Description

- Reviewed `src/aeat/application/operator_surface/_contract.py` as a static,
  cached backend contract surface.
- Verified it does not read files, construct direct SQL routes, read naked
  environment variables, write storage state, open remote providers, or swallow
  exceptions.
- Found a contract enrollment gap: the CLI mounts `aeat config bucket history`,
  and retired `archive` guidance points to `config bucket`, but the backend
  contract did not declare a `config bucket` command family.
- Enrolled `config bucket history` as a read-only mounted command family owned
  by `aeat.domain.buckets`.
- Closed `S240` through `vaultspec-core vault plan step check`.

## Outcome

`AFR-138` is closed as `manifest-discovery`. No storage migration was required:
the contract is in-memory metadata, but it now explicitly represents the
bucket-event history discovery surface instead of leaving that CLI path outside
the backend-owned operator-surface architecture.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/_models.py src/aeat/application/operator_surface/test_contract.py`
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

This step intentionally intersects `W12.P26.S243` because declaring the mounted
bucket family required adding `MountedCommandDomain.BUCKET` to the shared
operator-surface models.
