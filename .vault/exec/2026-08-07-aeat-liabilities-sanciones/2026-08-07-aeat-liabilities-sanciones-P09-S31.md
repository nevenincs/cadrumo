---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:f9b603f03d2ea17ba4f83396615161fb71491da7cebb80f0a13dd2179b2c7220'
step_id: 'S31'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Reconcile the sancion amount pattern against the tree's two existing amount authorities rather than adding a third: _STRICT_AEAT_MONEY_RE is byte-identical in the IVA compensation wallet parser and the sancion parser with no shared home, which is true duplication, while SPANISH_AMOUNT_GROUP is constraint-shape-divergent (unanchored capture group, NBSP-tolerant) and is NOT substitutable for the anchored house pattern. Give the house pattern one canonical home consumed by both callers, verified by a duplication gate asserting the literal appears exactly once in the tree

## Scope

- `src/cadrumo/adapters/inbound/notificacion/_sancion.py`

## Description

- Delete both hand-copied declarations of the anchored AEAT money pattern.
- Declare one canonical predicate in the core decimal package beside the separator and coercion helpers both consumers already used.
- Recompose the unanchored printed-amount group from the same shared separator taxonomy.
- Add a singularity gate keyed on object identity and behaviour, never on a count.

## Outcome

Delivered, and the canonical home is not the one the row nominated.

The row's premise held: the anchored pattern was byte-identical in the sancion reader and the IVA compensation wallet parser, with one of them describing it in prose as "shared verbatim" - which is exactly what a duplicate looks like from the inside. The substitutability pre-filter also held: the unanchored printed-amount group is NOT substitutable for the anchored pattern, because anchoring it would refuse an ungrouped amount the anchored pattern's second alternative accepts. The two were kept distinct rather than collapsed.

What moved is the placement. The consumers straddle inbound and outbound adapters, so the primitive went to core beside the helpers both already consumed, and a predicate was exported rather than the compiled pattern so the gate can assert object identity and the anchoring is applied in one place. The recomposition of the unanchored group from the shared separator set was proved behaviour-identical across 127 cases before landing.

The reconciliation initially covered two of THREE grammars. A third, in the same file this Step edited, was left on the dot-only separator set and is recorded under the review closure below.

## Notes

The module docstring authored with this Step justified the core placement by claiming the consumers sit on opposite sides of the hexagon and that placing the primitive in the inbound package would create the tree's first runtime outbound-to-inbound adapter edge. That claim is false: such an edge already exists and is eager, in the sede declarations observations module. The placement is still correct on the taxonomy argument, and the docstring was corrected to state what is actually true and to name the counter-evidence, rather than leaving a future reader to inherit a false premise.

A follow-up review found the third grammar and a widening that never reached the surface it was meant to protect. Both were closed as in-scope regressions before this row was marked complete.
