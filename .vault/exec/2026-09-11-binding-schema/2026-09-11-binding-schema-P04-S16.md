---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:6f5211a3ccd96ea6fde3cbae102c7635071c953f66ac617d9284400024aa1f7f'
step_id: 'S16'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---

# Run the edition-keyed identifier rename per modelo (232, 353, 360, 720, 123, 303) ahead of that modelo's provider-shape rewrite, collapsing byte-identical cross-edition pairs to one identifier, holding 100/2025 and 303/2025 until third-party edits are committed, and confirming the edition_keyed_identifier count drops per modelo

## Scope

- `dev/registry/rename_formula_binding_identifiers.py`
- `src/cadrumo/_data/registry/aeat/modelos/{232`
- `353`
- `360`
- `720`
- `123`
- `303}/revisions/*/bindings/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/{232`
- `353`
- `360`
- `720`
- `123`
- `303}/revisions/*/formulas/*.toml`

## Changes

- M `dev/registry/rename_formula_binding_identifiers.py`
- M `dev/registry/compiler/_loader_internals.py`
- M `src/cadrumo/domain/calculations/registry/schema.py`
- A `dev/registry/tests/test_rename_edition_year_collapse.py`
- A `dev/registry/tests/test_revision_family_source_defaults.py`
- M `dev/registry/tests/test_revision_manifest_only_placement.py`
- M `justfile`
- M `src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/{bindings,casillas}/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/720/revisions/2013-y-siguientes/{bindings,constructs}/*.toml`
- M `src/cadrumo/_data/registry/aeat/modelos/232/revisions/*/{revision.toml,bindings/*.toml,casillas/*.toml}`
- M `src/cadrumo/_data/registry/aeat/modelos/353/revisions/*/{revision.toml,bindings/*.toml}`

## Notes

The whole-revision-id rename was already applied in this checkout: the owning tool's
measurement pass reports zero formula and zero binding identifiers embedding their declaring
edition's key. This Step adds the second, modelo-anchored edition-year collapse rule, whose
year set is each edition's `valid_from` year plus every filing year its period selector
admits, and whose identity proof compares declaration bodies after lifting each edition's
shared source references. The lifting is carried by two new manifest-only revision fields,
`binding_source_refs` and `formula_source_refs`, mirroring `casilla_source_refs` on both the
manifest and the member side. The collapse was then applied one modelo at a time, each
verified through the directory loader before the next: 360 collapses 146, 720 collapses 43,
232 collapses 370 and lifts one binding source reference per edition, 353 collapses 166,
refuses 3 and lifts one per edition. Modelos 123 and 303 were left untouched: 123's two
year-keyed formulas collide with differently stated bare formulas, and 303 declares no
year-keyed identifier at all. The corpus `edition_keyed_identifier` count falls from 731 to
8, all of which are either the three refusals, 123's two, or the delta screen's weaker token
test reading an offset range or a period-selector segment as a year. The authority was not
republished and the plan Step is left open.

The collapse stranded the generated export trees of 232 and 353, which quote the renamed
binding ids and are generator-owned. That is a deadlock rather than a stale artifact: the
authority refuses to compile while a published tree names an undeclared binding, and every
generator entry point needs a compiling authority first. The export lane regenerated the four
trees, after which the authority compiles and no export field references an unknown binding.
The tool now refuses to apply when a published export tree quotes an id it would rename,
deriving the condition from the trees themselves rather than from the hand-kept roster that
named only modelo 390, and rewrites both quote styles so a single-quoted reference cannot be
left behind.
