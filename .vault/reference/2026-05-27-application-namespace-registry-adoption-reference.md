---
tags:
  - '#reference'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Application Namespace Registry Adoption Reference

## Scope

This reference grounds `W03.P05.S23`, which requires application repositories to consume secure-object namespace definitions from the central storage registry instead of owning local namespace, schema-version, sensitivity, or object-key literals.

## Existing Registry Pattern

The central registry lives in `src/aeat/adapters/persistence/storage/_namespace_registry.py` and exports `SecureObjectNamespaceDefinition` instances through `src/aeat/adapters/persistence/storage/__init__.py`. The registry records namespace value, owner, sensitivity, schema version, object-key grammar, default object key, and scope.

Application repositories already follow this pattern in the current tree:

- `src/aeat/application/workflow/_persistence.py` imports `WORKFLOW_STATE_NAMESPACE` and `WORKFLOW_RUN_NAMESPACE`, then derives namespace, schema version, sensitivity, and default object key from those definitions.
- `src/aeat/application/user_profile/_repository.py` imports `USER_PROFILE_VALUE_NAMESPACE` and `USER_PROFILE_SNAPSHOT_NAMESPACE`, then derives public compatibility constants from the registry entries.
- `src/aeat/application/filing/_history_repository.py` imports `APPLICATION_FILING_HISTORY_NAMESPACE` and uses its namespace, sensitivity, and schema version.
- `src/aeat/application/auth/_apoderado.py` imports `AUTH_APODERADO_CONFIGURATION_NAMESPACE` and derives its repository class attributes from that entry.
- `src/aeat/application/auth/_diagnostics.py` imports `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` and derives diagnostic namespace, sensitivity, and schema version from that entry.
- `src/aeat/application/calculations/_observations_repository.py` imports the calculation and IVA-wallet reconciliation namespace entries and derives repository namespace metadata from them.
- `src/aeat/application/calculations/_iva_compensation_history.py` imports `IVA_COMPENSATION_HISTORY_NAMESPACE`.
- `src/aeat/application/ledger/_rule_repository.py` imports `LEDGER_CLASSIFICATION_RULES_NAMESPACE`.
- `src/aeat/application/live/_borrador_100.py`, `src/aeat/application/live/_censo.py`, and `src/aeat/application/live/__init__.py` derive live snapshot and acquisition namespace metadata from registry definitions.

## Discovery Result

The production application scan originally found no remaining literal `aeat.*` namespace assignments or direct secure-object namespace arguments outside tests. Code review identified one remaining non-registry namespace constant path in auth diagnostics: it imported the Clave Movil diagnostic namespace from the outbound adapter and paired it with local sensitivity/schema literals. `W03.P05.S23` moved that path to `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE`.

`W03.P05.S23` closes by adding an application-level guard that scans production application modules and rejects future namespace literals assigned to namespace constants/class attributes, direct secure-object namespace literals, or secure-object calls that use namespace constants not imported from the storage registry surface.
