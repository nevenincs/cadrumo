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
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s240-s243-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S240` Review

## S240-001 | PASS | Contract is manifest discovery, not storage ownership

`src/aeat/application/operator_surface/_contract.py` declares immutable
operator-surface contract records and cached lookup helpers. It does not build
storage repositories, select secure storage backends, build SQL routes, read
environment variables, open files, write plaintext side stores, or mutate
bucket state.

## S240-002 | FIXED | Bucket inspection is enrolled

The CLI already mounts `aeat config bucket history`, and retired `archive`
guidance points operators to `aeat config bucket`. S240 now declares the
`config bucket` command family in the backend contract as read-only bucket
event-history discovery owned by `aeat.domain.buckets`.

## S240-003 | PASS | Cross-step model change is explicit

The contract fix required `MountedCommandDomain.BUCKET`, which is tracked by
`W12.P26.S243`. The combined S240/S243 review records the coupled model and
contract change so the plan does not hide the cross-file dependency.

## S240-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/operator_surface/_contract.py src/aeat/application/operator_surface/_models.py src/aeat/application/operator_surface/test_contract.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/operator_surface/test_contract.py` passed with 15 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-138` as `manifest-discovery`; implementation hardening
was required to enroll the real `config bucket` surface.
