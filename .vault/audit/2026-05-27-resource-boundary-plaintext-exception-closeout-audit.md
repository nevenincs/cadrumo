---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-architecture-adr]]'
---

# Resource boundary plaintext-exception closeout audit

## Scope

This closeout covers W12.P26.S311, W12.P26.S312, and W12.P26.S313.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S311 | AFR-209 | `core.resources._boundary` | accepted bundled-read-only plaintext exception |
| W12.P26.S312 | AFR-210 | `core.resources._repos.legal_parameters` | accepted bundled-read-only plaintext exception |
| W12.P26.S313 | AFR-211 | `core.resources._repos.modelos` | hardened bundled-read-only plaintext exception |

## Findings

- `core.resources._boundary` is the single `importlib.resources` access point for bundled corpus and registry data. It materializes package resources read-only and does not write profile, session, ledger, modelo work-unit, or remote mirror state.
- `LegalParameterRepository` loads immutable bundled legal parameter catalogues through the registry loader and process-local identity-map caching. It does not create an alternate operator-data store.
- `StaticModeloRepository` now wraps only the expected registry snapshot miss as `ResourceNotFoundError`; registry load, validation, and backend failures are no longer collapsed by a broad catch.
- `core.test_resources` now tracks the current directory-mode Modelo 036 registry layout at `modelos/036/manifest.toml`.

## Validation

- `uv run ruff check src/aeat/core/resources/_boundary.py src/aeat/core/resources/_repos/legal_parameters.py src/aeat/core/resources/_repos/modelos.py src/aeat/core/test_resources.py src/aeat/core/resources/_repos/test_modelos.py src/aeat/core/resources/_repos/test_singletons.py src/aeat/core/resources/test_registry.py`
- `uv run pytest src/aeat/core/test_resources.py src/aeat/core/resources/_repos/test_modelos.py src/aeat/core/resources/_repos/test_singletons.py src/aeat/core/resources/test_registry.py -q`
