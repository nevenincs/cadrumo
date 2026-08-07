---
tags:
  - '#research'
  - '#m200-grupo-mercantil-wiring'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:9da804e13ed7fe1c1199a382dd32f629df4b85e7389a8f30e3618867b9e05f06'
related:
  - "[[2026-08-07-m200-export-nif-misbinding-adr]]"
  - "[[2026-08-07-m200-export-nif-misbinding-plan]]"
  - "[[2026-08-07-m200-export-nif-misbinding-reference]]"
---

# `m200-grupo-mercantil-wiring` research: `unwired grupo mercantil block and the unswept slot-semantics class`

The M200 foreign-parent-TIN misbinding is closed: position 141 no longer writes
the declarant's own NIF, and a registry-build width check refuses that shape
being re-authored. Closing it left two things deliberately open, and this
document exists so neither becomes invisible. The first is the grupo mercantil
block itself, still unwired, which the fix converted from wrong data to an
honest absence rather than to correctness. The second is the broader class the
fix's own gate cannot see: a field bound to a semantically wrong slot at a
width the check accepts.

The second is no longer hypothetical. Measuring declared widths per draft
attribute across the whole registry -- the same method that surfaced the
original defect -- turned up a second live divergence in the same modelo, and
the width gate as shipped deliberately abstains over it. That is the finding
this document most needs a reader to act on.

## Findings

### A second live slot-semantics divergence: M200's envelope-open tag

`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`
declares field `modelo-200-page-000-draft-filing_year-pos-1` at `offset = 1`,
`length = 17`, `kind = "draft"`, `draft_attribute = "filing_year"`, on record
`modelo-200-page-000` (`record_type = "page_000"`, `order = 0`) -- the first
record emitted. `_draft_value` in
`src/cadrumo/application/filing/_export.py` resolves `filing_year` to
`str(draft.period.filing_year)`, four characters.

Driving the real export for a 2024 `0A` Modelo 200 draft through
`export_draft`, the payload's first 24 bytes are:

```
b'2024                    '
```

Seventeen bytes at position 1 is the width of the whole envelope-open tag, not
of a year. Modelo 111 composes exactly that width from seven fields in
`src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0010-record-envelope-header.toml`
-- literal `<T` at 1 (2), literal `111` at 3 (3), literal `0` at 6 (1), a
`filing_year` draft at 7 (4), a `period` draft at 11 (2), literal `0000>` at 13
(5) -- summing to 17. M200 collapses all of it into the single `filing_year`
binding, so the emitted record carries the year and thirteen spaces where the
tag belongs. The payload's last 24 bytes are blank as well, against Modelo
111's `b'</T111020261T0000>'` closing tag rendered from a `computed_key =
"envelope_closing_tag"` field; the M200 export layout declares no `literal`,
`computed`, or envelope field anywhere.

So M200's fichero-BOE appears to ship with neither an envelope-open nor an
envelope-close tag. This was not investigated further: whether AEAT's published
diseño for M200 requires the envelope at all, and what its exact expected
content is for this modelo, has to be read off the diseño before anything is
changed. Two outcomes are possible and they differ sharply -- either the tag is
required and every M200 fichero is structurally malformed, or M200 genuinely
has no envelope and the 17-byte `filing_year` binding is a mis-transcription of
some other 17-byte field. Both need the diseño, and the second is not
obviously less serious than the first.

### Why the shipped width gate does not catch it

The gate rules per draft attribute in
`_DRAFT_ATTRIBUTE_CANONICAL_WIDTHS`
(`src/cadrumo/domain/calculations/registry/_validate_exports.py`), and it
abstains on `filing_year`. The abstention is deliberate and is recorded at the
mapping, but it is worth stating plainly what it costs: gating `filing_year` at
4 would catch the divergence above at registry-build time, and the only reason
it is not gated is that doing so refuses the registry build until the page-000
declaration is restructured -- work needing its own decision and its own
byte-level verification of the emitted tag, which the closing change was not
scoped to perform.

Measured width distribution across every `draft_attribute` declaration in the
registry, by parsing each field block for its `length`:

| attribute | declared widths |
|---|---|
| `profile_tax_id` | 9 (26 declarations, no exceptions) |
| `filing_year` | 4 (32 declarations), 17 (1 declaration -- the one above) |
| `period_code` | 2 (23 declarations, no exceptions) |
| `modelo` | no declarations |
| `period` | no declarations |

Two consequences. `profile_tax_id` is now clean corpus-wide, which confirms the
original defect was the only instance of that specific shape. And
`period_code` is uniform, so it is gateable on the evidence available; it
abstains only because a period token is a plausible axis for a per-period-kind
width difference and that has not been checked against the diseños.

### The grupo mercantil block remains unwired, and blank is not correct

Positions 20, 29, 44, 59, 99, and 139 of M200 page 001B stay `kind = "filler"`,
and position 141 joins them. Per the record design those are the fiscal
group's dominant-company NIF, the alternate dominant-company identifier, the
mercantile group's ultimate parent NIF, that parent's razón social, the group
name, and the parent's country-of-residence code. A taxpayer that is part of a
grupo mercantil or grupo fiscal now ships the entire descriptive block blank.

What the standing goal still asks for that the closing change excludes: a
correct M200 filing for a group member. The change traded affirmatively-wrong
data for an honest absence, which is an improvement and not correctness. No
domain concept for group membership or ultimate-parent identity exists -- no
casilla, binding, or profile fact -- so nothing in the model can supply those
positions today.

Wiring it needs, in order: confirmation from AEAT's casilla catalogue whether
these positions carry casilla numbers at all (the diseño excerpt in the
reference shows no bracketed code on positions 20, 29, 44, 59, 99, 139, or 141,
which suggests export-only fields with no calculation-engine counterpart, and
that would change the shape of the wiring); a domain concept for grupo
mercantil membership and parent-company identity; and only then the bindings.
The parent's foreign TIN also cannot reuse the declarant identifier type --
`SubjectTaxId` enforces the Spanish NIF checksum and a foreign TIN will not
satisfy it, so a distinct type is required.

### A residual naming lie left in place deliberately

Field `modelo-200-page-001b-draft-profile_tax_id-pos-141` is now a filler, so
its id names a binding it no longer carries, against sibling fillers named
`modelo-200-page-001b-filler-pos-N`. The id was kept because the governing ADR
constrains the fix to the existing field id and the id is referenced nowhere
else in the tree; renaming it would have been unsanctioned scope. It should be
renamed when the block is wired, and the gate does not depend on it -- the
width check keys on the `draft_attribute`, not on the id, so the stale name
cannot make it misfire.

### What was not investigated

The semantic sweep the closing ADR opened is still not performed. Width
divergence is the only method applied here, and it is a weak proxy: it finds a
binding whose slot is the wrong SIZE and is blind to a binding whose slot is
the right size and the wrong MEANING. Nothing has cross-checked any
`casilla_id` or `binding` export field, on M200 or any other modelo, against
AEAT's published diseño descriptions. The heavier gate the ADR recorded as a
pathway -- parsing each modelo's diseño and diffing every field's
offset, length, and description against the registry -- remains the only
method that would actually close the class, and it needs a bundled diseño
corpus that does not exist yet.

## Sources

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0001-modelo-200-page-000.toml`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`
- `src/cadrumo/_data/registry/aeat/modelos/111/revisions/2019-y-siguientes/export/0010-record-envelope-header.toml`
- `src/cadrumo/application/filing/_export.py`
- `src/cadrumo/domain/calculations/registry/_validate_exports.py`
- `src/cadrumo/core/identity/_tax_id.py`
- AEAT `DR200e25.xls` ("Diseño de registro", Modelo 200, vers. 1.02, ejercicio
  2025), sheets `DP200001` and `DP200001B`, at
  https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR200e25.xls
  -- the position-141 description is quoted in the reference document and was
  not re-fetched here. The envelope-tag question above is NOT answered by the
  sheets already read; it needs `DP200000` or whatever sheet governs the
  page-000 record.
