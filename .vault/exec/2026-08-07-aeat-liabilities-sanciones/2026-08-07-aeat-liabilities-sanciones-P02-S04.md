---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:164f9e25d8c85c1ad909920605309b0a1aaf37515e4316cdc8cde376d4d3896d'
step_id: 'S04'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Add the LIVE_DEUDAS_SNAPSHOT_NAMESPACE bucket-scoped namespace constant beside LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE

## Scope

- `src/cadrumo/adapters/persistence/storage`

## Description

Added the `LIVE_DEUDAS_SNAPSHOT_NAMESPACE` bucket-scoped namespace beside
`LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE`, at `FINANCIAL` sensitivity,
`BUCKET_LOCAL` scope and `FULL_CUSTODY_ONLY` custody, with the object-key
grammar `deudas-snapshot:{bucket_id}:{snapshot_id}`.

## Outcome

Modified files:

- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py` (definition,
  `STORAGE_NAMESPACE_REGISTRY` roster entry, `__all__`)
- `src/cadrumo/adapters/persistence/storage/__init__.py` (facade import plus
  `__all__`)

The namespace is enrolled in the registry roster, not merely declared, so it is
covered by the hierarchy gates rather than being an orphan constant.

## Verification

`src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`,
27 tests, green. Landed in commit `685abbf6b4` with the rest of P02,
`12 0 .../_namespace_registry.py`, `2 0 .../storage/__init__.py`.

## Notes

Storage sensitivity is `FINANCIAL` because a debts snapshot states what AEAT
believes a taxpayer owes, which is financial data about the taxpayer under the
secure-storage-only mandate; custody is `FULL_CUSTODY_ONLY`, matching the
expedientes and notifications siblings rather than admitting a remote mirror.
