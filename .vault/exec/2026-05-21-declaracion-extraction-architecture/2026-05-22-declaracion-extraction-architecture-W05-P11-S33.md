---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S33'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# W05.P11.S33 - M303 real declaration round-trip

Completed a real round-trip parse test for Modelo 303 using the sanitized corpus fixture `src/aeat/tests/fixtures/justificantes/303/2024-1T.pdf`.

Changes:
- Added `modelo-303-declaracion-pdf` for registered, printed result-chain casillas `27`, `45`, `64`, `66`, and `71`.
- Added `test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy`.
- Extended declaración tax-id extraction to accept the AEAT `NIF Presentador: <NIF/NIE>` shape present in the real fixture.

Scope note: the fixture also prints result boxes `46`, `69`, `87`, and `110`, but those numeric IDs are absent from the current M303 casilla registry, so the profile does not target them.

Verification:
- `uv run --no-sync pytest -x src\aeat\adapters\inbound\declaracion\test_parser_boundary.py` -> 8 passed.
- `uv run --no-sync pytest -x src\aeat\domain\calculations\registry\test_committed_registry.py` -> 41 passed.
- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\_parser.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py` -> passed.
