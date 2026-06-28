---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S16'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S16`

Authored the Modelo 303 DP30304 page-04 segment record (998 bytes).

## Structure

Record id: `modelo-303-page-04`, record_type: `page_04`, order: 4
Starts at byte offset 4632 (328+1581+1706+1017).

10 fields covering DR DP30304 rows 1-43:
- Rows 1-4 (offsets 1-11): page opening tag `<T303 04000>`
- Row 5 (offset 12): complementaria header flag
- Rows 6-22 (offsets 13-55): activity codes and IAE epigraphs (43-byte filler)
- Rows 19-23 (offsets 56-80): territorial percentages 89-92/107 (25-byte filler)
- Rows 24-41 (offsets 81-369): annual operation totals 80/81/93/94/... (289-byte filler)
- Row 42 (offsets 387-986): 600-byte reserved filler
- Row 43 (offsets 987-998): closing tag `</T30304000>`

Page 04 is only populated by subjects exempt from modelo 390 in the last period.
High-numbered casillas (79-128) are serialised as fillers; they are not defined
in this revision's casilla set.

Commit: `c744459f4`
