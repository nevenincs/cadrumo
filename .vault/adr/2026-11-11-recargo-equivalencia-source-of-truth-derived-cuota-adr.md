---
tags:
  - "#adr"
  - "#recargo-equivalencia-source-of-truth"
date: '2026-11-11'
related:
  - "[[2026-08-07-recargo-equivalencia-source-of-truth-adr]]"
  - "[[2026-08-07-recargo-equivalencia-source-of-truth-research]]"
supersedes:
  - '2026-08-07-recargo-equivalencia-source-of-truth-adr'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:91ebb5586f82aaeec902f836aef6661628e8be5bf5398236dee9fd5491f20d1f'
---
# `recargo-equivalencia-source-of-truth` adr: `the recargo de equivalencia cuota is derived from base and rate` | (**status:** `accepted`)

## Problem Statement

The Modelo 303 recargo casillas declare the recargo de equivalencia devengado. Today the
figure stored on each transaction reaches those casillas as it stands, and a figure that
departs from the published rate only raises an advisory, as
`2026-08-07-recargo-equivalencia-source-of-truth-adr` ruled. The casilla sum is taken
from the stored amount at `src/cadrumo/domain/calculations/registry/ledger_iva_bindings.py:679`,
and the advisory lives in `src/cadrumo/application/aggregation/modelo_bindings_invoice_iva.py`.
A stored figure that is not base times rate therefore produces an exported return whose
recargo cuota disagrees with its own base and printed Tipo. This record replaces that
ruling. The defect is registered as T112.

## Considerations

- Arts. 160 and 161 of Ley 37/1992 fix the recargo: its base is the IVA base, and its
  cuota is that base times the rate published for the applied IVA rate on the devengo
  date. The figure is set by law, not by agreement between the parties.
- The 303 prints each recargo rung's Tipo as a record-design constant, so a cuota that
  is not base times Tipo is internally inconsistent on the filed record itself.
- A supplier figure that departs from the law is corrected by correcting the transaction
  or by issuing a factura rectificativa (art. 89 Ley 37/1992). It is not a second legal
  value to declare.
- The rate table is now re-keyed on applied rate and devengo date
  (`src/cadrumo/domain/iva/recargo_equivalencia.py`), and it already serves the advisory.
- The application never files. A defect that survives export reaches the taxpayer with
  no gate behind it, so the refusal must name both figures, the rate, the date and the
  provision, and must offer a way to correct the transaction.

## Considered options

**Keep the stored figure authoritative and advise on mismatch.** This is the predecessor
ruling. Rejected because it exports a 303 whose recargo cuota contradicts its own base
and Tipo, and the advisory does not stop that return.

**Derive the cuota and silently replace the stored figure.** Rejected because the
operator never learns that the transaction or the invoice is wrong, so the books keep a
figure that the return contradicts.

**Derive the cuota per line, and refuse a stored figure that departs by more than
rounding.** Chosen. The return carries the legal figure. A departure becomes a
structured finding that the operator resolves at its source. The stored figure never
wins.

## Constraints

- The derivation is per line: the line base times the rate resolved for that line's
  applied IVA rate and devengo date, rounded to the cent. The stored figure is compared
  at line level, with a tolerance of at most 0.01 per line for rounding only.
- A larger difference is a refusal. It carries a structured finding naming the stored
  and derived figures, the rate, the date and the provision, plus a served door to
  correct the transaction. Wording comes from the backend catalogue; no frontend
  composes it.
- The rate lookup is keyed on the applied IVA rate and the devengo date. It covers every
  art. 161 rate and every transitional window. An unmodelled rate and date pair stays
  unresolved: it is never guessed, never projected and never zero. The predecessor's
  re-keying constraint still binds.
- Before any refusal goes live, every rate and window the lookup serves is grounded in
  the BOE text and the provisions are cited in the registry. The predecessor recorded
  two agent-prepared catalogue entries pending review, and this record does not
  inherit them unreviewed.
- Tests run through the real resolver for every year of the registry's supported
  envelope, enumerated from the registry and never listed by hand. They cover an exact
  figure, a rounding-only difference, a refused mismatch, a transitional window and an
  unmodelled pair.
- Scope is the recargo cuota. Whether `iva_amount_sum` carries the same pattern is
  checked and reported to the coordinator before anything changes. It is not widened
  under this record.

## Implementation

We will derive the recargo de equivalencia cuota of each IVA ledger line from its base
and the registry rate for its applied IVA rate and devengo date, and refuse a stored
figure that departs from it by more than one cent per line. The derived figure is the
value that reaches the 303. The invoice mismatch advisory becomes this refusal rather
than a parallel signal. Where the derivation runs (the IVA observation build or the
binding aggregation) is an implementation choice within these constraints.

## Rationale

The recargo is a quantity the law computes, not a fact the invoice establishes. The
predecessor's knockout was that a legitimate invoice can carry a figure the table does
not predict. Under arts. 160 and 161 such an invoice is not legitimate on that point:
its remedy is rectification, and the return must not carry the departure. The
predecessor's other concern, that a computed figure must not silently overwrite a
recorded one, is met by refusing rather than replacing. The operator sees both figures
and the provision, and corrects the record. That keeps the standing posture of
surfacing rather than silently resolving, while enforcing the rule the 303 itself
encodes.

Accepted 2026-11-11 by the coordinator (COORD), under the operator's standing authority
that AEAT tax rules are enforced and not offered as choices. The coordinator imposed the
binding conditions listed under Constraints.

## Consequences

- A 303 with a recargo cuota inconsistent with its base can no longer be exported from
  stored figures.
- Operators whose transactions carry a mistyped or mis-charged recargo are blocked until
  they correct it. The refusal must therefore be specific and must name its door.
- The rate table becomes filing-load-bearing, so its grounding review is a precondition
  rather than a follow-up.
- Historical returns are not changed. A previously exported return with a wrong recargo
  is surfaced on recalculation, not rewritten.
- Reconsider if AEAT's record design ever accepts a recargo cuota that is not base times
  Tipo.
