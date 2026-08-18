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
