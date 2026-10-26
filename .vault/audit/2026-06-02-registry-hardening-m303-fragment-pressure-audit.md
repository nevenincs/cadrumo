---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-10-03'
body_hash: 'sha256:6ad87da3f72e497bac10bb5702d6f0839a9f6c8a404b300fdbcb6a1c72e6a83a'
related:
  - '[[2026-06-02-registry-hardening-fragment-headroom-audit]]'
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
| 1536 | the retired data file |
| 1506 | the retired data file |
| 1296 | the retired data file |
| 1296 | the retired data file |
| 1239 | the retired data file |
| 1239 | the retired data file |
| 1039 | the retired data file |
| 627 | the retired data file |
| 190 | the retired data file |
| 190 | the retired data file |
| 27 | the retired data file |
| 19 | the retired data file |
| 10 | the retired data file |

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
| 1536 | 115 | the retired data file |
| 1506 | 113 | the retired data file |

The casilla pressure can be split at `[[revisions.<id>.casillas]]` boundaries.
That uses existing revision append-array behavior and does not need a new
schema construct.

### Export

| Lines | Layouts | Records | Fields | Path |
| ---: | ---: | ---: | ---: | --- |
| 1296 | 1 | 6 | 90 | the retired data file |
| 1296 | 1 | 6 | 90 | the retired data file |
| 1239 | 1 | 1 | 88 | the retired data file |
| 1239 | 1 | 1 | 88 | the retired data file |

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

- the historical check
  - Result: 2 passed in 10.28s.
- `uv run --no-sync python -c "from aeat.domain.calculations.registry import load_modelo_directory; from aeat.core.resources import bundled_path; m=load_modelo_directory(bundled_path('registry','aeat','modelos','303')); print(m.id, sorted(m.revisions)); print([(rid, len(rev.casillas), len(rev.export_layouts)) for rid, rev in sorted(m.revisions.items())])"`
  - Result: `303 ['2009-y-siguientes', '2023-y-siguientes']` and `[('2009-y-siguientes', 113, 1), ('2023-y-siguientes', 115, 1)]`.
