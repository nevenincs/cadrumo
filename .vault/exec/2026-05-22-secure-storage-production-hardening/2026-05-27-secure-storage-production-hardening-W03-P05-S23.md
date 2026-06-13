---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S23'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w03-p05-s23-review-audit]]'
  - '[[2026-05-27-application-namespace-registry-adoption-reference]]'
---

# `secure-storage-production-hardening` `W03.P05.S23`

Replaced the remaining application auth diagnostic namespace policy with the storage registry definition and added a guard for application repository namespace adoption.

- Modified: `src/aeat/application/auth/_diagnostics.py`
- Added: `src/aeat/application/test_namespace_registry_adoption.py`
- Added: `.vault/reference/2026-05-27-application-namespace-registry-adoption-reference.md`
- Added: `.vault/audit/2026-05-27-secure-storage-production-hardening-W03-P05-S23-review.md`

## Description

Application auth diagnostics now imports `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` from the storage registry and derives the diagnostic namespace, sensitivity, and schema version from that definition. This removes the remaining production application use of a namespace constant owned by an outbound adapter.

The new application namespace adoption guard scans production application modules and rejects secure-object namespace literals, namespace assignments outside registry derivation, and secure-object calls that use namespace constants not sourced from the storage registry surface. The reference note records the application files already following the registry-derived pattern and the auth diagnostics correction made during this step.

## Tests

Passed:

- `uv run ruff check src/aeat/application/test_namespace_registry_adoption.py src/aeat/application/auth/_diagnostics.py src/aeat/application/auth/test_diagnostics.py .vault/reference/2026-05-27-application-namespace-registry-adoption-reference.md`
- `uv run pytest src/aeat/application/test_namespace_registry_adoption.py src/aeat/application/auth/test_diagnostics.py -q`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

`uv run python -m aeat.locales audit` was run as required and failed on unrelated shared-worktree locale parity drift outside this step.
