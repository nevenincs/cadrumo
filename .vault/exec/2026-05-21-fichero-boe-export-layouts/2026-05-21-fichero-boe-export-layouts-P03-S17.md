---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S17'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S17`

Authored the Modelo 303 DP30305 page-05 segment record (1523 bytes).

## Structure

Record id: `modelo-303-page-05`, record_type: `page_05`, order: 5
Starts at byte offset 5630 (328+1581+1706+1017+998).

8 fields covering DR DP30305 rows 1-72:
- Rows 1-4 (offsets 1-11): page opening tag `<T303 05000>`
- Row 5 (offset 12): complementaria header flag
- Rows 6-70 (offsets 13-839): prorrata fields (casillas 500-524) and
  regularización deducción diferenciada (casillas 700-735) as 827-byte filler;
  these high-numbered casillas are not defined in this revision
- Row 71 (offsets 840-1511): 672-byte reserved filler
- Row 72 (offsets 1512-1523): closing tag `</T30305000>`

Commit: `c744459f4`
