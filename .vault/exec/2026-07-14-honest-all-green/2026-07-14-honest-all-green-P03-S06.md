---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S06'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Fix the secure-object integrity diagnostics failures after master-key rotation

## Scope

- `src/cadrumo diagnostics integrity`

## Description

- Re-ran the three failing diagnostics tests sequentially at HEAD; all three raised `StorageValidationError` (`KeyError` on an unregistered namespace) from inside the secure-object integrity probe, not a crypto/key-rotation defect.
- Traced the mechanism: `_probe_secure_objects_integrity` lists every namespace present in the table and calls `repo.probe_namespace_integrity(ns)`; that method (and its row-level companion `iter_namespace_decryptability`) called `_check_session_freshness(namespace)`, which enforces namespace registration and raises on any unregistered namespace. The broad-except then records the whole namespace as `readable=0, unreadable=1` instead of counting the individual rows, so the K2-readable row is dropped and the K1 unreadable rows are undercounted.
- Confirmed this was introduced by the rename commit `dec439b019`, which added the `namespace` parameter to `_check_session_freshness` and threaded it into these crypto-layer probes, turning them into registration-enforcing reads. The test namespaces (formerly `aeat-test.*`, an unregistered prefix) had to move to `cadrumo-test.*` (also unregistered), so the newly-added enforcement started refusing them.
- Established the correct pattern from the siblings that do the same job: `list_namespaces()` and `quarantine_unreadable_rows()` both call `_check_session_freshness()` with NO namespace argument (session/route freshness only, no registration enforcement) and correctly handle unregistered namespaces - which is why `quarantine_unreadable_secure_objects` passed while the probe-based paths failed.
- Fixed `probe_namespace_integrity` and `iter_namespace_decryptability` to call `_check_session_freshness()` without the namespace argument, matching their documented intent (a strictly crypto-layer probe that intentionally bypasses the consumer classification / schema-version / registration contracts) and their siblings. No key-derivation, key-schedule, or DEK/KEK code was touched.

## Outcome

All three failing tests pass sequentially, and the full `test_diagnostics.py` plus the storage suites that exercise these probes and the refusal contracts (`test_runtime.py`, `test_secure_objects_part3.py` former-product refusal, `test_namespace_registry.py`, `test_namespace_registry_adoption.py`, `test_repair_integrity.py`) are green: 108 passed, `-n 0`. Ruff clean. The session/route-mismatch refusal is preserved (the route check in `_check_session_freshness` is namespace-independent; `test_runtime_bound_repository_refuses_diagnostics_after_session_bucket_changes` still passes), and the former-product-namespace refusal on consumer reads/writes is untouched (it lives on `exists`/`list_keys`/`save`/`delete`, not on the crypto probe).

## Notes

Per the key-management caution in the dispatch brief and `no-legacy-compatibility`, I verified the fix touches no key schedule or key-derivation branch: it changes only which pre-probe contract check runs (session/route freshness, yes; namespace registration, no) before a read-only crypto count. No peer WIP on `secure_objects.py` (last commits 2026-07-12/13, working tree clean before my edit). Committed with an explicit pathspec.
