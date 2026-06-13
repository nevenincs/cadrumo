---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S15'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S15`

Authored the Modelo 303 DP30303 page-03 segment record (1017 bytes).

## Structure

Record id: `modelo-303-page-03`, record_type: `page_03`, order: 3
Starts at byte offset 3615 (328+1581+1706).

38 fields covering DR DP30303 rows 1-38:
- Rows 1-4 (offsets 1-11): page opening tag `<T303 03000>`
- Rows 5-27 (offsets 12-440): informativo casillas 59, 60, 120, 122-124,
  62-63, 74-76 and resultado casillas 64-66, 77, 110 (domain), 78 (domain),
  87 (domain), 68, 69 (domain), 70, 109, 71 (all money/ratio, many SIGNED)
- Rows 28-31 (offsets 391-406): header flags: sin_actividad, autoliq_rectificativa,
  previous_receipt, tipo_rectificacion
- Rows 32-33 (offsets 407-440): rectificativa casillas 108, 111
- Row 34 (offsets 441-560): 120-byte reserved filler
- Rows 35-36 (offsets 561-562): motivo_rectificacion header flags
- Row 37 (offsets 563-1005): 443-byte reserved filler
- Row 38 (offsets 1006-1017): closing tag `</T30303000>`

Commit: `c744459f4`
