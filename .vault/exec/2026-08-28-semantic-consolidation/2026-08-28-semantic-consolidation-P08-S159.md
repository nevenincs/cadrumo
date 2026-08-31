---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:85437e8a8bdcdc51d6833599c8ae4dd48bb19aa1c38fbb7653711b407f3ef705'
step_id: 'S159'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Align the raw Orden module coefficient with the seasonal sibling beside it and the runtime it compiles into, so a bad extraction refuses at the boundary that can name its source

## Scope

- `src/cadrumo/domain/calculations/registry/_m303_orden_raw_models.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/_m303_orden_raw_models.py`
- `verify:` raw module coefficient probed -- 0 refused on the coefficient field, 0.5 accepted
- `verify:` `pytest registry -k "m303_orden or orden_raw or orden_projection" -n 0 -m ""` -> pass (59)

## Notes

Completes the coefficient family. Four fields carried the same concept across
two layers and only one of the four said what was true:

| | raw extraction | runtime |
| --- | --- | --- |
| module coefficient | was `ge=0`, now `gt=0` | was `ge=0`, now `gt=0` |
| seasonal coefficient | `gt=0` already | was `ge=0`, now `gt=0` |

The seasonal raw field was right all along, which is what made the module field's
`ge=0` visible as an inconsistency rather than a convention -- two fields named
`coefficient` in one file with opposite zero-inclusion.

The siting is the point. This is the EXTRACTION boundary, whose whole job is
refusing a bad read of the BOE. A zero module coefficient used to pass here and
fail later at compile, which is past the point where the error can still name the
source line it came from -- the boundary that could have said "this row of the
Orden read wrong" instead handed a clean object to a stage that could only say
"a module coefficient is not positive".
