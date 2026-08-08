---
tags:
  - '#reference'
  - '#m200-export-envelope-tag'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:20118b22d5a064c1c9c1cf0fa2feb65102b8a9ae8633a2dfb1180790801be6df'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace m200-export-envelope-tag with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `m200-export-envelope-tag` reference: `M200 fichero-BOE envelope tag reconstruction grounding`

## What AEAT's own spec says (decisive, previously unread)

The bundled corpus does carry the page-000 diseño; a prior investigation missed
it because it looked only at `DP200001`/`DP200001B`. It is sheet `DP200000` in
`src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_200/files/16-200-ejercicio-2024-actualizado-13-10-2025-10-7-mb-xls.xls.extracted.md`
(vers. 1.04, "Impuesto sobre Sociedades... 2024"), lines 1-24:

- Row 1: offset 1, length 17, "Constante. `<T` + modelo + discriminante(\*) +
  Ejercicio devengo + periodo + tipo + `>`" — example content
  `"<T200020240A0000>"`. `(*)` note: discriminante is `"0"` Normal/Abreviado/PYMES,
  `"A"` Aseguradoras, `"E"` Entidades de crédito, `"I"` Inversión colectiva,
  `"G"` Garantía recíproca, "en función del estado de cuentas que se
  cumplimenta."
- Row 2: offset 18, length 5, literal `"<AUX>"`.
- Row 3: offset 23, length 70, reserved, blanks.
- Row 4: offset 93, length 4, "Versión del programa (\*\*)" — optional, filled by
  software vendors.
- Row 5: offset 97, length 4, reserved, blanks.
- Row 6: offset 101, length 9, "NIF Empresa Desarrollo (\*\*)" — optional.
- Row 7: offset 110, length 213, reserved, blanks.
- Row 8: offset 323, length 6, literal `"</AUX>"`.
- Row 12: offset 329, variable length, "Contenido del fichero" — the page
  records (page_001 through page_054, then DID).
- Row 13: offset `***` (i.e. immediately after all page content), length 18,
  "Constante. `</T` + modelo + discriminante + Ejercicio devengo + periodo +
  tipo + `>`" — example `"</T200020240A0000>"`.

Byte-for-byte decomposition of the row-1 example `"<T200020240A0000>"` (17
chars): `<T`(2) `200`(3) `0`(1, discriminante) `2024`(4, filing_year) `0A`(2,
period token) `0000>`(5, marker+close) = 2+3+1+4+2+5 = 17. This is the exact
same shape Modelo 111 already declares as six separate fields — see below —
with one extra one-character component (discriminante) inserted after the
modelo literal.

Row 13's example `"</T200020240A0000>"` (18 chars) is byte-identical to what
`application/filing/_export.py::_computed_field_value` already renders today
for the `computed_key = "envelope_closing_tag"` template:
`f"</T{draft.modelo}0{year}{period_code}0000>"` — note the hardcoded `"0"`
between `{draft.modelo}` and `{year}` is already the discriminante slot,
already defaulted to `"0"` (Normal/Abreviado/PYMES). **No code change is needed
to produce M200's closing tag** — only a new export record declaring the field
that invokes the existing computed key.

## Modelo 111's sibling composition, the working precedent

`src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0010-record-envelope-header.toml`
declares the open tag as six fields, all summing to offset 1-17: literal `<T`
(offset 1, len 2), literal `111` (offset 3, len 3), literal `0` (offset 6, len
1), draft `filing_year` (offset 7, len 4), draft `period_code` (offset 11, len
2), literal `0000>` (offset 13, len 5) — then literal `<AUX>` (offset 18, len
5), filler (offset 23, len 70), header `program_version` (offset 93, len 4),
filler (offset 97, len 4), header `presenter_nif` (offset 101, len 9), filler
(offset 110, len 213), literal `</AUX>` (offset 323, len 6). A separate record
`0030-record-envelope-footer.toml`, `record_type = "envelope_footer"`, `order =
2`, carries the single computed closing-tag field (offset 1, len 18,
`computed_key = "envelope_closing_tag"`).

M200's positions 18, 23, 93, 97, 101, 110, 323 match M111's byte-for-byte
(`<AUX>` at 18/len5, reserved at 23/len70, program_version at 93/len4, reserved
at 97/len4, presenter_nif/NIF-empresa-desarrollo at 101/len9, reserved at
110/len213, `</AUX>` at 323/len6). The layouts are the same envelope shape;
M200 simply inserts one extra byte (the discriminante) inside the open tag,
which pushes nothing else because M111's own offset-6 literal `"0"` occupies
that exact same position and width already — it happens to already have a
placeholder in the identical spot, just interpreted as a literal page marker
for M111 rather than a regime code for M200.

## What the current M200 registry declares (the defect)

`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`,
record `modelo-200-page-000`, `record_type = "page_000"`, `order = 0`:

- `modelo-200-page-000-draft-filing_year-pos-1`: offset 1, length 17, `kind =
  "draft"`, `draft_attribute = "filing_year"`. `_draft_value` (`_export.py:891`)
  resolves this to `str(draft.period.filing_year)` — 4 characters. `_pad`
  right-space-pads any `padding` value (including `"none"`, per its own
  in-code comment) to the declared length, so the emitted bytes are `"2024"`
  followed by 13 spaces — not truncated, not malformed at that slot, but
  entirely missing the `<T`, `"200"`, discriminante, period token and
  `"0000>"` marker AEAT's spec requires there.
- offset 18 (len 5, `<AUX>` position), offset 93 (len 4, program_version),
  offset 97 (len 4, reserved), offset 101 (len 9, NIF empresa desarrollo), all
  declared `kind = "filler"` — every one renders as spaces. The `<AUX>` and
  `</AUX>` literal markers AEAT requires are silently blank.
- **No record anywhere in the M200 export layout declares `record_type =
  "envelope_footer"` or a `computed_key = "envelope_closing_tag"` field.**
  Confirmed by grepping every `record_type =` declaration across all 78 files
  under `.../200/revisions/2024-y-siguientes/export/` — only `page_000` (order
  0) through `page_054` and `did` (order 76) exist. The closing tag AEAT's spec
  requires at the end of the fichero (row 13) has no declaration at all.

A real export (driven by the reporting agent) confirmed this at the byte
level: first 24 bytes `b'2024                    '`, last bytes of the fichero
blank where M111 renders `b'</T111020261T0000>'`.

## Severity conclusion

An envelope tag **is** required for M200 — AEAT's own diseño declares both the
open (row 1) and close (row 13) constants, matching the shape every other BOE
fichero modelo in this corpus uses (M111 confirmed; the pattern is standard
across AEAT's fixed-width ficheros). The current registry is **not** a
"slightly wrong width on a padded field" — it is missing the open tag's six
literal/draft sub-components (all but the bare year), the `<AUX>`/`</AUX>`
literal markers, and the entire closing tag record. Every Modelo 200
fichero-BOE this application has ever produced is structurally malformed
against AEAT's published diseño: it carries no open envelope tag, no `<AUX>`
markers, and no close envelope tag. This is the **larger** defect the dispatch
brief asked to weigh against the NIF misbinding, and it is larger: that defect
corrupted one 15-byte field's content; this one omits six required literal/tag
records across the entire file.

## The discriminante is a new, currently-unmodeled concept

No casilla, binding, or profile field for "estado de cuentas" / entity
regime-type (Normal/Abreviado/PYMES vs Aseguradoras vs Entidades de crédito vs
Inversión colectiva vs Garantía recíproca) exists anywhere in the domain model
today (confirmed: no `discriminante`, `estado_cuentas`, `entity_regime`, or
`accounts_regime` symbol in `src/cadrumo`, registry TOML, or the audit corpus
for the schema-hardening M200 sweep, which only ever built the Normal/PYMES
casilla set). `_computed_field_value`'s existing closing-tag template already
defaults this slot to literal `"0"` — the current application only supports
the Normal/Abreviado/PYMES regime, so `"0"` is the correct value for every
filer this application can currently produce a draft for, not an arbitrary
default.

## Draft-attribute canonical widths (current abstention)

`src/cadrumo/domain/calculations/registry/_validate_exports.py:67-103`,
`_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS`, keyed by `draft_attribute`:
`profile_tax_id` is gated at 9 (`SPANISH_TAX_ID_WIDTH`); `modelo` and `period`
abstain (`None`, no declaration anywhere to gate against); `filing_year`
abstains with an explicit comment naming this exact M200 divergence as the
reason; `period_code` abstains "because the token's width has not been
established against the published diseños." The `DP200000` sheet's row 1
establishes `periodo` at 2 characters (`"0A"` in the example), matching every
other `period_code` declaration corpus-wide (23 declarations, uniform at 2 per
the dispatch brief's measured distribution) — the abstention reason for
`period_code` no longer holds once this reference is read.

## `draft_attribute` and field-kind schema

`src/cadrumo/domain/calculations/registry/_schema_surfaces.py:695` types
`draft_attribute` as `Literal["modelo", "period", "profile_tax_id",
"filing_year", "period_code"]` — no change needed; the restructured page-000
record composes existing `draft`, `literal`, and `header` field kinds, all
already declared and validated (`_validate_field_kind`,
`_schema_surfaces.py:708-720`: `LITERAL` requires `literal`, `HEADER` requires
`header_key`, `COMPUTED` requires `computed_key`).

## Files to change

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`
  — restructure the open-tag field into the six-component composite, promote
  `<AUX>`/`</AUX>` to `literal`, promote `program_version`/NIF-empresa-desarrollo
  to `header`.
- A new export fragment declaring `record_type = "envelope_footer"`, `order =
  77` (immediately after `did`'s `order = 76`), one field: offset 1, length 18,
  `kind = "computed"`, `computed_key = "envelope_closing_tag"` — mirrors
  `0030-record-envelope-footer.toml` for M111 exactly.
- `src/cadrumo/domain/calculations/registry/_validate_exports.py` —
  `_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS["filing_year"]` moves from `None` to `4`
  once the sole divergent declaration is fixed; `["period_code"]` moves from
  `None` to `2` on the same evidence.
