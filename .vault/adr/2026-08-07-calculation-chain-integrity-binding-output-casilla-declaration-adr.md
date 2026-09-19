---
tags:
  - '#adr'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:bc4eef83583b74bdad1f78ac46c1a7df46a104507cb95d822adf4f8f26cf6e56'
related:
  - "[[2026-08-07-calculation-chain-integrity-adr]]"
  - '[[2026-08-07-calculation-chain-integrity-m390-annual-under-modelling-research]]'
---
# `calculation-chain-integrity` adr: `Whether a binding selector may declare a match casilla distinct from its output casilla` | (**status:** `proposed`)

## Problem Statement

`2026-08-07-calculation-chain-integrity-adr` ruled `W01` on T-05's established pattern: the M130 retenciones-a-cuenta binding's output casilla stays a Python constant (`_M130_RETENCIONES_CASILLA`) plus a snapshot cross-check, not a new `output_casilla_id` selector field. That ruling stands and is shipped -- this record does not reopen it. What it does raise is a question `T-05` itself never answers, because the T-05 inventory (`.vault/reference/2026-05-15-linkage-design-audit-reference.md`) was scoped to hardcoded casilla MAPS living entirely outside the registry, not to a registry SELECTOR SCHEMA that may be structurally unable to express a fact at all. This record asks the narrower, structural question: can a `ledger_iva_aggregation`-style binding ever declare "match these observations, but report on a DIFFERENT casilla than the one whose `binding` field points at me" -- and if it structurally cannot, is that a gap worth a future ADR closing, separate from the M130 case T-05 already resolved.

## Considerations

- The registry expresses "which casilla does a binding feed" through two genuinely different, coexisting conventions, both counted directly against the committed registry tree rather than taken from a secondhand report: casilla-declares-binding (`CasillaDefinition.binding: BindingId | None`, one binding per declaring casilla -- 144 TOML files carry a `binding = "..."` line) and binding-declares-casilla (a binding selector carries its own `target_casilla_id`, used by six source families -- `ledger_renta_income_aggregation`, `ledger_renta_gastos_estimacion_directa_aggregation`, `ledger_renta_gastos_pago_fraccionado_aggregation`, `ledger_impatriado_income_aggregation`, `ledger_irnr_income_aggregation`, `retenciones_aggregation` -- across 52 binding entries in 8 modelos: 100, 111, 115, 130, 151, 180, 193, 210).
- `_IvaLedgerSelector` (`src/cadrumo/domain/calculations/registry/_ledger_bindings.py`) is the casilla-declares-binding direction's selector and carries no casilla-identifying field at all -- it matches by `categories` / `rate_kinds` / `flow_direction` / `cash_accounting_treatments` / `fact` only. The output casilla is determined entirely by which `CasillaDefinition.binding` names the binding's id, and that pointer is single-valued: one casilla, one binding. There is structurally no field anywhere in this direction to say "this binding's aggregate belongs on a casilla OTHER than the one whose `binding` field points here." A binding in this direction that needed a match/output divergence has no selector field to express it in, independent of any Python-constant workaround -- the workaround pattern T-05 established lives entirely in the OTHER direction (a binding-declares-casilla selector's `target_casilla_id`, which is exactly what M130 retenciones has and what the accepted `W01` ruling defends with a constant plus cross-check).
- T-05's own "Promotion path" (`Do not reopen R025/R026 without a new ADR that supersedes the current cross-domain routing-table design`) names two specific, closed inventory rows (`FIRST_SLICE_EXPENSE_CASILLAS`, the Modelo 100 gastos routing table). It does not, on its text, extend to a *different* selector schema question for the casilla-declares-binding direction, which T-05 never inventories at all -- T-05's whole inventory is module-level Python maps outside the registry, and `_IvaLedgerSelector`'s absent field is a registry SCHEMA gap, not a hardcoded map. Whether the accepted `W01` ruling's reasoning (a schema field "reopens" the routing-table design) actually reaches this different, un-inventoried direction is exactly what this record asks a future decision to settle -- not something this record asserts either way.
- The reverted `300cddcb3f` implementation (superseded by `fc0d0353b2`) is retained here as evidence, not as a live artefact: an `output_casilla_id: CasillaId | None` field on `_RentaLedgerIncomeSelector`, a build-time "must differ from `target_casilla_id`" validator, a per-modelo allowed-output-casillas set, and a `renta_income_binding_output_casilla_values` projection generalizing the redirect. It worked, passed the full aggregation and E2E suite, and demonstrates ONE concrete shape a future decision could adopt for the binding-declares-casilla direction specifically -- it does not demonstrate anything about the casilla-declares-binding / IVA direction's structural gap, which would need its own selector shape (a casilla-identifying field added to `_IvaLedgerSelector` and its five siblings) if ever closed.

## Considered options

1. **Leave both directions as measured today (do nothing).** The IVA direction's match/output divergence stays inexpressible; if a future IVA-family binding ever needs it, the fix is invented under time pressure with no prior decision to ground it. Costs nothing now, defers the decision to whoever hits the wall.
2. **Extend the casilla-declares-binding direction with a second, optional casilla-identifying field on the shared IVA-style selector base** (e.g. an `output_casilla_id` sibling to a new match-side field), closing the gap for that direction specifically. Not attempted or prototyped by this session; a future ADR would need its own selector-shape design, since nothing here demonstrates it.
3. **Adopt the reverted `output_casilla_id` shape for the binding-declares-casilla direction specifically, formally superseding `W01`'s T-05-pattern ruling for that direction only**, leaving the IVA direction's separate gap (option 2) untouched as a distinct question. This is the narrowest read of what the peer's measurement actually supports: it grounds the binding-declares-casilla direction's expressiveness gap, not the IVA direction's.
4. **Treat T-05's "do not reopen" line as binding across both directions and close this record as `rejected`.** Consistent with the umbrella ADR's `W01` ruling and the most conservative reading, but does not engage with the fact that `_IvaLedgerSelector` has no field to express the divergence at all -- a gap T-05 never inventoried and therefore never ruled on.

## Constraints

- No option here is implemented or prototyped except option 3's shape, which already shipped and was reverted (`300cddcb3f`) -- readopting it is a re-land, not new design work, if this record is accepted.
- Option 2 (the IVA-direction fix) has zero prior art in this codebase; a future ADR adopting it starts from a blank selector-shape design, not from a working reverted implementation.
- This record cannot itself decide between options -- it exists because the question is genuinely open, not because one option is obviously correct. Closing it requires the same authority that closed `W01` (an accepted ruling on this feature), not an implementation choice made in passing.
- The 144/52/8 counts above are a point-in-time measurement against the committed registry tree on `2026-08-07`; a future decision should re-measure rather than trust this record's numbers verbatim, since the registry TOML tree continues to grow.

## Implementation

No implementation is proposed by this record. If a future decision resolves toward option 3, the concrete shape is already written and tested in commit `300cddcb3f` (reverted at `fc0d0353b2`): an optional `output_casilla_id: CasillaId | None` field on the affected binding family's selector, a build-time validator refusing an `output_casilla_id` equal to `target_casilla_id`, a per-modelo allowed-output-casillas set validated at registry build, and a generic projection function reading the declaration off any binding on a revision. If a future decision resolves toward option 2, the IVA-direction selector families (`_IvaLedgerSelector` and its OSS/M390 siblings) would need a new casilla-identifying field design with no existing prototype.

## Rationale

This record does not pick a winner. Its purpose is narrower: it distinguishes what `2026-08-07-calculation-chain-integrity-adr`'s `W01` ruling actually decided (the M130 retenciones case, a binding-declares-casilla instance, correctly resolved under T-05's established and already-shipped pattern) from a structurally different, un-inventoried question T-05 never reaches -- whether the casilla-declares-binding / IVA direction can express a match/output divergence at all. Measuring the two conventions directly (144 files / 52 entries / 8 modelos) rather than relying on a secondhand report confirms the split is real and the IVA direction's selector genuinely carries no field for this. That is evidence the question is live, not evidence for any particular answer to it.

## Consequences

Gain: the distinction between "T-05 already settled this" (the M130 case, `W01`, accepted) and "T-05 was never asked this" (the IVA-direction expressiveness gap) is now a citable record instead of a claim made once in chat and forgotten. A future agent who hits an IVA-family binding needing a match/output divergence has a starting point -- the measured split, the reverted prototype shape, and the named open options -- instead of re-deriving all three under time pressure.

Honest difficulty: this record's own existence is a judgment call about scope-splitting that could itself be wrong -- a reviewer could reasonably conclude the IVA-direction gap is close enough to the M130 case that `W01`'s reasoning already covers it, collapsing this record's four options back to option 4. That collapse would be a legitimate accepted disposition of this record, not a defect in raising the question.
