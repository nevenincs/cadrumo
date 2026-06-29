---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-26'
modified: '2026-06-29'
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
- `relation_orphaned` — 1. INVESTIGATION RECLASSIFIED THIS AS A
  FALSE POSITIVE. See "Pattern B" below. The sweep classifier
  matched `selector.relation` against `RelationDefinition.id`; the
  runtime actually matches via `RelationDefinition.target_binding`.
  The binding is correctly relation-driven and is NOT a hazard
  under the P03 runtime flip.
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
`_initial_values`. AEAT Modelo 130 instructions, under the current
RD 439/2007 art. 110 payment framework, and the parallel rule for
estimación objetiva (Modelo 131) require the prior quarter's saldo
negativo to deduct from the current quarter's diferencia.

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

### Pattern B — orphan relation reference (1 entry, reclassified as false positive)

| Modelo | Revision | Casilla | Binding id                                                | Detail                                     |
| :----- | :------- | :------ | :-------------------------------------------------------- | :----------------------------------------- |
| 100    | 2025     | 1577    | `renta-2025-modelo-184-atribucion-actividades-economicas` | Selector declares `relation = "atribucion-actividades-economicas"`. The matching `RelationDefinition` exists at id `renta-2025-rel-184-atribucion-actividades-economicas` with `target_binding` pointing at this binding's id. |

**Resolution**: NOT a runtime hazard. Investigation surfaced that
the relation→binding runtime linkage uses
`RelationDefinition.target_binding`, not the binding's
`selector.relation` field. The matching relation exists with
`target_binding = "renta-2025-modelo-184-atribucion-actividades-economicas"`
at `.../revisions/2025/relations/0008-renta-2025-rel-184-atribucion-actividades-economicas.toml`,
so the runtime resolves the binding correctly.

The defect is the sweep classifier: it treated `selector.relation`
as the canonical lookup key and reported a false orphan when the
shorthand did not match the prefixed relation id. Every M100 2025
binding uses an unprefixed `selector.relation` shorthand
(`atribucion-actividades-economicas`,
`retenciones-trabajo-actividades-premios`, etc.) while the actual
relation ids carry the `renta-2025-rel-XXX-` prefix — that is a
consistent convention in the registry, not a defect in the
binding.

**P03 is NOT blocked by this finding.** The runtime flip will not
surface this binding as a calculation error: relation-driven
bindings resolve through the relation pipeline, not through the
direct previous-filing resolver, and the relation→binding linkage
is intact.

Optional follow-up (low priority, not blocking): either reconcile
the unprefixed `selector.relation` shorthand convention with the
relation id, or remove the field entirely from the selector schema
since the runtime does not consult it. Address in a separate
campaign — out of scope for the silent-zero elimination work.

## Provenance

- Sweep script: discarded under P07.S35 (one-off as planned). The
  script body lives in commit `5d069ce6b` (P02.S06-S08) for
  archival reference; the runtime classifier had a known false-
  positive bug (relation_orphaned matched `selector.relation`
  against `RelationDefinition.id` instead of using
  `target_binding`) tracked at P07.S37.
- Sweep output: discarded under P07.S35. The findings catalogued
  in this audit are the durable record.
- Classification logic: `_PreviousModeloSelector.required_period_anchors_for_target` plus presence-of-`RelationDefinition`-targeting-the-binding-id in the revision.

### Correct classification rule (for future re-implementations)

The original sweep script (P02.S06, commit `5d069ce6b`) had a
known false-positive defect in the `relation_orphaned` branch.
The bug: it matched the binding's `selector.relation` shorthand
against `RelationDefinition.id`. The shorthand was documentation
drift and never matched the prefixed relation id; the runtime
ignored it entirely. The bug surfaced one false positive
(M100 2025 C1577) during the original sweep — investigation
proved the binding was correctly relation-driven via
`target_binding`.

**Authoritative rule for any re-implementation of the
bound-casilla resolution sweep:**

- A previous-filing binding is `direct_resolvable` iff its
  selector returns a non-empty
  `required_period_anchors_for_target` for at least one period
  declared by the revision's `period_selector`.
- A previous-filing binding is `direct_dead` iff
  `required_period_anchors_for_target` is empty AND no
  `RelationDefinition` in the revision targets the binding
  (`target_binding == binding.id`).
- A previous-filing binding is `relation_driven` iff
  `required_period_anchors_for_target` is empty AND at least one
  `RelationDefinition` in the revision has
  `target_binding == binding.id`. The `selector.relation`
  shorthand is irrelevant — it was retired under P07.S32.
- A previous-filing binding is `absent_by_design` iff the cap
  (`max_year_delta`) suppresses every anchor for every declared
  target period. It is functionally `direct_dead` but
  intentionally so; the runtime materialises zero with the
  `absent_by_design` provenance marker.
- The `relation_orphaned` classification SHOULD NOT EXIST — it
  was always a defect rooted in the now-retired `selector.relation`
  shorthand.

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
