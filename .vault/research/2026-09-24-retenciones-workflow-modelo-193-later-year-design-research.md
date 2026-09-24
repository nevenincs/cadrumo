---
tags:
  - '#research'
  - '#retenciones-workflow'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:ead4293674905e8f6bf2ab92b343767591c1853aacad9c8d97f8342dce4a651a'
related: []
---

# `retenciones-workflow` research: `Modelo 193 later-year record design`

Question: which record design governs Modelo 193 for ejercicio 2026 and later? Measured on 2026-09-23: no design dated after ejercicio 2025 exists, and the 2025 design has no end year, so on the order's own wording it governs 2026 until amended. That is a reading of the order text; no AEAT statement confirms it. Re-check the sources before relying on the answer, because a later order would change it.

## Findings

### The 2025 design is the only current one

- The AEAT record-design catalogue (modelos 100–199, page updated 2026-08-25) lists a single entry-193 design: `DR_Modelo_193_2025.pdf`, "Orden EHA/3377/2011 (actualizado por Orden HAC/1430/2025)". It has no XLS and no file labelled 2026. The PDF itself was not opened in this pass.
- Orden HAC/1430/2025 (BOE 2025-12-12, in force 2025-12-13) applies to Modelo 193 for the first time for ejercicio 2025. It adds the type-2 CÓDIGO ISIN field (positions 193–204) and changes CLAVE CÓDIGO (79), CÓDIGO EMISOR (80–91) and NATURALEZA DEL DECLARANTE (208). It sets no end year.
- Orden HAC/1504/2024 (BOE 2024-12-31) first applied to ejercicio 2024 and is superseded for 2025.
- The consolidated Orden EHA/3377/2011 (latest version 2025-12-12) references no 2026 amendment.

### No 2026 change is announced

- The AEAT GI12 procedure page (updated 2026-09-08) lists regulations only up to HAC/1430/2025.
- The AEAT notice of 2025-12-12 confirms 193's first year under that order is 2025; in the same order only Modelo 195 starts in 2026.
- The informativas campaign page (updated 2026-07-13) has no ejercicio-2026 campaign yet.
- The Hacienda draft orders found (the 2025-09-16 informativas draft and the 2026-03-10 DAC8 draft) do not cover 193 for 2026. The full list of 2026 drafts was not exhausted.
- The last two amendments were published on 2024-12-31 and 2025-12-12, so a new one would most likely appear in November or December 2026.

### Registry and implementation consequences

The registry's Modelo 193 revision `2025-y-siguientes` declares `year_from = 2025` with no `year_to`, so ejercicio 2026 already resolves to the 2025 design, and no authoring is possible until a new order appears. The gap when measured was implementation: `src/cadrumo/application/aggregation/m193_phase_materialization.py` builds the PENDING (accrual-year) and SETTLED_PRIOR_ACCRUAL (payment-year) disclosure rows, but no export path consumed it.

## Sources

- https://sede.agenciatributaria.gob.es/Sede/ayuda/disenos-registro/modelos-100-199.html
- https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/DR_Modelo_193_2025.pdf
- https://www.boe.es/buscar/doc.php?id=BOE-A-2025-25389
- https://www.boe.es/buscar/doc.php?id=BOE-A-2024-27528
- https://www.boe.es/buscar/act.php?id=BOE-A-2011-19396
- https://sede.agenciatributaria.gob.es/Sede/procedimientoini/GI12.shtml
- https://sede.agenciatributaria.gob.es/Sede/todas-noticias/2025/diciembre/12/modificacion-determinadas-declaraciones-informativas.html
- https://sede.agenciatributaria.gob.es/Sede/declaraciones-informativas/campana-declaraciones-informativas.html
- https://www.hacienda.gob.es/SGT/NormativaDoctrina/Proyectos/16092025-proyecto-OM-informativas-2025.pdf
- https://www.hacienda.gob.es/sgt/normativadoctrina/proyectos/09032026-main-proyecto-om-dac8.pdf
- `src/cadrumo/application/aggregation/m193_phase_materialization.py`
