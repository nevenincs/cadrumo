---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P16.S100'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-26-declaracion-extraction-architecture-w05-p16-backlog-expansion-exec]]'
---

# W05.P16.S100 - Modelo 303 printed boxes 46, 69, 87, and 110

Closed the decision and implemented the extraction-profile expansion.

## Decision

Do not create duplicate numeric casilla IDs for Modelo 303 printed boxes
46, 69, 87, and 110. They already exist as source-grounded canonical
registry casillas:

- `iva.resultado-regimen-general` carries `form_number = "46"` and
  `export_refs = ["modelo-303-page-01-casilla-46"]`.
- `iva.resultado` carries `number = "69"` and
  `export_refs = ["modelo-303-page-03-casilla-69"]`.
- `iva.compensacion-pendiente-periodos-posteriores` carries
  `number = "87"` and
  `export_refs = ["modelo-303-page-03-casilla-87"]`.
- `iva.compensacion-pendiente-periodos-anteriores` carries
  `number = "110"` and
  `export_refs = ["modelo-303-page-03-casilla-110"]`.

The safe expansion is to target those canonical IDs through
`match_strategy = "named_label"` using the real declaration PDF text,
not to add numeric aliases as separate casillas.

## Implementation

Expanded `modelo-303-declaracion-pdf` to extract:

- `iva.resultado-regimen-general`
- `iva.compensacion-pendiente-periodos-anteriores`
- `iva.compensacion-pendiente-periodos-posteriores`
- `iva.resultado`

The shared inbound PDF `ExtractedCasilla.casilla_id` boundary was widened
from 32 to 128 characters because valid registry semantic IDs exceed the
old adapter-local limit. A focused test now proves that a real registry
semantic identifier is accepted.

## Verification

`uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\adapters\inbound\pdf\_shared.py src\aeat\adapters\inbound\pdf\test_shared.py` passed.

`uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\adapters\inbound\pdf\test_shared.py -q` passed with 21 tests.

`uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_303_registry.py -q` passed with 57 tests.
