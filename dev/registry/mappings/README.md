# Semantic maps — authored record-design meaning

One TOML fragment set per (modelo, design epoch), consumed by
`dev.registry.pipeline._semantic_map_loader`. Every file is AUTHORED meaning
over the official record design: provenance header (`source_ref`,
`source_sha256`) plus hand-attributed entries with `legal_refs` and anchors.

## File schema

`NNNN-<fragment>.toml` — `NNNN` is the global ordinal (the load order);
`fragment_id` inside the file matches the filename stem.

## Fragment names mirror the official design

Fragment names are NOT a uniform vocabulary by design: they mirror the
official design's own structure, so the map stays auditable against the
source document:

- `records` — the design's record/table list.
- `paginaNN` — one page/sheet of the official layout.
- `dp303NN`, `dr232NN` — an AEAT-named subdocument sheet.
- `did` / `dp303did` — the identifying-header fragment, named after the
  official document it covers.
- `declarante`, `entidad`, `socio`, `declarado`, `inmueble` — official record
  names for models whose design names records rather than sheets.

A directory name that is not a plain year (modelo 303's `2024-early` /
`2024-late`) is a design EPOCH: AEAT published two designs inside 2024 and
each carries its own map.

## Three ways a field reaches its casilla

An entry attributes meaning to a design position, and there are three distinct
ways that meaning becomes a link from an emitted field back to a casilla. They
matter to a map author because the choice is made here, and to anyone measuring
coverage because a walk that knows only some of them under-reports.

- **Directly.** The field names its casilla, and the link is the field's own
  `casilla_id`.
- **Through a projection.** The field names a `projection_ref` instead, and the
  casilla is resolved from it. Repeated typed rows are served this way.
- **Through the record's row mapping.** The record maps a repeated row's field
  names to the casillas they carry. This link lives on the RECORD, not on any
  field, and after binding derivation the row's own field names the binding
  rather than the casilla — so on the resolved surface this mapping is the only
  path to those casillas.

A fourth shape is not a link but is easily mistaken for a missing one: an
official design may split one amount across an integer-part field and a
decimal-part field, both attributed to the same casilla. Two entries pointing at
one casilla is correct there, and the pair together carries the value.

## Measure through the resolved surface, never the authored fragments

Export fields are derived from bindings when a revision loads, so the authored
collection holds template and inline fields only. Any figure about what an export
carries must come from
`cadrumo.domain.calculations.registry.export.resolved_export_endpoints`, which
returns the surface whole with all three paths unioned.

This is not a style preference, and the declaration-hardening review produced
wrong figures in two distinct ways worth telling apart.

Rebuilding the surface by hand and dropping a path gave an export-reference
residue reported first as 384, then as 18, then as 0, each correction restoring
one linkage the walk had not known about. The accessor exists so that walk is
written once.

Reading the resolved surface but not what consumes it gave a monetary-scale
count of 3069 where the answer is 24. That walk used the accessor correctly; it
asked the declaration how a value is written when the codec scales the money
wire type itself and the official design splits some amounts across two fields.
Neither fact is visible in the declaration.

The general rule behind both: ask the thing that consumes the declaration, not
the declaration. Every one of those readings was plausible and each survived
until someone checked it against the renderer or the design.
