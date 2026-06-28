---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S14'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S14`

Authored the Modelo 303 DP30302 page-02 segment record (1706 bytes).

## Structure

Record id: `modelo-303-page-02`, record_type: `page_02`, order: 2
Starts at byte offset 1909 (328+1581).

20 fields covering DR DP30302 rows 1-91:
- Rows 1-4 (offsets 1-11): page opening tag `<T303 02000>`
- Row 5 (offset 12): complementaria flag header field
- Rows 6-77 (offsets 13-900): per-activity rows serialised as 888-byte filler
  (RS activity fields require per-activity-row bindings not in scope)
- Rows 78-89 (offsets 901-1104): result casillas 47-58 (money, some SIGNED)
- Row 90 (offsets 1105-1694): 590-byte reserved filler
- Row 91 (offsets 1695-1706): closing tag `</T30302000>`

## DP30302 descriptions resolution

The 2024 XLSX has all "C" in the description column for DP30302.
Descriptions recovered from the 2022 XLSX edition which contains full
RS per-activity field labels.

Commit: `c744459f4`
