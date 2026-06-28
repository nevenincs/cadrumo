---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S240]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S243]]'
---

# `secure-storage-production-hardening` `W12.P26.S240/S243` Review

## S240-001 | PASS | Contract and models are metadata-only

`_contract.py` builds cached in-memory `OperatorSurfaceContract` records.
`_models.py` defines strict frozen Pydantic models and enums. Neither file owns
durable storage, SQL routing, environment wrangling, repository writes, remote
provider calls, or plaintext persistence.

## S240-002 | FIXED | `config bucket` is now enrolled

The CLI mounts `aeat config bucket history`, and retired `archive` guidance
already points operators to `aeat config bucket`. The backend operator-surface
contract previously omitted that command family, leaving an accepted storage
inspection path outside the architecture contract. `MountedCommandDomain.BUCKET`
and the `config bucket` mounted family now close that gap.

## S240-003 | PASS | Mutability is read-only

The enrolled `config bucket history` family is classified as
`OperatorMutability.READ_ONLY`, matching its role as bucket-event history
inspection rather than profile/bucket mutation.

## S240-004 | PASS | Tests cover real contract shape

`test_contract.py` now asserts the backend contract exposes the bucket family,
its command tuple, its service owner, and its read-only mutability. This is a
contract-shape assertion over the actual builder, not duplicated business
logic.

## S240-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/_models.py src/aeat/application/operator_surface/test_contract.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-138` and `AFR-141` as `manifest-discovery`.
