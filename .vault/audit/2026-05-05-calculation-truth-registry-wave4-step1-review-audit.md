---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave4-step1-exec]]'
---



# `calculation-truth-registry` Code Review

MODELO-123-001 | RESOLVED | Historical revision represented

The current 2024-and-later Modelo 123 registry foundation verifies and has
behavior coverage for aggregation and export. The 2019-through-2023 official
layout is now represented as an explicit registry revision with behavior
coverage for revision selection, its eight-casilla aggregation shape, and its
own official export layout.

MODELO-123-002 | INFO | No live fixture available

The authenticated read-only declaration register scan returned zero Modelo 123
rows for 2020 through 2026. Live sanitized fixture and filed-data parser tests
cannot be completed from the scanned account today. The implementation correctly
does not fabricate a fixture or weaken parser expectations.

MODELO-123-003 | RESOLVED | Deadline applicability represented

Modelo 123 deadline windows are now gated by the first-class
`pays_capital_income_with_retencion` profile field. The deadline engine test
proves Modelo 123 is not applicable by default and becomes applicable only when
that profile condition is true.

MODELO-123-004 | RESOLVED | Runtime provider accepts multi-revision modelos

Adding the 2019-through-2023 revision exposed that the default filing schema
provider assumed single-revision modelos. The provider now selects the current
open-ended revision deterministically when no period is supplied, while
period-specific snapshot selection remains the path for historical filings.

MODELO-123-005 | RESOLVED | Historical export layout represented

The 2019-through-2023 Modelo 123 revision carries casillas, formulas,
extraction profiles, guard policy, workbook layout classification, verification
expectations, application links, and export layout records. The focused export
suite proves a period-specific 2023 snapshot writes and parses the historical
record design through the registry-backed export path.
