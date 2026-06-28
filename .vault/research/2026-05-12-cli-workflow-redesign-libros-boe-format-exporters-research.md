---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `libros-boe-format-exporters`

## Findings

The project has BOE fixed-width export substrate for filing exports and modelos
declare `export_layouts`, but libro-registro exporters are missing for facturas
emitidas, facturas recibidas, ingresos/gastos, and bienes de inversión.

Legal sources include RIVA art. 62 for IVA libros and RIRPF art. 68.7 for
autónomo record books. Sources:
`https://boe.es/buscar/act.php?id=BOE-A-1992-28925` and
`https://www.boe.es/eli/es/rd/2007/03/30/439/con`.

Target placement is `aeat app ledger export libros ...`, backed by outbound
AEAT/BOE format adapters. Libro-registro exports are ledger exports, not
modelo filing exports.

Reject reusing model-specific `app modelo export` paths for libros, JSON-only
libro exports, or shims that disguise filing layouts as libro layouts.
