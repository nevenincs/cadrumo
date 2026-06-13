---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 Current Registry Foundation Step

## Scope

- Add the current Modelo 131 registry foundation for 2026.
- Ground formulas in AEAT instructions and RD 439/2007 article 110.
- Keep historical 2019-2023, 2024, and 2025 revision authoring pending until
  explicitly represented in the registry file.

## Changes

- Added `registry/aeat/modelos/131.toml` with Modelo 131 identity and current
  2026 revision.
- Added the 15-casilla liquidacion block for the current revision.
- Added formulas for casillas 04, 06, 07, 10, 13, and 15.
- Added submitted-file and declaration-PDF extraction profiles for the current
  revision.
- Added source-backed verification expectation, static portal guard, workbook
  parity reference, and application links.

## Verification

- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_catalogue_verification.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
