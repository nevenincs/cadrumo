---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S121'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-auth-gated-acquisition-status-audit]]'
---

# W05.P18.S121 - Modelo 190 2024 registry and parser verification

Implemented. The authenticated Sede listing found a Modelo 190 exercise-2024
row, but capture was blocked because the local registry had no 2024 snapshot.
Instead of pulling taxpayer-specific artifacts after the registry fix, this
slice used the existing sanitized 2024 fixture for parser verification.

Changes:

- Added `orden-hac-1432-2024:df-unica` to the IRPF legal catalogue, grounded
  in BOE `BOE-A-2024-26484`.
- Added `aeat-dr-190-2024` and `boe-modelo-190-2024-amendment` source refs.
- Added an observation-focused Modelo 190 revision `2024` with the three
  declarante summary fields, declaration-PDF extraction profile, read-only
  filed-declarations surface, workbook parity reference, and required
  application links.
- Adjusted the retenciones summary label pattern to match the actual 2024
  printed declaration text: `Importe total de las retenciones e ingresos a
  cuenta relacionados`.
- Added registry tests proving the 2024 revision resolves against 2024 legal
  and source authority and that the 2024 record-design PDF contains the
  registered summary field positions.
- Added the real sanitized Modelo 190 `2024-0A.pdf` parser round-trip test.

Validation:

- `uv run --no-sync ruff check src\aeat\_data\registry\aeat\modelos\190.toml src\aeat\domain\calculations\registry\test_modelo_190_registry.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py`
- `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\test_modelo_190_registry.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py`
- `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\test_committed_registry.py`
