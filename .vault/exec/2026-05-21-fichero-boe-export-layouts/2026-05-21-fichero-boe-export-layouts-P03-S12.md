---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S12'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S12`

Authored the Modelo 303 DP30300 envelope-header segment record (328 bytes).

## Structure

Record id: `modelo-303-envelope-header`, record_type: `envelope_header`, order: 0

Fields grounded in DR DP30300 rows 1-13:
- Rows 1-3 (offsets 1-5): opening literals `<T` / `303` / `0`
- Row 4 (offsets 7-10): `filing_year` draft field (AAAA)
- Row 5 (offsets 11-12): `period_code` draft field (PP)
- Row 6 (offsets 13-17): literal `0000>`
- Row 7 (offsets 18-22): literal `<AUX>`
- Row 8 (offsets 23-92): 70-byte reserved filler
- Row 9 (offsets 93-96): `program_version` header field (4 bytes)
- Row 10 (offsets 97-100): 4-byte reserved filler
- Row 11 (offsets 101-109): `presenter_nif` header field (9 bytes)
- Row 12 (offsets 110-322): 213-byte reserved filler
- Row 13 (offsets 323-328): literal `</AUX>`

Verified at bytes 0-17 and 322-328 in the golden-SHA test output.

Commit: `c744459f4`
