---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-fragment-headroom-audit]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---

# M303 Fragment Pressure Audit

## Scope

This audit executes `P01.S09`: audit M303 casilla and export fragments near the
reviewability ceiling.

## Summary

M303 has no fragment above the 1750-line hard gate, but it has persistent
near-ceiling pressure:

- two casilla fragments above 1500 lines;
- four export fragments above 1200 lines;
- one revision file above 1000 lines.

The pressure is real, but it is currently lower than the residual M200 export
pressure. After P01.S08, the largest committed TOML fragment is still M200 page
043 at 1612 lines. M303 split follow-up is therefore tracked in `P05.S29`
instead of being executed immediately in P01.

## Fragment Inventory

| Lines | Path |
| ---: | --- |
| 1536 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.toml` |
| 1506 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.toml` |
| 1296 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.toml` |
| 1296 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.toml` |
| 1239 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0002-export-layout.toml` |
| 1239 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0002-export-layout.toml` |
| 1039 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml` |
| 627 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml` |
| 190 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0001-export-layout.toml` |
| 190 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0001-export-layout.toml` |
| 27 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml` |
| 19 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml` |
| 10 | `src/aeat/_data/registry/aeat/modelos/303/manifest.toml` |

## Threshold Counts

| Threshold | M303 TOML files at or above threshold |
| ---: | ---: |
| 1600 | 0 |
| 1500 | 2 |
| 1400 | 2 |
| 1300 | 2 |
| 1200 | 6 |
| 1000 | 7 |
| 750 | 7 |
| 600 | 8 |

M303 has 13 TOML files.

## Shape Analysis

### Casillas

| Lines | Casillas | Path |
| ---: | ---: | --- |
| 1536 | 115 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/casillas/0001-casillas.toml` |
| 1506 | 113 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/casillas/0001-casillas.toml` |

The casilla pressure can be split at `[[revisions.<id>.casillas]]` boundaries.
That uses existing revision append-array behavior and does not need a new
schema construct.

### Export

| Lines | Layouts | Records | Fields | Path |
| ---: | ---: | ---: | ---: | --- |
| 1296 | 1 | 6 | 90 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.toml` |
| 1296 | 1 | 6 | 90 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.toml` |
| 1239 | 1 | 1 | 88 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0002-export-layout.toml` |
| 1239 | 1 | 1 | 88 | `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0002-export-layout.toml` |

The export pressure can be split with existing export-layout fragment behavior:

- `0003-export-layout.toml` can split at record boundaries first, because it has
  six records.
- `0002-export-layout.toml` can split at `records.fields` boundaries, repeating
  the layout id and record id as in the M200 page-019 split.

## Tracking

The follow-up is now explicit in the plan:

- `P05.S28`: remaining M200 export pressure.
- `P05.S29`: M303 casilla/export pressure split.
- `P05.S30`: post-split corpus headroom re-audit.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 10.28s.
- `uv run --no-sync python -c "from aeat.domain.calculations.registry import load_modelo_directory; from aeat.core.resources import bundled_path; m=load_modelo_directory(bundled_path('registry','aeat','modelos','303')); print(m.id, sorted(m.revisions)); print([(rid, len(rev.casillas), len(rev.export_layouts)) for rid, rev in sorted(m.revisions.items())])"`
  - Result: `303 ['2009-y-siguientes', '2023-y-siguientes']` and `[('2009-y-siguientes', 113, 1), ('2023-y-siguientes', 115, 1)]`.
