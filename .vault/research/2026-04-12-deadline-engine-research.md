---
tags:
  - "#research"
  - "#deadline-engine"
date: 2026-04-12
modified: '2026-04-12'
title: Filing-Deadline Computation Engine — Research
related:
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-deadline-engine-plan]]"
issue: wgergely/aeat#38
---

# research: filing-deadline computation engine

## goal

Survey the AEAT publication channels for filing-window dates and the
canonical legal substrate that determines *who must file which modelo*
for an autónomo profile, so the engine can compute a deterministic,
typed schedule from `(profile, year)` with citations.

## sources

### canonical AEAT calendars

- **Calendario del contribuyente** (yearly):
  `https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-practicos/calendario-contribuyente.html`
  Each year (2025, 2026) has a per-modelo entry with the filing window
  open and close dates and the payment cutoff (typically `closes_on - 5`
  for direct-debit autónomos).
- **Modelo-specific filing pages** (e.g.,
  `https://sede.agenciatributaria.gob.es/.../Modelo_303.shtml`) carry
  the BOE references for the order that fixes each year's window.

### canonical autónomo deadlines (representative — 2026 cycle)

The dates below are the standard windows the engine encodes for the
2026 calendar year. Each row cites the BOE order that fixes the
modelo's filing schedule plus the relevant article of the Manual
práctico chapter for the modelo.

| modelo | period         | opens_on   | closes_on  | cite                                            |
|--------|----------------|------------|------------|-------------------------------------------------|
| 130    | 2026Q1         | 2026-04-01 | 2026-04-20 | Orden HFP IRPF pagos fraccionados; MP cap. IRPF |
| 130    | 2026Q2         | 2026-07-01 | 2026-07-20 | idem                                            |
| 130    | 2026Q3         | 2026-10-01 | 2026-10-20 | idem                                            |
| 130    | 2026Q4         | 2027-01-01 | 2027-01-30 | idem                                            |
| 303    | 2026Q1         | 2026-04-01 | 2026-04-20 | Orden HFP IVA autoliquidación; MP cap. IVA      |
| 303    | 2026Q2         | 2026-07-01 | 2026-07-20 | idem                                            |
| 303    | 2026Q3         | 2026-10-01 | 2026-10-20 | idem                                            |
| 303    | 2026Q4         | 2027-01-01 | 2027-01-30 | idem                                            |
| 100    | 2025 (annual)  | 2026-04-02 | 2026-06-30 | Orden IRPF declaración anual; MP IRPF           |
| 390    | 2026 (annual)  | 2027-01-01 | 2027-01-30 | Orden IVA resumen anual; MP IVA cap. resumen    |
| 111    | 2026Q1..Q4     | quarter+1  | day 20     | Orden retenciones IRPF; MP retenciones          |
| 115    | 2026Q1..Q4     | quarter+1  | day 20     | Orden retenciones alquiler; MP retenciones      |
| 180    | 2026 (annual)  | 2027-01-01 | 2027-01-30 | Resumen anual 115                               |
| 190    | 2026 (annual)  | 2027-01-01 | 2027-01-30 | Resumen anual 111                               |
| 036    | event          | n/a        | n/a        | Census (alta/modificación/baja); event-driven   |
| 037    | event          | n/a        | n/a        | Simplified census; event-driven                 |
| 349    | 2026Q1..Q4     | quarter+1  | day 20     | Recapitulativa intra-EU                         |
| 720    | 2025 (annual)  | 2026-01-01 | 2026-03-31 | Bienes en el extranjero                         |

The engine records the canonical orders as opaque BOE references on
the obligation, not as live URLs — citations are stable, URLs decay.

## applies_to truth tables

The columns below are the relevant `AutonomoProfile` flags. `Y` means
the modelo applies if and only if the flag combination matches.

### Modelo 130 — IRPF pagos fraccionados (estimación directa)

- Applies to every autónomo unless they are in **estimación
  objetiva** (out of scope for this engine — modelo 131) or earn
  >70 % of revenue from clients applying retención.
- Profile-flag derivation: `iva_regime != EXENTO` is *not* the
  driver; the driver is "is the autónomo in estimación directa". For
  the v1 engine we treat the autónomo set as estimación directa
  (project north star) and so 130 always applies.
- Cite: BOE Orden HFP IRPF pagos fraccionados; MP IRPF cap. pagos
  fraccionados.

### Modelo 303 — IVA autoliquidación

- Applies whenever `iva_regime ∈ {GENERAL, SIMPLIFICADO}`.
- Does **not** apply when `iva_regime == RECARGO_EQUIVALENCIA`
  (the supplier files for the autónomo) nor when `iva_regime ==
  EXENTO`.
- Cite: BOE Orden HFP IVA autoliquidación; MP IVA cap. 303.

### Modelo 100 — IRPF declaración anual

- Applies to every individual with sufficient income; for v1 we
  always apply it to the autónomo profile (the project assumes the
  user is an autónomo with non-zero activity).
- Cite: BOE Orden IRPF declaración anual.

### Modelo 390 — IVA resumen anual

- Applies whenever Modelo 303 applies, except where the autónomo is
  exempt from 390 by virtue of filing 303 with the additional
  information block (a regime not modelled in v1).
- Cite: BOE Orden IVA resumen anual; MP IVA cap. resumen.

### Modelo 111 — Retenciones IRPF rendimientos del trabajo y profesionales

- Applies iff `has_employees == True` (the autónomo pays salaries
  with retención) **or** the profile pays professionals with
  retención (collapsed into `has_employees` for v1 — if you have
  retenciones at all, you file 111).
- Cite: BOE Orden retenciones IRPF; MP cap. retenciones.

### Modelo 115 — Retenciones IRPF arrendamientos de inmuebles urbanos

- Applies iff `pays_rent_with_retencion == True`.
- Cite: BOE Orden retenciones alquiler.

### Modelo 180 — Resumen anual 115

- Applies iff Modelo 115 applies.

### Modelo 190 — Resumen anual 111

- Applies iff Modelo 111 applies.

### Modelo 036 / 037 — Censo

- Event-driven. The engine emits **no** scheduled obligations for
  these. `applies_to` returns `False` because there is no recurring
  filing window. They are still part of the modelo catalogue for
  unrelated tooling.

### Modelo 349 — Operaciones intracomunitarias

- Applies iff `does_intracomunitario == True`.
- Cite: BOE Orden operaciones intracomunitarias.

### Modelo 720 — Bienes en el extranjero

- Applies iff `bienes_extranjero_above_threshold == True`.
- Cite: BOE Orden 720.

## status thresholds

- `OVERDUE`  — `today > closes_on`
- `DUE_TODAY` — `today == closes_on`
- `DUE_SOON` — `closes_on - today ∈ [1, AEAT_DEADLINE_DUE_SOON_DAYS]`
- `UPCOMING` — `closes_on - today > AEAT_DEADLINE_DUE_SOON_DAYS`
- `FILED`    — set externally (#10 storage), never inferred by the
  engine in v1.
- `NOT_APPLICABLE` — never produced by `compute` (filtered out at
  source by `applies_to`); reserved for downstream consumers.

## non-goals

- Persisting the schedule to the storage layer (#10 follow-up).
- Filing anything.
- Notifications/alerts.
- Modelos beyond the autónomo set listed above.
- Hard imports from in-flight subpackages — Protocol stubs only.
