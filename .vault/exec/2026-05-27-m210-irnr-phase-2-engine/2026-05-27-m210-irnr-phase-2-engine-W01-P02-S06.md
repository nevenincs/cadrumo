---
tags:
  - '#exec'
  - '#m210-irnr-phase-2-engine'
date: '2026-07-09'
modified: '2026-07-09'
step_id: 'S06'
related:
  - "[[2026-05-27-m210-irnr-phase-2-engine-plan]]"
  - "[[2026-07-09-m210-irnr-phase-2-engine-adr]]"
---

# author the grouping-validity verification predicates (same code, same pagador save codigo 35, same tipo de gravamen, same bien, no offsetting between grouped rentas) grounded in the bundled Articulo cuarto text

## Scope

- `src/aeat/application/modelo/_verification_predicates.py`

## Description

- DEFERRED to Slice C, no code authored. The grouping-validity rules were not implemented because doing so now would fabricate a data structure the fetched diseno de registro must define.

## Outcome

- The Articulo cuarto grouping text IS bundled (`orden-hac-56-2024.html`: same codigo de tipo de renta / mismo pagador salvo codigo 35 / mismo tipo de gravamen / mismo bien / "En ningun caso las rentas agrupadas pueden compensarse entre si"), so grounding is available.
- But every grouping rule validates a relationship ACROSS multiple grouped rentas, and (a) the current M210 casilla model is single-renta (13 casillas, one `tipo_renta` text casilla; no per-renta codigo/pagador/gravamen/bien detail rows) and (b) the verification-predicate DSL in `_verification_predicates.py` is single-filing casilla-scoped (a `Mapping[CasillaId, Decimal]` plus text values), with no operator that reasons over a set of grouped rentas. The grouped-rentas detail rows are the diseno de registro Type-2 detail = NEEDS-FETCH 1 (Slice C, fetch-gated).

## Notes

- Authoring grouping predicates now would require inventing a grouped-rentas structure that the fetched Slice-C diseno must define. Deferred to Slice C (may also want a grouped-rentas modelling ADR addendum). No code, no fabrication.
