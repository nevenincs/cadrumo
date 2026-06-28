---
tags:
  - '#audit'
  - '#registry-construct-pressure'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-registry-construct-pressure-plan]]'
---

# `registry-construct-pressure` audit: `Post-split registry fragment headroom`

## Scope

Re-measure every TOML file under `src/aeat/_data/registry/aeat/modelos` after
the M200 construct split landed.

## Findings

- PASS: No registry TOML file is over 1,500 lines.
- PASS: No registry TOML row is over 600 characters.
- PASS: The M200 2024-and-later records directory now tops out at 900 lines:
  `constructs.part-001.toml` and `constructs.part-001b.toml`.
- PASS: The new M200 construct split files are below the pressure band:
  `constructs.part-002b.toml` is 753 lines and `constructs.part-002a.toml` is
  716 lines.
- OBSERVED: One TOML file remains above the 1,200-line soft review band:
  `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
  at 1,218 lines.
- OBSERVED: The largest row is 572 characters in
  `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/casillas/0618-0552.toml`.

## Largest files

- 1,218 lines:
  `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
- 1,039 lines:
  `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- 969 lines:
  `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/export/0003-export-layout.part-001.toml`
- 969 lines:
  `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/export/0003-export-layout.part-001.toml`
- 954 lines:
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0010-modelo-200-page-007.toml`

## Recommendations

- Close the M200 construct-pressure slice; the intended hard-cap pressure is
  removed.
- Track `M123` as the next soft-band follow-up only if the project treats 1,200
  lines as a hard enforcement threshold rather than a review signal.
- Keep the registry reviewability tests as the primary guard against future
  file-size and row-width creep.

## Codification candidates

No new codification candidate. File-size and row-width gates are already
represented by registry reviewability tests and the active fragment architecture
ADR.
