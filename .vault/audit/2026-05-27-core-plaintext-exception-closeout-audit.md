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



# Core plaintext-exception closeout audit

## Scope

This closeout covers W12.P26.S299, W12.P26.S300, W12.P26.S309, and W12.P26.S310.

| Row | AFR | Module | Disposition |
| --- | --- | --- | --- |
| W12.P26.S299 | AFR-197 | `core.locks` | accepted plaintext exception with debug breadcrumbs |
| W12.P26.S300 | AFR-198 | `core.logging` | accepted plaintext diagnostic boundary |
| W12.P26.S309 | AFR-207 | `core.output_rendering` | hardened locale-backed exceptions |
| W12.P26.S310 | AFR-208 | `core.paths` | accepted containment helper boundary |

## Findings

- `core.locks` owns sidecar lock files and POSIX directory fsync best-effort durability. It does not store profile, session, modelo, ledger, or remote payload data. Non-fatal fsync and lock-release failures now log debug breadcrumbs instead of disappearing through suppression helpers.
- `core.logging` is the central log configuration and secret-scrubbing boundary. Runtime paths come from `Settings`, default log records are filtered for sensitive key/value pairs, and observability `run_event` records are not echoed to stderr.
- `core.output_rendering` now raises registered AEAT exceptions without raw English messages in `args`; operator output resolves through the central error registry and locale catalogue.
- `core.paths` is a validation-only containment helper. It raises `CoreValidationError`, rejects traversal and unsafe record tokens, and does not persist data.

## Validation

- `uv run ruff check src/aeat/core/output_rendering.py src/aeat/core/test_output_rendering.py src/aeat/core/locks.py src/aeat/core/test_logging.py src/aeat/core/test_paths.py`
- `uv run pytest src/aeat/core/test_output_rendering.py src/aeat/core/test_logging.py src/aeat/core/test_paths.py src/aeat/core/errors/test_registry.py src/aeat/entrypoints/cli/test_error_registry_contract.py -q`

## Residual Note

The broader `src/aeat/core/test_resources.py` run currently fails because the shared tree no longer contains `registry/aeat/modelos/036.toml`; the current layout has `registry/aeat/modelos/036/manifest.toml`. Resource rows W12.P26.S311-S313 remain open for that separate registry-layout reconciliation.
