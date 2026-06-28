---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F06'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F06`

Centralised older live Sede/auth executable route fragments that were left as follow-up debt after the focused auth/wallet pass.

- Modified: `src/aeat/core/external_constants.toml`
- Modified: `src/aeat/core/external_constants.py`
- Modified: `src/aeat/core/test_external_constants.py`
- Modified: `src/aeat/adapters/outbound/aeat/verify/__init__.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_parse.py`

## Description

The CSV verifier now derives its read-guard host from the Sede origin in the external constants registry. The declarations register now checks post-navigation URL shape from the centralized declarations listing path. The expediente parser now derives cotejo CSV matching and IRPF detail year route matching from typed registry constants. A structural AST guard scans the live auth/Sede/wallet/CSV executable modules and refuses AEAT host, route, selector-access, or wallet literals outside docstrings.

No live AEAT operation was performed. The change only affects local constants, guards, and parser route matching on read-only surfaces.

## Tests

- `uv run pytest src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/test_verify.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestExtractCsvFromUrl src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestReadOperationGuard src/aeat/adapters/outbound/aeat/sede/test_iva_compensation_wallet.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py -q --disable-warnings` completed with 91 passed.
- `uv run pytest src/aeat/core/test_external_constants.py::test_live_sede_executable_route_literals_stay_centralized -q --disable-warnings` completed with 1 passed.
- `uv run ruff check src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/__init__.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_parse.py` passed.
- `git diff --check -- src/aeat/core/external_constants.toml src/aeat/core/external_constants.py src/aeat/core/test_external_constants.py src/aeat/adapters/outbound/aeat/verify/__init__.py src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/_parse.py` passed.
