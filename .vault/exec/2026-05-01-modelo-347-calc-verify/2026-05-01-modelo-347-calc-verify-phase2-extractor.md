---
tags:
  - '#exec'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-plan]]'
---

# `modelo-347-calc-verify` `implementation` `phase2-extractor`

Extended the declaration extractor to produce Modelo 347 summary casillas plus typed detail rows.

- Modified: `src/aeat/adapters/inbound/declaracion/_schema.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/modelo_347_v2025.py`
- Modified: `src/aeat/adapters/inbound/declaracion/_extractors/__init__.py`
- Modified: `src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py`

## Description

`DeclaracionFiling` now carries a default-empty `modelo_347_records` tuple. M347 has registered 2024, 2025, and 2026 extractors. The extractor keeps the existing four resumen casillas and parses typed per-counterparty detail rows from deterministic fixture rows plus a human-readable declaration-detail line shape.

## Tests

Round-trip tests cover 2024/2025/2026 detail extraction, registry presence, the existing resumen MVP path, and the human-readable detail-line parser.
