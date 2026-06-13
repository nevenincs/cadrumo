---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S19'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S19`

Authored the Modelo 303 page-closing trailer segment completing the
eight-segment envelope.

## Structure

Record id: `modelo-303-envelope-footer`, record_type: `envelope_footer`, order: 99
Starts at byte offset 7976 (328+1581+1706+1017+998+1523+823).

1 field:
- `modelo-303-envelope-closing-tag` (offset 1, length 18, kind=computed,
  computed_key=envelope_closing_tag)

The computed closing tag generates `</T3030{AAAA}{PP}0000>` dynamically at
export time using the model ID, filing year, and period code. For period 2025Q1
this produces `</T303020251T0000>`.

Confirmed at the last 18 bytes of the golden-SHA test output.

Commit: `c744459f4`
