---
tags:
  - '#exec'
  - '#live-iva-compensation-wallet'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'W04.F07'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
  - '[[2026-05-20-live-iva-compensation-wallet-review-audit]]'
---

# `live-iva-compensation-wallet` `W04.F07`

Fixed the older Modelo 303 submitted-file extraction gap discovered during filed-history IVA compensation reconciliation.

- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`

## Description

The Modelo 303 submitted-file fallback now selects page-03 result casilla offsets by filing year. The 2022 official record design places casilla `71` at position 357, while the newer 2023+ design places it at position 374. The fallback now uses the 2022 position for 2022 declarations and keeps the existing default for later filings.

The regression test derives the 2022 casilla `71` position from the bundled official AEAT workbook and builds a redacted 2022-shaped record with a non-money marker at the newer position. This proves the parser is reading the official 2022 location without using private live captured values.

## Tests

- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py::test_modelo_303_2022_submitted_file_fallback_uses_2022_result_position src/aeat/adapters/outbound/aeat/sede/test_declarations.py::test_modelo_303_submitted_file_fallback_extracts_result_casillas src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileObservation -q --disable-warnings` completed with 9 passed.
- `uv run pytest src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileContext src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestSubmittedFileObservation src/aeat/adapters/outbound/aeat/sede/test_declarations.py::TestFiledObservationBindings -q --disable-warnings` completed with 15 passed.
- `uv run ruff check src/aeat/adapters/outbound/aeat/sede/_declarations.py src/aeat/adapters/outbound/aeat/sede/test_declarations.py` passed.
