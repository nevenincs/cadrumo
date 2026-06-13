---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S13'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S13`

Authored the Modelo 303 DP30301 page-01 segment record (1581 bytes).

## Structure

Record id: `modelo-303-page-01`, record_type: `page_01`, order: 1
Starts at byte offset 328 (after DP30300).

88 fields covering DR DP30301 rows 1-88:
- Rows 1-4 (offsets 1-11): page opening tag `<T303 01000>`
- Rows 5-24 (offsets 12-129): identification flags (complementaria, tipo declaracion,
  NIF, surnames, ejercicio, periodo, tributacion foral, REDEME, etc.)
- Rows 25-33 (offsets 130-247): new 2024 casillas 150-152 (0% tier), 153-155 (0.5%/0.75% tier)
- Rows 34-36 (offsets 247-285): casillas 04-06 (reducido 10%)
- Rows 37-39 (offsets 286-324): casillas 07-09 (general 21%)
- Rows 40-41 (offsets 325-358): casillas 10-11 (intracomunitarias)
- Rows 42-43 (offsets 359-392): casillas 12-13 (ISP excl. intracom)
- Rows 44-45 (offsets 393-426): casillas 14-15 (modificaciones, SIGNED)
- Rows 46-54 (offsets 427-583): recargo equivalencia casillas 156-26
- Rows 55-60 (offsets 583-633): casillas 25-27 (mod bases recargo + total cuota devengada)
- Rows 61-78 (offsets 634-939): IVA deducible casillas 28-45
- Row 79 (offset 940-956): casilla 46 resultado regimen general (SIGNED, domain casilla)
- Rows 80-85 (offsets 957-1034): new 2024 casillas 165-170
- Row 86 (offsets 1035-1556): 522-byte reserved filler
- Row 87 (offsets 1557-1569): 13-byte AEAT seal filler
- Row 88 (offsets 1570-1581): closing tag `</T30301000>`

Commit: `c744459f4`
