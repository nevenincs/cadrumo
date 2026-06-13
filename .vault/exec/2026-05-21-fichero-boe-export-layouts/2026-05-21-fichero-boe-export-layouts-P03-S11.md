---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S11'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S11`

Wired `export_refs` onto the Modelo 303 casillas so each casilla binds to its
fichero-BOE record field.

## Coverage

89 casillas now carry `export_refs` in 303.toml:

- 5 pre-existing domain casillas: `iva.resultado-regimen-general` (→ casilla-46),
  `iva.compensacion-pendiente-periodos-anteriores` (→ casilla-110),
  `iva.compensacion-aplicada-periodo` (→ casilla-78),
  `iva.compensacion-pendiente-periodos-posteriores` (→ casilla-87),
  `iva.resultado` (→ casilla-69).
- 84 new numbered casillas: all non-literal fields (tipo-% constants are
  `kind="literal"` in the export layout and do not need `export_refs`).

## Legal catalogue additions

Added to `src/aeat/_data/registry/aeat/legal/iva.toml`:
- `ley-37-1992:art-94` (deducibilidad conditions)
- `ley-37-1992:art-95` (limitaciones derecho deducir)
- `ley-37-1992:art-122` (régimen simplificado)
- `ley-37-1992:art-123` (contenido RS)
- `ley-37-1992:art-124` (obligaciones formales RS)

Corpus HTML stubs created at `src/aeat/_data/corpus/normatives/html/` for each.

Added `export` application link to the `2009-y-siguientes` revision.

Commit: `c744459f4`
