---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S18'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S18`

Authored the Modelo 303 DP303DID identification segment record (823 bytes).

## Structure

Record id: `modelo-303-page-did`, record_type: `page_did`, order: 6
Starts at byte offset 7153 (328+1581+1706+1017+998+1523).

13 fields covering DR DP303DID rows 1-13:
- Rows 1-2 (offsets 1-2): literal `<T`
- Row 2 (offsets 3-5): literal `303`
- Row 3 (offsets 6-10): literal `DID00` — type An in DR (not Num)
- Row 4 (offset 11): literal `>`
- Row 5 (offsets 12-22): SWIFT-BIC (11 bytes, header, optional)
- Row 6 (offsets 23-56): IBAN (34 bytes, header, optional)
- Row 7 (offsets 57-126): bank name (70 bytes, header, optional)
- Row 8 (offsets 127-161): bank address (35 bytes, header, optional)
- Row 9 (offsets 162-191): city (30 bytes, header, optional)
- Row 10 (offsets 192-193): country code (2 bytes, header, optional)
- Row 11 (offset 194): SEPA marca (1 byte, header, optional)
- Row 12 (offsets 195-811): 617-byte reserved filler
- Row 13 (offsets 812-823): literal `</T303DID00>`

## DID00 An-type resolution

DR DP303DID row 3 declares type "An" for the page identifier field, not "Num".
This means the field holds the ASCII string "DID00", not a zero-padded integer.
Implemented as `kind="literal"` with `literal="DID00"` — confirmed at
bytes 7158-7162 in the golden-SHA test output.

Commit: `c744459f4`
