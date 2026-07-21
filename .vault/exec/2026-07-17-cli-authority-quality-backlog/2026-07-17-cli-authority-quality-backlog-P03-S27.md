---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S27'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# NEEDS ADJUDICATION and prerequisite for P03.S09: resolve the split namespace authority where clave-diagnostics namespace values are duplicated across core.external_constants (CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE, used by _clave_movil_support.py), a raw literal in _clave_permanente_support.py line 49 (no CLAVE_PERMANENTE core symbol, asymmetric), and the adapters storage registry (CLAVE_MOVIL and PERMANENTE_DIAGNOSTICS_NAMESPACE whose .namespace values are themselves raw literals duplicating core), plus raw classification SensitivityClass.SESSION and schema_version 1 at _clave_movil_page_flow.py lines 460-461 duplicating the registry namespace .sensitivity and .schema_version. Decide the single authority (core.external_constants versus the adapters storage registry) and whether registry values source from core, then single-source all consumers, gated on one authority with no duplicated namespace literal across core, registry, and consumer

## Scope

- `src/cadrumo/core/external_constants.py`
- `src/cadrumo/adapters/persistence/storage/_namespace_registry.py`
- `src/cadrumo/adapters/outbound/aeat/auth/`

## Description

Adopt Option 1 of the accepted adjudication: the storage namespace registry definition is the single authority for clave-diagnostics namespace metadata.

- Delete the retired `CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE` string constant from `core/external_constants.py` (delete-not-alias).
- Remove its re-export chain: the import and `__all__` entry in `_clave_movil.py`, and the import and `__all__` entry in the auth package `__init__.py`.
- Repoint `_clave_movil_support.py` to import `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` from the storage package public facade and source its module-local `DIAGNOSTIC_NAMESPACE` alias from `.namespace`.
- Replace the raw `SensitivityClass.SESSION` and `schema_version=1` literals in the `_clave_movil_page_flow.py` diagnostic save with `.sensitivity` and `.schema_version` read off the registry def; drop the now-unused `SensitivityClass` import.
- Delete the dormant clave-permanente diagnostics declarations: the `DIAGNOSTIC_NAMESPACE` literal and its `__all__` entry in `_clave_permanente_support.py`, and the `CLAVE_PERMANENTE_DIAGNOSTICS_NAMESPACE` registry def with its registry-list and `__all__` entries.
- Repoint the two test consumers of the deleted core symbol (`_runtime_attached_repositories_support.py`, `application/auth/tests/test_diagnostics.py`) to the registry def's `.namespace`.
- Update the registry parity test to 66 rows and drop the clave-permanente tuple.
- Add a write-path binding proof persisting a diagnostic through the page-flow's exact symbols and asserting the persisted namespace, classification, and schema_version equal the registry def.

## Outcome

Single typed authority for clave-diagnostics namespace metadata. The four-tier duplication (core string, registry def raw literal, support alias, raw sensitivity/schema literals) is collapsed onto the registry def. The dormant clave-permanente diagnostic namespace, which had no producer writing it, is deleted rather than repointed. Targeted suites (`adapters/outbound/aeat/auth`, `adapters/persistence/storage`, `application/auth`) pass except the seven `CADRUMO_LIVE_TESTS_ENABLED`-gated live tests, which are environmental and pre-existing. Import-hygiene, lazy-import-policy, docstring-core-struct-links, ruff, and ty gates are green; `import cadrumo.adapters.outbound.aeat.auth` resolves clean.

## Notes

The clave-permanente follow-up flagged in the ADR consequences was confirmed dormant: no `.save()` producer references the clave-permanente diagnostic namespace and the registry def was not re-exported from the storage facade, so it was deleted (delete-not-keep-dead-code) rather than wired. The new intra-adapters import (`adapters.outbound.aeat.auth` -> `adapters.persistence.storage`) is intra-layer and precedented; it did not trip the import-hygiene or lazy-import gates.
