---
tags:
  - '#research'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-adr]]"
---



# `silent-zero-base-aggregation` research: `M130 agrarian estimacion-objetiva income classification axis`

Scopes the classification axis required before Modelo 130 casilla 08 "Volumen de
ingresos del trimestre" (estimación objetiva agrícola/ganadera/forestal, apartado
II) can be aggregated from the ledger. This is the one silent-zero base candidate
that is neither peer-blocked nor a bounded mirror: it is blocked by a missing
domain capability.

## Findings

### The gap

M130 casilla 08 sits in the `actividades_agricolas_ganaderas_forestales_pesqueras`
section — the estimación objetiva (módulos agrarios) régimen of apartado II — a
different régimen from the estimación directa (apartado I) whose income (casilla
01) and gastos (casilla 02) are now ledger-aggregated. Casilla 08 is manual and
silently zero for an agrarian-objetiva filer.

### Why it is not a bounded mirror

Aggregating casilla 08 with the existing income aggregator would mis-route: the
income aggregator selects actividad-económica receipts by `irpf_category ==
"actividad_economica"` and the business classification, neither of which
distinguishes agrarian-objetiva income from estimación-directa income. Folding the
directa receipts into the agrarian volume (or vice versa) would put income in the
wrong régimen's casilla — a wrong regulated number. The transaction model carries
no agrarian-objetiva marker.

### What is needed (the classification axis)

A per-transaction régimen/activity-type marker that distinguishes:

- actividad económica en estimación directa (feeds M130 apartado I, M100 0171),
- actividad agrícola/ganadera/forestal en estimación objetiva (feeds M130 casilla
  08 and the M131 / M100 agrarian-objetiva surfaces),

so an agrarian income aggregator can select only agrarian-objetiva receipts. The
marker likely belongs alongside `irpf_category` on the transaction, set at
classification time (the operator declares the activity régimen), and validated at
preflight. Once the axis exists, casilla 08 becomes a bounded mirror: a new
`ledger_renta_*` agrarian-income binding selecting the agrarian-objetiva marker
over the cumulative quarterly window, mirroring the directa income aggregation.

### Decision gate

This requires a domain-model change (the classification axis) and is therefore an
ADR-scale prerequisite, not a registry-only bind. It is recorded here so a future
agent does not naively reuse the directa income aggregator for casilla 08. The
agrarian aggregation is deferred until the classification axis lands; the existing
directa income/gasto aggregation is unaffected.
