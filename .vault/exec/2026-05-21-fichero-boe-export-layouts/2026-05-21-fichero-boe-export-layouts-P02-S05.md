---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S05'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P02.S05`

Audited the existing Modelo 130 export_layouts block against the corpus
Diseño de Registros DR 13001 and corrected the two divergences identified
in P01.S03: the missing offset-432 field and the wrong `data_type` on the
complementaria indicator at offset 12.

## Changes

### Fix 1: data_type boolean -> text for complementaria-indicator (offset 12)

File: `src/aeat/_data/registry/aeat/modelos/130.toml`

Field `modelo-130-complementaria-indicator` at offset 12 (length 1) had
`data_type = "boolean"`. The AEAT Diseño de Registros DR 13001 row 5
defines this field as type `A` (single alphabetic character, blank or `X`).
Boolean is not a valid data_type for a single-character `A` field. Changed
to `data_type = "text"` to match the DR.

Authority: DR 13001 row 5, sheet `DR 13001`, Orden HAP/258/2015 v1.2.

### Fix 2: Add missing offset-432 field (declaracion_complementaria)

File: `src/aeat/_data/registry/aeat/modelos/130.toml`

The DR 13001 row 31 defines a 1-byte `An` field at byte offset 432 labelled
"Declaracion complementaria" (blank or `X`). This is a distinct field from
the "Indicador de pagina complementaria" at offset 12. The existing export
layout jumped from casilla-19 (offset 415, length 17, ending at 431) to
`previous_receipt` at offset 433, leaving byte 432 unmapped.

Added:

```toml
[[revisions."2019-y-siguientes".export_layouts.records.fields]]
id = "modelo-130-declaracion-complementaria"
offset = 432
length = 1
kind = "header"
header_key = "declaracion_complementaria"
data_type = "text"
required = false
padding = "right_space"
justification = "left"
signed = false
```

The `previous_receipt` field at offset 433 was correct and unchanged;
the missing byte had not shifted it.

Authority: DR 13001 row 31, sheet `DR 13001`, Orden HAP/258/2015 v1.2.

## Verification

Registry snapshot loads without validation errors after both changes.
The full P02 test run passed (92 tests green; see S08 record).

Commit: `ae3b45ccc`
