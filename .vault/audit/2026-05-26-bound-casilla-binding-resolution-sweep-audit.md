---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
  - "[[2026-05-26-modelo-130-relation-regression-audit]]"
---

# `modelo-130-relation-regression` audit: `bound-casilla-binding-resolution-sweep`

## Scope

Plan step `P02.S06` ran a programmatic sweep over the full AEAT
registry tree to enumerate every casilla declared with
`input_kind = "bound"` and classify the named binding by its
resolution path. This document is the durable catalogue of
findings; `P02.S08` actions every entry classified as
`direct_dead` or `relation_orphaned` before the runtime flip in
phase `P03`.

The sweep is the structural safety net for the runtime change in
`P03`. The 2026-05-26 ADR documents the silent `Decimal("0")`
fallback that bound casillas with dead bindings produce today;
eliminating that fallback will surface every dead binding as a
calculation error unless each one is repaired or annotated as
absent-by-design beforehand.

## Sweep totals

87 bound casillas declared across every modelo revision in the
registry. Classification distribution:

- `direct_resolvable` — 7. Selector declares a period anchor that
  resolves to at least one source observation. Safe under the
  runtime flip.
- `direct_dead` — 5. Selector declares no period anchor and no
  relation targets the binding. SILENT-ZERO HAZARD; must be
  repaired or annotated before `P03`.
- `relation_driven` — 3. Selector lacks a period anchor but a
  `RelationDefinition` in the revision carries the source contract.
  Safe.
- `relation_orphaned` — 1. Selector declares `relation = "..."`
  but the referenced relation does not exist in the revision. Same
  hazard class as `direct_dead`; must be repaired or annotated.
- `non_previous_filing` — 71. Binding's source is not
  `previous_filing` (profile, invoice, ledger, etc.); resolution
  goes through a different pipeline. Not affected by this campaign.

## Actionable findings

Six entries require remediation before `P03`. Five are the same
structural pattern (quarterly IRPF instalment carry-forward), one is
a separate orphan-relation defect.

### Pattern A — quarterly IRPF instalment prior-quarter carry-forward (5 entries)

These bindings declare the prior-quarter negative-result
carry-forward for IRPF pago-fraccionado instalments. The selector
declares `source_modelo = "<self>", source_output =
"saldo-negativo-fin-periodo"`, omits the period anchor and the
relation, and aggregates with `{op = "copy"}`. With no period
anchor and no relation declaration the binding silently never
fires; the bound casilla defaults to `Decimal("0")` through
`_initial_values`. AEAT's RD 439/2007 art. 110.5 (Modelo 130) and
the parallel rule for estimación objetiva (Modelo 131) require the
prior quarter's saldo negativo to deduct from the current
quarter's diferencia.

| Modelo | Revision        | Casilla | Binding id                                          |
| :----- | :-------------- | :------ | :-------------------------------------------------- |
| 130    | 2019-y-siguientes | 15    | `modelo-130-resultados-negativos-anteriores`         |
| 131    | 2019-2023       | 11      | `modelo-131-2019-2023-resultados-negativos-anteriores` |
| 131    | 2024            | 11      | `modelo-131-2024-resultados-negativos-anteriores`    |
| 131    | 2025            | 11      | `modelo-131-2025-resultados-negativos-anteriores`    |
| 131    | 2026            | 11      | `modelo-131-2026-resultados-negativos-anteriores`    |

**Remediation**: extend each selector to declare
`source_period_offset_from_target = -1` and `max_year_delta = 0`
(the same-ejercicio capability landed in `P01`). 1T produces no
anchor and the bound casilla materialises `Decimal("0")` via the
absent-by-design constructor (provenance-marked); 2T/3T/4T resolve
the prior quarter's seed.

`P04` already plans the M130 revision (`P04.S14`). The plan must be
amended to include the four M131 revisions; the same selector
shape applies because the AEAT rule and the saldo-negativo
mechanism are identical.

### Pattern B — orphan relation reference (1 entry)

| Modelo | Revision | Casilla | Binding id                                                | Detail                                     |
| :----- | :------- | :------ | :-------------------------------------------------------- | :----------------------------------------- |
| 100    | 2025     | 1577    | `renta-2025-modelo-184-atribucion-actividades-economicas` | Selector declares `relation = "..."` but no `RelationDefinition` in the 2025 revision matches the referenced relation id. |

**Remediation**: this is not the M130 carry-forward pattern.
Possible answers: declare the missing relation in the modelo-100
2025 revision, revise the selector to remove the relation
reference and add explicit period anchors, or annotate the binding
as absent-by-design if the binding is not yet wired. Requires its
own investigation; the M130 plan's `P02.S08` must defer to a
follow-up audit unless one of these answers is clearly correct.

## Provenance

- Sweep script: `.vault-scratch/bound_casilla_sweep.py` (one-off, discarded after S08 closes).
- Sweep output: `.vault-scratch/bound_casilla_sweep.json` (one-off, discarded after S08 closes).
- Classification logic: `_PreviousModeloSelector.required_period_anchors_for_target` plus presence-of-`RelationDefinition`-targeting-the-binding-id in the revision.

## Plan amendment required

Plan step `P04.S14` currently scopes the binding revision to
Modelo 130 only. The sweep proves the same pattern affects
Modelo 131 across four revisions. The plan must be amended:

- Add a step `P04.S14a` (or equivalent identifier via
  `vault plan step insert`) revising each of the four M131 binding
  selectors with `source_period_offset_from_target = -1` and
  `max_year_delta = 0`.
- The legal grounding extension in `P04.S15` continues to target
  `[legal."rd-439-2007:art-110"]`; M131's legal basis is also
  RD 439/2007 (estimación objetiva carry-forward semantics
  parallel modulos-objetivos), confirm during `S14a`.

The M100 C1577 orphan-relation finding is held as a follow-up
audit; not actioned in this plan unless `S08` discovers the
correct remediation is a one-line selector revision.
