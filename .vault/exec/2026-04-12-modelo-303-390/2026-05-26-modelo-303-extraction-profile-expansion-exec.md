---
step_id: "ad-hoc-2026-05-26"
tags:
  - "#exec"
  - "#modelo-303-extraction-profile"
date: 2026-05-26
modified: '2026-05-26'
related:
  - "[[2026-04-12-modelo-303-390-phase1-task1-exec]]"
---

# M303 declaracion_pdf extraction profile expansion: 10 → 12 named_label targets

## Summary

Expanded the M303 `declaracion_pdf` extraction profile coverage from 10 to 12
named_label targets by adding boxes 29 and 37 — both confirmed stable across all
8 corpus PDFs (2023-1T through 2024-4T).

## Discovery

Surveyed printed text from 8 corpus PDFs via pdfplumber for all IVA devengado
and IVA soportado rows. Tested every candidate label pattern against all 8
specimens before committing any addition.

## Slug → Box Mapping (additions)

| casilla_id | Form box | Printed label | Ground-truth value (all 8 PDFs) |
|---|---|---|---|
| `29` | 29 | "Por cuotas soportadas en operaciones interiores corrientes" | `Decimal("1000.00")` |
| `37` | 37 | "En adquisiciones intracomunitarias de bienes y servicios corrientes" | `Decimal("1000.00")` |

## Candidates skipped

| Box | Reason |
|---|---|
| 33 (importaciones corrientes cuota) | Unstable: only 2 of 8 PDFs have `1.000,00` as last token; others end with bare `33` |
| 11 (adquisiciones intracomunitarias cuota devengado) | Unstable: 5/8 have value, 3/8 end with bare `11` |
| 13 (inversión sujeto pasivo cuota) | Unstable: 4/8 have value, 4/8 end with bare `13` |
| 72 (compensación) | Ambiguous: pattern matches 2 lines |
| 77 (IVA aduana) | Value not adjacent to label; line ends with bare `77` |
| 76 (regularización art 80) | Value not adjacent to label; line ends with bare `76` |
| 59 (entregas intracomunitarias) | Value not adjacent to label; ends with bare `59` |

## Files changed

- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Test results

- 53/53 tests pass (`test_modelo_parity_coverage.py` + all `declaracion/` tests)
- All 26 modelos valid (parity coverage test)
- ruff: clean

## Commit

`1bf2a7e7f` — M303 extraction profile: expand coverage from 10 to 12 named_label targets
