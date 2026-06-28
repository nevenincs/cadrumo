---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W01.P01.S01 - over-limit module inventory

Scope: `src/aeat`.

## Description

- Ran exact `fd` and Python `splitlines()` inventory over every Python module under `src/aeat`.
- Classified each over-1250-line module as production or test scope.
- Preserved the inventory as the current decomposition baseline after the business invoice extraction.

## Outcome

Current over-1250-line inventory:

```text
 3814 production src/aeat/application/modelo/_actions.py
 3784 production src/aeat/application/ledger/_actions.py
 3550 production src/aeat/entrypoints/cli/_ledger.py
 3093 test       src/aeat/tests/fixtures/justificantes/_generate.py
 2890 production src/aeat/entrypoints/cli/_config/__init__.py
 2708 production src/aeat/domain/calculations/registry/_bindings.py
 2605 production src/aeat/application/live/__init__.py
 2584 production src/aeat/domain/calculations/registry/_schema.py
 2514 test       src/aeat/application/ledger/tests/test_actions.py
 2375 test       src/aeat/adapters/inbound/declaracion/tests/test_verification_chain.py
 2274 production src/aeat/core/errors/registry/_domain.py
 2134 production src/aeat/adapters/outbound/aeat/sede/_declarations.py
 2079 test       src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py
 2061 production src/aeat/entrypoints/cli/_app_live.py
 2045 test       src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects.py
 1967 test       src/aeat/application/modelo/tests/test_file_flow.py
 1881 production src/aeat/entrypoints/cli/_modelo.py
 1848 test       src/aeat/adapters/outbound/aeat/sede/tests/test_declarations.py
 1781 production src/aeat/domain/calculations/registry/_record_design.py
 1757 production src/aeat/adapters/persistence/storage/master_key/_master_key.py
 1719 production src/aeat/adapters/outbound/aeat/auth/_clave_movil.py
 1667 production src/aeat/adapters/persistence/storage/sql/secure_objects.py
 1565 test       src/aeat/domain/calculations/registry/tests/test_registry_schema.py
 1511 test       src/aeat/entrypoints/cli/tests/test_modelo.py
 1473 production src/aeat/core/config.py
 1454 production src/aeat/domain/calculations/registry/_applicability.py
 1437 production src/aeat/adapters/outbound/aeat/auth/_authenticator.py
 1419 production src/aeat/core/errors/registry/_application.py
 1400 production src/aeat/application/auth/_operator.py
 1399 production src/aeat/entrypoints/cli/_config/_google.py
 1387 test       src/aeat/domain/calculations/registry/tests/test_referential_integrity.py
 1356 test       src/aeat/adapters/outbound/aeat/auth/tests/test_authenticator.py
 1336 production src/aeat/domain/calculations/registry/_workbook_parity.py
 1295 production src/aeat/core/errors/registry/_adapters.py
 1294 production src/aeat/adapters/outbound/google/_calc_sheets_apply.py
 1289 production src/aeat/application/workflow/_engine.py
 1265 test       src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py
```

## Notes

No files were modified for this step.
