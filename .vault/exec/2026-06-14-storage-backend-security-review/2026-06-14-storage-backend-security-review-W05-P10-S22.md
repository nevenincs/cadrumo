---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S22'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---




# Extend the namespace adoption gate to scan domain and adapters outbound in addition to application

## Scope

- `src/aeat/application/tests/test_namespace_registry_adoption.py`

## Description

- Rewrite the namespace-adoption gate (`test_namespace_registry_adoption.py`) to
  the cross-check enforcement: scan application + domain + adapters/outbound and
  require every `aeat.*` namespace string used as a secure-object namespace
  (assigned to a `*_NAMESPACE` target or passed as a secure-object call's
  `namespace`) to equal a value in `STORAGE_NAMESPACE_REGISTRY`.

## Outcome

The gate now enrolls the domain (and outbound, application) namespaces under the
registry authority across all three trees WITHOUT requiring an eager storage
import (which would break the json-pipe-safety lazy-import tests). A literal that
matches no registered namespace fails as drift; legitimate non-registry
`_NAMESPACE` constants (mirror sync-state keys, `"_probe"` markers) are not `aeat.*`
namespaces and are no longer over-flagged. Gate passes across the full codebase.
Committed in `a1175f9be`.

## Notes

This supersedes the original gate's "must import the constant" rule, which was
infeasible for the lazy domain modules. The named registry constants promoted in
S21 (`ea0a4c99d`) remain the authority the gate cross-checks against and are
available to any non-lazy consumer that wants the constant directly.
