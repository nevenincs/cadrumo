---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P26.S161'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W07.P26.S161

Surveyed M111 and M130 corpus PDF text layouts via pdfplumber; confirmed that the `numeric_casilla` profile strategy (box number at line start) cannot match either modelo's real AEAT PDF form layout.

## Findings

**M111 corpus (4 PDFs, 2024-1T..4T)**

- Box numbers appear at the END of multi-column label rows, not at line start.
- Example: `Rendimientos dinerarios ... 07 1 08 1.000,00 09 1.000,00` — the box number is embedded inside a table row.
- Exception: closure casillas 28 and 30 appear on dedicated totals lines where the label text and box number+value co-appear:
  - `Suma de retenciones e ingresos a cuenta ( 03 + ... 27 ) .... 28 1.000,00`
  - `Resultado a ingresar ( 28 – 29 ) .... 30 1.000,00`
- In 2024-4T (negative/zero filing), box 28 line ends with just `28` (no value), box 30 still shows `1.000,00`.

**M130 corpus (15 PDFs, 2021-2T..2024-4T)**

- All box numbers appear at END of label lines (e.g. `...Ingresos computables ... 01`).
- Actual monetary values are printed as a detached block of standalone `1.000,00` lines at the bottom of page 2, with no adjacent labels.
- Neither `numeric_casilla` NOR `named_label` can extract M130 corpus casilla values; the layout is positional, not label-anchored.

**Named-label candidates for M111**

- `28`: label_pattern `Suma\s+de\s+retenciones\s+e\s+ingresos\s+a\s+cuenta`
- `30`: label_pattern `Resultado\s+a\s+ingresar\s+\(\s*28\s*.+?29\s*\)`

Both candidates verified to extract `Decimal('1000.00')` in 2024-1T/2T/3T and valid Decimal in 2024-4T.
