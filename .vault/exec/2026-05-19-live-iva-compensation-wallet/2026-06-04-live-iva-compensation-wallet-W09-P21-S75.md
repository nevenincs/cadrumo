---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S75'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-06-03-live-iva-compensation-wallet-code-review-audit]]'
---

# W09.P21.S75 portal constants guard

Scope: Add static guard coverage that prevents portal route and host source-of-truth literals from returning outside centralized constants and schema surfaces.

## Description

- Added `test_portal_registry_modules_do_not_reintroduce_route_or_host_literals`.
- The guard scans non-test modules under `src/aeat/domain/portals`.
- It excludes module/class/function docstrings and the central host resolver helper.
- It fails on AEAT/Cl@ve host literals, `/Sede/`, `/wlpl/`, and root route literals in portal entry data modules.

## Verification

- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest -q src/aeat/core/test_external_constants.py::test_portal_registry_modules_do_not_reintroduce_route_or_host_literals src/aeat/core/test_external_constants.py::test_portal_paths_registry_covers_literal_free_portal_entries` passed with 2 tests.
- `PYTHONPATH=src .venv\Scripts\python.exe -m pytest -q src/aeat/domain/portals src/aeat/core/test_external_constants.py` passed with 129 tests.
- `PYTHONPATH=src .venv\Scripts\python.exe -m ruff check src/aeat/core/test_external_constants.py src/aeat/core/external_constants.py src/aeat/domain/portals src/aeat/entrypoints/cli/_app_live.py` passed.

## Notes

The broader test-suite literal classification remains open under WALLET-044/S88. No live AEAT request was made. No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.
