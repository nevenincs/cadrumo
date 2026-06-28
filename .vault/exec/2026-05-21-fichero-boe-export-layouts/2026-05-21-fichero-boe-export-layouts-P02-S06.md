---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S06'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P02.S06`

Verified that `export_refs` are already present on all 19 Modelo 130 casilla
definitions in the current `2019-y-siguientes` revision of `130.toml`.

## Findings

An audit of `src/aeat/_data/registry/aeat/modelos/130.toml` confirms that
all 19 casillas (01 through 19) each carry an `export_refs` list naming the
corresponding `ExportFieldDefinition.id` in the export layout:

| Casilla | export_refs value |
|---------|-------------------|
| 01 | `["modelo-130-casilla-01"]` |
| 02 | `["modelo-130-casilla-02"]` |
| 03 | `["modelo-130-casilla-03"]` |
| 04 | `["modelo-130-casilla-04"]` |
| 05 | `["modelo-130-casilla-05"]` |
| 06 | `["modelo-130-casilla-06"]` |
| 07 | `["modelo-130-casilla-07"]` |
| 08 | `["modelo-130-casilla-08"]` |
| 09 | `["modelo-130-casilla-09"]` |
| 10 | `["modelo-130-casilla-10"]` |
| 11 | `["modelo-130-casilla-11"]` |
| 12 | `["modelo-130-casilla-12"]` |
| 13 | `["modelo-130-casilla-13"]` |
| 14 | `["modelo-130-casilla-14"]` |
| 15 | `["modelo-130-casilla-15"]` |
| 16 | `["modelo-130-casilla-16"]` |
| 17 | `["modelo-130-casilla-17"]` |
| 18 | `["modelo-130-casilla-18"]` |
| 19 | `["modelo-130-casilla-19"]` |

The `saldo-negativo-fin-periodo` virtual casilla (carry-forward helper) does
not have `export_refs` and correctly has none — it is not a wire field.

The plan task description noted "NO export_refs are present" based on the
P01.S03 audit of the *original* file state at the time of the campaign start.
The export_refs were added in a prior campaign step (visible in the current
file state). No code changes were needed for this step; the step closes as
already-complete.
