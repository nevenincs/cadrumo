---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-10-03'
body_hash: 'sha256:6e32f677349a96e41975951211d4ebfe0687e249867cbc0bdd5b3cbcdbc2c2ae'
related: []
---

# `secure-storage-production-hardening` `W12.P26.S247` Review

## S247-001 | FIXED | Namespace enumeration failure no longer becomes a clean report

`_build_repair_integrity_report` previously caught every namespace-listing exception and continued with `namespaces = ()`, which could produce an `ok` diagnostic under storage failure. The function now lets namespace enumeration failures propagate, preserving fail-closed repair behavior.

## S247-002 | PASS | Runtime-default secure-object routing remains enrolled

The no-argument repair-integrity and repair-list report builders enter the active bucket repair session and resolve `secure_object_repository_for_active_bucket`. Repair-remediation decisions are saved and loaded through `SecureObjectRepository` using the registered repair decision namespace, sensitivity, and schema version.

## S247-003 | PASS | Privacy boundary exposes digests, not payloads

Repair list rows surface `object_key_digest`, decryptability status, row metadata, and unreadable reasons only. Payload bytes remain inside the secure-object repository and are not rendered by the application report.

## S247-004 | PASS | Exception handling is observable

The active bucket session fallback logs debug metadata before allowing diagnostics to continue. The repaired namespace enumeration path no longer swallows repository/storage errors.

## S247-005 | FIXED | Repair-remediation refusals are localized structured errors

`RepairIntegrityError` and `RepairDecisionNotFoundError` call sites for list-filter conflicts, decision-id mismatches, and missing decisions now use `translated_message` keys with structured context instead of raw English prose. Focused tests assert the error key/context contract without duplicating repository logic.

## S247-006 | PASS | Validation

- the historical check passed.
- the historical check passed with 13 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.

Disposition: close `AFR-145` as `runtime-default`.
