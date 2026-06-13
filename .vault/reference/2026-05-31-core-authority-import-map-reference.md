---
tags:
  - '#reference'
  - '#core-authority-import-map'
date: '2026-05-31'
modified: '2026-05-31'
related: []
---

# `core-authority-import-map` reference

## Module(s)
All `src/aeat/` Python modules across six layers: `core`, `domain`, `application`, `adapters`, `entrypoints`, `tests`.

## File(s)
- `src/aeat/core/**/*.py` — core utilities (i18n, logging, paths, config, resources)
- `src/aeat/domain/**/*.py` — domain logic (25+ bounded contexts: invoices, iva, fincas, modelos, etc.)
- `src/aeat/application/**/*.py` — application services and orchestration
- `src/aeat/adapters/**/*.py` — inbound/outbound adapters and persistence
- `src/aeat/entrypoints/**/*.py` — CLI and API entry points
- `src/aeat/tests/**/*.py` — shared test infrastructure

## Findings

### Import-Direction Violations Summary

Architecture rules and current state:

1. **core → downward**: CLEAN. Core imports from domain/application/adapters/entrypoints: 0 production violations. Only test files (1 violation).

2. **domain → sibling domains**: MOSTLY CLEAN. 88 intra-domain imports recorded; 11 are registry-exception legal (via `domain.calculations.registry`). Production: 0 violations on sibling cross-domain. Tests: 77 violations (tests routinely import across domain boundaries for integration).

3. **domain → application/adapters/entrypoints**: 1 production violation found in `src/aeat/domain/user_profile/_registry_contract.py` importing from `aeat.application`. Tests: 15 violations (acceptable pattern).

4. **application → adapters/entrypoints**: CLEAN. Application correctly imports adapters (56 instances), but never the reverse. No production violations.

5. **adapters → application/entrypoints**: CLEAN. Adapters do not import upward. 14 instances of adapter→application are actually test-only files (e.g., test_runtime_migrated_repositories.py); production code is boundary-clean.

6. **Adapter → domain binding**: Healthy. 13 adapter modules reference domain packages; most are tightly bound to 1–2 domain contexts. Top reference: `persistence/storage/test_runtime_migrated_repositories.py` (4 domains: calculations, justificante, modelos, profile) — test-only.

### Violation Inventory

**Total violations: 165 recorded**
- Production violations: 1
- Test violations: 164

**Production violation detail:**
- File: `src/aeat/domain/user_profile/_registry_contract.py`
- Violation: `domain` → `application` (non-registry import)

**Hot test-violation files (top 5):**
1. `src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py` (11 violations)
2. `src/aeat/domain/invoices/test_reconciliation.py` (7 violations)
3. `src/aeat/application/test_diagnostics.py` (5 violations)
4. `src/aeat/application/test_repair_integrity.py` (5 violations)
5. `src/aeat/domain/invoices/test_repository.py` (5 violations)

### Registry-Exception Count

11 domain-to-domain imports are legal because they target `aeat.domain.calculations.registry` (the canonical registry bootstrap layer that all domains are allowed to reference).

### Per-Layer Import Matrix

| Source | core | domain | application | adapters | entrypoints | tests |
|--------|------|--------|-------------|----------|-------------|-------|
| core | 43 | 1 | 1 | 0 | 0 | 1 |
| domain | 112 | 88 | 3 | 13 | 0 | 11 |
| application | 83 | 142 | 149 | 56 | 0 | 45 |
| adapters | 38 | 37 | 14 | 106 | 0 | 13 |
| entrypoints | 43 | 32 | 92 | 57 | 47 | 105 |

## Remediation Path

1. **Production violation:** Inspect `src/aeat/domain/user_profile/_registry_contract.py` for the application import and refactor to use domain-layer contracts only.

2. **Test violations:** Acceptable under testing discipline. Tests legitimately cross boundaries for integration; no action required.

3. **Adapter binding:** All adapters healthy. Storage adapter heavy reference count concentrated in test fixtures; production clean.

4. **Core-layer integrity:** Fully preserved. No downward reach from core in production code.
