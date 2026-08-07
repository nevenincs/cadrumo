---
tags:
  - '#reference'
  - '#m200-export-nif-misbinding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b3a83c4c703f0bda17b8b88406145c2f81cafc621a89170ab12a8118943da6d4'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace m200-export-nif-misbinding with a kebab-case feature tag, e.g. #foo-bar.
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

# `m200-export-nif-misbinding` reference: `M200 grupo mercantil NIF export field misbinding`

Grounds a live filing-correctness defect found incidentally while sweeping
identifier byte-widths across the registry, not part of any active campaign.
Every source cited below was re-verified independently against the current
tree and against a freshly-fetched AEAT-published diseño de registro; nothing
here is taken on relay.

## Summary

### The two declarations at issue

`_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0002-modelo-200-page-001.part-001.toml`
lines 90-102 declares field `modelo-200-page-001-draft-profile_tax_id-pos-14`:
`offset = 14`, `length = 9`, `kind = "draft"`,
`draft_attribute = "profile_tax_id"`. This writes the filer's own NIF into
page 001 (`record_type` implied by file position 14) — **correct**.

`_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`
lines 168-180 declares field `modelo-200-page-001b-draft-profile_tax_id-pos-141`
inside record `modelo-200-page-001b` (`record_type = "page_001b"`, `order = 2`):
`offset = 141`, `length = 15`, `kind = "draft"`,
`draft_attribute = "profile_tax_id"`. The `draft_attribute` mechanism
(`_draft_value` in `application/filing/_export.py:891`) resolves
`profile_tax_id` to `draft.profile_tax_id` — the filer's own Spanish NIF —
regardless of which field or record binds it. So this field, too, writes the
filer's own NIF, right-padded from 9 to 15 characters.

### What AEAT's own spec says that byte range holds

Fetched fresh from AEAT's published URL
`https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR200e25.xls`
(a `.xls`, sheet `DP200001B`, "vers. 1.02", titled for "Impuesto sobre
Sociedades ... 2025" — the return for fiscal year 2024, matching the registry
revision `2024-y-siguientes`; no year-mismatch concern survives this check).
Row 4 headers: `Nº | Posic. | Lon | Tipo | Descripción`. The relevant rows on
sheet `DP200001B`:

| Nº | Posic. | Lon | Descripción |
|---|---|---|---|
| 6 | 13 | 7 | Grupo fiscal - Claves 00009-00010 - Nº de grupo fiscal [00040] |
| 7 | 20 | 9 | Grupo fiscal - Claves 00009-00010 - N.I.F. de la sociedad representante/dominante (incluida en el grupo fiscal) |
| 8 | 29 | 15 | Grupo fiscal - Clave 00010 - Nº identificación de la sociedad dominante (grupos constituidos solo por entidades dependientes) |
| 9 | 44 | 15 | Grupo mercantil - Datos de la sociedad matriz última: NIF |
| 10 | 59 | 40 | Grupo mercantil - Datos de la sociedad matriz última: Razón social |
| 11 | 99 | 40 | Grupo mercantil - Datos de la sociedad matriz última: Nombre de grupo |
| 12 | 139 | 2 | Grupo mercantil - Identificación fiscal del país de residencia - País de residencia |
| **13** | **141** | **15** | **Grupo mercantil - Identificación fiscal del país de residencia - NIF en el país de residencia (TIN)** |

Position 141, length 15 is AEAT's slot for the **mercantile group's ultimate
parent company's foreign tax identification number (TIN)**, in the parent's
country of residence — an entity, and a jurisdiction, that has nothing to do
with the filer's own Spanish NIF. `length = 15` is the byte width AEAT
declares for this field; it is correct. The `draft_attribute = "profile_tax_id"`
binding is what is wrong: it writes the filer's 9-character NIF, padded, into
a foreign-entity TIN slot AEAT defines for a different taxpayer.

`DP200001` row 11 (item 7), position 14 length 9, is confirmed
`"Identificación - NIF"` — the declarant's own NIF. That binding is correct.

### The adjacent grupo mercantil / grupo fiscal block is otherwise unwired

Every other field in the position 13-158 span above the mislabeled one is
declared `kind = "filler"` in the registry
(`modelo-200-page-001b-filler-pos-20`, `-29`, `-44`, `-59`, `-99`, `-139`, plus
the single `casilla` field at offset 13 length 7 mapped to casilla `00040`,
the group number). None of positions 20, 29, 44, 59, 99, or 139 — the fiscal
group's dominant-company NIF, the alternate dominant-company id, the
mercantile group's own parent NIF, parent razón social, group name, or
country-of-residence code — is wired to any binding, casilla, or draft
attribute. So for a taxpayer that IS part of a grupo mercantil or grupo
fiscal, the entire descriptive block ships blank except for the one
mislabeled field, which ships the filer's own NIF instead of the parent's
foreign TIN.

### The record renders unconditionally

`page_001b` (`record_type = "page_001b"`) is rendered by
`_render_layout` in `application/filing/_export.py:624-649`, which iterates
`layout.records` sorted by `order` and calls `did_page_suppressed(record,
headers=...)` (imported from `application/filing/_export_parity.py`) before
emitting each record. `_did_page_suppressed`
(`application/filing/_export_parity.py:82-103`) is scoped to exactly one
`record_type`:

```
if record.record_type != _DID_PAGE_RECORD_TYPE:  # "page_did"
    return False
```

`page_001b` is not `page_did`, so the predicate always returns `False` for it
— there is no disposition, group-membership, or any other condition under
which `page_001b` is skipped. Every Modelo 200 fichero-BOE export renders this
record, so every export carries the filer's own NIF in the ultimate-parent
foreign-TIN slot, whether or not the taxpayer belongs to any group.

### Nothing validates draft-attribute-to-slot semantics

Two structural validators run over export fields and neither checks meaning:

- `_record_field_ranges` (`domain/calculations/registry/_export.py:386-403`)
  only requires offset and length to be both-declared-or-neither, and returns
  `(start, end, field_id)` triples consumed by `_reject_overlapping_ranges`
  (`:406-412`), which only rejects overlapping byte ranges within one record.
- `ExportFieldDefinition._validate_field_kind`
  (`domain/calculations/registry/_schema_surfaces.py:707-722`) only checks that
  a declared `kind` carries its required companion field (`DRAFT` requires
  `draft_attribute` to be non-`None`, etc.) — it does not check that the
  `draft_attribute` chosen is the semantically correct one for that offset, or
  that its declared `length` matches the source's typed width.

So TOML authorship is the sole authority on both field width and slot
correctness; no gate cross-checks either against AEAT's published record
design. `SubjectTaxId` (the typed source `profile_tax_id` resolves) is always
9 characters — `draft_attribute = "profile_tax_id"` declared at `length = 15`
is itself a detectable anomaly independent of the AEAT cross-check.

### Corpus-wide width-anomaly sweep: this defect class is isolated to one field

`draft_attribute = "profile_tax_id"` is declared 28 times across the registry
(modelos 111, 115, 123, 130, 131, 180, 200, 202, 232, 303, 349, 390, across
their revisions). Every declaration was enumerated and its `offset`/`length`
extracted. **Exactly one** — `modelo-200-page-001b-draft-profile_tax_id-pos-141`
— declares `length = 15`; every other declaration (including M200's own
correct page-001 and page-DID bindings, both `length = 9`) declares
`length = 9`, matching `SubjectTaxId`'s fixed width. The width-anomaly method
that surfaced this defect is exhaustive for this one draft attribute across
the whole corpus: **no second occurrence of this specific defect (a
`profile_tax_id` binding at a non-9-length slot) exists anywhere else in the
registry.**

That sweep does not clear the broader defect *class* — a `draft_attribute`,
`casilla_id`, or `binding` bound to the semantically wrong slot at a
width-consistent length would not be caught by a width anomaly, and no
semantic cross-check against AEAT's published designs has ever been run for
any other field kind or draft attribute, on M200 or any other modelo. That
remains unswept.

### Prior governing ADR: completeness, not slot semantics

`.vault/adr/2026-07-01-fichero-boe-parity-gate-adr.md` (accepted) added a
pre-write `.boe` completeness gate: every casilla the completeness manifest
requires, applicable to a non-suppressed record, must reach disk
(`required_applicable ⊆ rendered`, one-directional). It is grounded in
`CalculationCompletenessManifest` and checks *presence*, not *correctness of
binding*. This defect passes that gate cleanly — the mislabeled field is
`kind = "draft"`, not a manifest-tracked casilla, and even if it were, the
gate only asserts a required casilla is *represented on disk*, never that the
value written to a given offset is the value AEAT's design says that offset
holds. A new gate closing this defect class extends the parity-gate lineage
rather than replacing it: same authority family (AEAT's published record
design), a different axis (per-field semantic correctness of the
`draft_attribute`/`casilla_id`/`binding` choice, not manifest coverage).

## Sources

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0002-modelo-200-page-001.part-001.toml`
- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0003-modelo-200-page-001b.toml`
- `src/cadrumo/application/filing/_export.py`
- `src/cadrumo/application/filing/_export_parity.py`
- `src/cadrumo/domain/calculations/registry/_export.py`
- `src/cadrumo/domain/calculations/registry/_schema_surfaces.py`
- AEAT `DR200e25.xls` ("Diseño de registro", Modelo 200, vers. 1.02, ejercicio
  2025), sheets `DP200001` and `DP200001B`, fetched from
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_200_299/archivos_25/DR200e25.xls`
  and parsed directly (`xlrd`) — the last-saved-by metadata and file content
  were read back after fetch, per the corpus-fetch caution in
  `aeat-calculation-grounding`.
- `.vault/adr/2026-07-01-fichero-boe-parity-gate-adr.md` (prior parity-gate
  authority, extended rather than duplicated by this work).
