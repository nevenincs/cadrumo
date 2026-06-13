---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S02'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P01.S02`

Studied the canonical registry-TOML fichero-BOE export layouts for
modelos 180, 202, and 232, capturing the record/field/encoding/grammar
that P02 and P03 must follow.

## Description

### Directory and file structure

Each revision directory that ships a fichero-BOE export carries an
`export_layouts/` subdirectory containing multiple TOML files that are
all merged at load time into the same `export_layouts` array for the
revision. The split is organisational (one file per record segment) and
not semantic. The layout itself is declared as a flat TOML array with a
single top-level `export_layouts` entry that has `id`, `legal_refs`, and
`source_refs`, followed by `export_layouts.records` and
`export_layouts.records.fields` arrays.

For flat-file modelos (`130.toml`, `303.toml`) the full export layout
lives inside the single `.toml` file rather than a subdirectory.

### Envelope/page/footer structure

Every multi-page AEAT fichero-BOE follows a three-level structure:

- **Envelope header** (`record_type = "envelope_header"`, `order = 0`):
  Opens the transmission. Fixed 328-byte AUX block:
  - Offset 1–2: literal `<T` (2)
  - Offset 3–5: literal modelo number e.g. `202` (3)
  - Offset 6: discriminante literal `0` (1)
  - Offset 7–10: filing year AAAA (4, `kind = "draft"`, `draft_attribute = "filing_year"`)
  - Offset 11–12: period code PP (2, `kind = "draft"`, `draft_attribute = "period_code"`)
  - Offset 13–17: literal `0000>` (5)
  - Offset 18–22: literal `<AUX>` (5)
  - Offset 23–92: AEAT reserved, spaces (70, `kind = "filler"`)
  - Offset 93–96: program version (4, `kind = "header"`, `header_key = "program_version"`)
  - Offset 97–100: AEAT reserved, spaces (4, `kind = "filler"`)
  - Offset 101–109: presenter NIF (9, `kind = "header"`, `header_key = "presenter_nif"`)
  - Offset 110–322: AEAT reserved, spaces (213, `kind = "filler"`)
  - Offset 323–328: literal `</AUX>` (6)
  Total envelope header: 328 bytes before page content.

- **Page records** (`record_type = "page_01"` etc., `order = 1, 2, …`):
  Each page record starts with an open-tag block:
  - Offset 1–2: literal `<T` (2)
  - Offset 3–5: literal modelo number (3)
  - Offset 6–7 (or 6–10): page identifier literal e.g. `01` for simple
    forms or `01000` for M303-style (length 2 or 5 depending on DR)
  - Then `000>` or `>` closing the tag
  - Then identification/header fields (complementaria indicator, NIF,
    surnames, name, filing year, period code)
  - Then casilla fields: `kind = "casilla"`, `casilla = "NN"`,
    `data_type = "money"`, `padding = "left_zero"`,
    `justification = "right"`, `signed = true/false` as per DR
  - Then header/draft fields for supplementary data
  - Then AEAT reserved filler
  - Then a seal filler (13 bytes)
  - Closing literal tag e.g. `</T13001000>` or `</T30301000>`

- **Envelope footer** (`record_type = "envelope_footer"`, `order = 99`
  or highest):
  Single computed field: `kind = "computed"`,
  `computed_key = "envelope_closing_tag"`, length 18.
  This produces the dynamic closing tag `</T{modelo}{discriminante}{AAAA}{PP}0000>`.

### Field schema

Every `ExportFieldDefinition` carries:

| Key | Type | Notes |
|-----|------|-------|
| `id` | str | Unique within the layout. Naming pattern: `{modelo}-{record-slug}-{description-slug}[-pos-{offset}]` |
| `offset` | int | 1-based byte offset within the record |
| `length` | int | Byte count |
| `kind` | enum | `literal`, `casilla`, `filler`, `draft`, `header`, `computed` |
| `literal` | str | Required when `kind = "literal"` |
| `casilla` | str | Required when `kind = "casilla"` — the casilla id (e.g. `"01"`) |
| `draft_attribute` | str | Required when `kind = "draft"` — e.g. `"filing_year"`, `"period_code"`, `"profile_tax_id"` |
| `header_key` | str | Required when `kind = "header"` — e.g. `"surnames"`, `"name"`, `"iban"`, `"previous_receipt"` |
| `computed_key` | str | Required when `kind = "computed"` — e.g. `"envelope_closing_tag"` |
| `data_type` | enum | `text`, `money`, `integer`, `date` |
| `required` | bool | `true` for literals and casilla fields; `false` for fillers |
| `padding` | enum | `left_zero` (numeric right-justified), `right_space` (text left-justified), `none` |
| `justification` | enum | `right` (numeric), `left` (text), `none` (literals/computed) |
| `signed` | bool | `true` for money fields that can be negative (N-type in DR); `false` otherwise |
| `date_format` | str | Present only when `data_type = "date"`, e.g. `"ddmmaaaa"` |
| `legal_refs` | list | Inherited from the ExportLayoutDefinition |
| `source_refs` | list | Inherited from the ExportLayoutDefinition |

### Encoding and line ending

All observed modelos use `encoding = "latin-1"` (ISO-8859-1). No
ISO-8859-15 is used in the wire format. The original ADR section 4
confirmed this. All records use `line_ending = "none"` — the page
records are concatenated without inter-record delimiters; the envelope
provides framing through the tag literals.

### Casilla-field wire encoding conventions (from DR notes)

- **An (alphanumeric)**: left-justified, right-padded with spaces.
  `padding = "right_space"`, `justification = "left"`.
- **Num (numeric)**: right-justified, left-padded with zeros. No sign.
  `padding = "left_zero"`, `justification = "right"`, `signed = false`.
- **N (numeric with sign)**: right-justified, left-padded with zeros.
  Negative values have `N` in the first position of the field.
  `padding = "left_zero"`, `justification = "right"`, `signed = true`.
- **A (alphabetic flag)**: single character, no padding needed.
  `padding = "none"`, `justification = "none"`.
- Money fields always use 17-byte slots (15 integer + 2 decimal,
  implicit — no decimal separator in the wire bytes). Money amounts
  are multiplied by 100 and zero-padded to 15 digits.
- Rate/percentage fields use 5-byte slots (3 integer + 2 decimal,
  implicit).

### export_refs wiring on casillas

Each `CasillaDefinition` that participates in an export layout carries
an `export_refs` list. Each element names the `ExportFieldDefinition.id`
that the casilla maps to, e.g. `export_refs = ["dp30301.casilla_03"]`.
This is the casilla→field binding that the serialiser follows to place
the casilla value at the correct byte offset.

## Tests

No production code was changed. This is a discovery and documentation
step. The template description above is the authoritative reference for
P02 (M130) and P03 (M303) layout authoring.
