---
tags:
  - '#adr'
  - '#silent-zero-base-aggregation'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-research]]"
  - "[[2026-06-10-calculation-aggregation-taxonomy-adr]]"
---

# `silent-zero-base-aggregation` adr: `Silent-zero regulated-base aggregation: bounded mirror vs ADR boundary` | (**status:** `accepted`)

## Problem Statement

A recurring silent under-declaration was found across the modelo registry: a
regulated base or volume casilla resolves to zero on the live calculate path
while its sibling cuota aggregates from the ledger, producing a cuota-without-base
shape AEAT rejects and a return that under-declares without surfacing a finding.
The registry-wide sweep recorded in the companion research enumerated every
candidate and classified each as either a bounded mirror (an existing canonical
ledger-aggregation source can feed the casilla through registry wiring alone) or
an ADR-scale change (a new resolver, period semantics, classification axis, or
official-form restructure). This ADR ratifies that boundary so the bounded
mirrors are shipped and the ADR-scale items are deferred deliberately rather than
force-fitted into wrong regulated numbers.

## Considerations

- The calculation-aggregation taxonomy already mandates one canonical mechanism
  per value channel: cross-modelo fold-ins are relations, ledger projection is a
  ledger-aggregation resolver, and a new aggregation surface must enroll under an
  existing taxonomy row rather than introduce a parallel path.
- A bounded mirror reuses an existing `ledger_*_aggregation` source family,
  selector shape, and fact (for example `base_amount_sum` on
  `ledger_iva_aggregation`, or the OUTGOING sibling of the renta-income source),
  enrolled in the live source mesh and grounded in the same binding provision as
  its sibling cuota.
- An ADR-scale change introduces a new resolver/aggregator, a new period model
  (annual vs quarterly), a classification axis the transaction model does not
  carry, or a restructure of an official AEAT box into a computed total — any of
  which ripples across locales, completeness manifests, and a large test surface.
- The shared worktree carries concurrent peer work; the M303 régimen-general base
  bindings are an in-flight bounded mirror owned elsewhere and are out of scope
  here.

## Constraints

- No invented legal behaviour: a regulated value must be grounded in the binding
  provision that establishes it, cross-checked against the bundled authoritative
  corpus. The M303 prorrata and M100 income mechanisms cannot be approximated by a
  per-period base sum without producing wrong figures.
- The source-mesh caller-override guard makes every ledger-aggregation casilla
  ledger-authoritative; restructuring an official box into "ledger plus operator
  adjustment" (to admit non-ledger deductible items) is itself an ADR-scale change
  because it adds casillas requiring four-language locale authoring, manifest and
  formula-graph updates, and broad test realignment.
- Agrarian estimación-objetiva income (M130 apartado II) and actividad-económica
  directa income are indistinguishable in the current transaction classification,
  so they cannot share one aggregator without mis-routing.

## Implementation

Bounded mirrors are implemented in-tree and verified end to end. Modelo 130
casilla 02 "Gastos" is bound to the new `ledger_renta_gasto_aggregation` source,
the OUTGOING sibling of `ledger_renta_income_aggregation`, enrolled in the live
mesh with owned/lock-source bookkeeping and grounded identically to the income
side; an untagged expense is surfaced rather than gross-folded. The Modelo 303
régimen-general per-tier bases are a bounded mirror (the existing
`ledger_iva_aggregation` source with the `base_amount_sum` fact) being landed by a
peer.

The ADR-scale items below carry a decided mechanism (so the plan can execute
them) but are NOT coded in this session because they are blocked by active peer
work on Modelo 303 or require legal-schedule grounding that must not be invented:

- **M303 prorrata volumes — deferred on CORRECTNESS grounds (primary), peer file
  (secondary).** The regulated general prorrata is NOT a per-period volume sum:
  LIVA art. 104/104bis applies the PRIOR year's definitive percentage
  provisionally across the year's quarters and REGULARISES it in Q4 against the
  current year's actual annual volumes. A `ledger_iva_aggregation base_amount_sum`
  binding on the current quarter's volumes therefore computes neither the
  provisional percentage nor the annual-regularised one for any trader with
  exempt-without-right operations — it would ship a wrong deducible percentage,
  exactly the per-period approximation this ADR's Constraints and the
  codification-candidate rule forbid. The only case the per-period sum gets right
  is the fully-taxable trader (con-derecho = total → 100 percent), and for THAT
  case the correct, minimal fix is the prorrata-porcentaje formula's no-volume
  default (full right to deduct, LIVA art. 94), not a volume binding. A faithful
  prorrata mechanism needs the provisional-percentage carry + Q4 regularisation
  model (a cross-period structure akin to the IVA-wallet), which is genuine design,
  not a bounded mirror. Secondary blocker: the prorrata casillas live in an M303
  casilla file holding stale uncommitted peer work (last modified ~35h before this
  session — abandoned, not live, but still non-authored WIP not to be intermingled).

- **M303 recargo de equivalencia — IMPLEMENTED.** The research below de-risked
  the design (the existing retailer-side category is the wrong flow; a supplier-side
  recargo carrier was needed), and the supplier-side recargo was then built
  end-to-end: a non-negative `recargo_amount` field on the transaction model (the
  recargo a supplier charges on a repercutido sale), threaded through the IVA ledger
  aggregator into `IvaLedgerObservation.recargo_amount`; a new `recargo_amount_sum`
  fact on `ledger_iva_aggregation` that sums it; three M303 recargo cuota bindings
  routing by IVA tier (general 21% -> 5.2%, reducido 10% -> 1.4%, super-reducido 4%
  -> 0.5%) grounded in the already-bundled LIVA art-161 tier schedule
  (`liva-art-161:recargo-rate-*`, review_status reviewed); casillas 24/21/158 bound,
  added to the M303 manifest and construct with art-161 coverage; and a CLI input
  surface (`aeat app ledger add --recargo-amount`, command/patch model fields, action
  wiring, four-language locale). Regression tests prove the per-tier aggregation, the
  transaction roundtrip, and the no-recargo-is-zero case. The full
  registry+aggregation+ledger sweep shows only the two pre-existing peer-owned reds.
  Historical note (superseded design): Recargo de equivalencia is a SURCHARGE alongside IVA:
  a single sale carries both an IVA rate + cuota AND a recargo rate (0.5 / 1.0 /
  1.4 / 5.2 percent, LIVA art. 161) + recargo cuota. The current IVA model
  (`IvaCategory` + one `IvaRateKind` + one `iva_amount` per line) cannot represent
  this dual structure — adding the recargo tiers to `IvaRateKind` would be a wrong
  model (it conflates IVA rate tiers with surcharge tiers and still has nowhere to
  carry the recargo cuota distinct from the IVA cuota). The corrected decision:
  recargo requires a transaction-model change first (a recargo rate + recargo
  amount alongside the IVA fields, or a dedicated recargo classification), then a
  recargo aggregation source and the M303 recargo casilla binds. This is genuine
  domain-model design, NOT a rate-axis enum addition, and is BLOCKED additionally
  on the M303 peer file. The tier schedule must be grounded against the bundled
  corpus, never invented. DECISIVE scoping fact (verified): no transaction in the
  ledger model can carry recargo data today — recargo is missing an INPUT SURFACE,
  not only registry wiring, so even a complete model+aggregation+binds would
  resolve every recargo cuota to zero until operators can DECLARE recargo on a
  transaction (a classification / manual-entry / import-mapping surface). Recargo
  is therefore irreducibly a standalone feature spanning the confidential
  transaction model, its persistence roundtrip, a classification input surface, a
  recargo aggregation with a tier axis, the LIVA art-161 tier grounding, and the
  M303 binds (in peer-held files) — its own research→ADR→plan→execute cycle, not a
  tail sub-step of this feature. The M303 recargo casillas span BOTH peer-stale
  M303 casilla files, and recargo cuotas must aggregate (no peer-clean
  formula-default path exists, unlike prorrata), so there is no safe partial
  landing: model fields without binds would be a dormant shell
  (`no-dormant-source-resolvers`). RESEARCH RESOLVED (the decisive semantic
  finding): the existing `IvaCategory.RECARGO_EQUIVALENCIA` is the RETAILER's
  PURCHASE side — `_iva_ledger.py` places it in `_NON_DECLARABLE_IVA_CATEGORIES`
  ("a cost for the retailer, settled via the supplier") and `_preflight.py` flags
  recargo on a non-retailer as `ANOMALY_RECARGO_ON_NON_RETAILER`. The M303 recargo
  cuota casillas, however, are declared by the SUPPLIER who CHARGES recargo on
  sales to recargo-regime retailers — a SUPPLIER-SIDE flow that does not exist in
  the taxonomy at all. Reusing the existing retailer-side, non-declarable category
  to feed the M303 recargo cuotas would aggregate the wrong economic flow and ship
  a wrong M303 recargo figure (`aeat-safety-legal-gates` / no wrong regulated
  numbers). Recargo therefore requires a new SUPPLIER-SIDE recargo-charged-on-sale
  classification (distinct from the existing retailer-cost category), its input
  surface, the recargo amount carrier, the art-161 tier mapping, and the M303
  binds — a dedicated research→ADR→plan→execute feature. This is the research the
  goal mandates, now performed; its output is that recargo cannot be a registry
  gap-fill without modelling the supplier-side flow first.

- **M100 annual actividad-económica income — IMPLEMENTED (the disentanglement
  fear was disproven).** Casilla 0171 "Ingresos de explotación" was manual and a
  genuine silent zero for a direct M100 filing (the only M130 to M100 relation
  carries pagos fraccionados, not income). The earlier worry that binding 0171
  would collide with the project verb was WRONG: the project verb calculates via
  the formula-runtime path (`calculate_registry_snapshot` with explicit inputs),
  not the bucket-aggregation path, so a bound 0171 still takes the verb's supplied
  rendimiento there while real filings aggregate it from the ledger. Implemented:
  an annual M100 income aggregator (full-ejercicio window, actividad eligibility,
  re-targeting the eligible observations to 0171), the `ledger_renta_income_aggregation`
  selector relaxed to admit M100/0171, the mesh resolver routed by modelo (M100
  annual vs M130 quarterly), and casilla 0171 bound with a grounded binding
  (LIRPF art. 27/28). The full registry+aggregation+modelo sweep showed ZERO new
  failures (3758 passed; only the two pre-existing peer-owned reds remain), so the
  M100-chain blast radius was a non-issue.

- **M390 reverse-charge/import — decided mechanism (corrected after
  investigation).** The earlier claim that the `reconciliacion-303` relation is
  the resultado carrier is WRONG: the M390 `cuota-devengada-total` /
  `cuota-deducible-total` use the LEDGER-aggregated cuotas, and the
  reconciliacion-303 casillas are a separate cross-check against the summed M303
  quarterly totals. Consequence: domestic reverse-charge is omitted from both
  totals and nets to zero (harmless to the resultado), but the IMPORT deducible
  cuota is omitted from the deducible total only, so the M390 annual result
  over-states the amount to pay for an importer. The corrected decision: add an
  M390 `ledger_iva_aggregation` import-deducible binding (a bounded mirror of the
  M303 import binding) so the annual deducible total includes imports, and add a
  reconciliation predicate that flags any divergence between the ledger total and
  the reconciliacion-303 total. Domestic reverse-charge stays out of the totals
  (net zero) for official-box exposure only.

- **M130 agrarian objetiva volume (casilla 08)** needs an agrarian-vs-directa
  classification axis the transaction model lacks; deferred until that axis
  exists. **M100 capital-income nets** are not bank-ledger flows and are out of
  ledger scope.

The M130 actividad-económica legal-grounding completion (adding the establishing
articles LIRPF art. 27/28/30 alongside the pago-fraccionado provision on casillas
01/02/03 and their bindings, with the construct covering the union) is a bounded,
peer-clean, corpus-grounded change executed in this feature's surface.

## Rationale

The research sweep showed that of the modelos whose cuotas aggregate from the
ledger, the standard IVA group (309, 322, 353, 369, 390) already carries no
silent base, M130 directa is now fully covered, and M303 régimen-general bases are
an in-flight bounded mirror. Every remaining candidate exceeds a bounded mirror by
the taxonomy's own test (new mechanism, period model, classification axis, or
official-form restructure). Shipping those as quick registry edits would either
ship wrong regulated numbers (prorrata, agrarian mis-routing) or a large unreviewed
official-form restructure (M100 income, box restructures), both of which the
taxonomy and the safety-and-legal-gates discipline forbid. Stopping at this ADR
preserves the verified-green state and routes the design work to where it can be
grounded and reviewed.

## Consequences

The cuota-without-base defect is closed for M130 directa and (via the peer) M303
régimen-general, and the full silent-zero surface is now enumerated and
classified rather than discovered ad hoc per filing. The deferred items remain
open: M303 prorrata still blocks a fully-taxable trader's export until its annual
mechanism lands, and M100 still under-declares actividad income until its annual
income aggregation lands. Those are now scoped decisions with named mechanisms
rather than latent silent zeros. The pitfall to guard against is a future agent
treating any of the deferred items as a bounded mirror and force-fitting a
per-period sum; the research and this ADR record why that is wrong.

## Codification candidates

- **Rule slug:** `silent-zero-base-must-aggregate-or-defer-to-adr`.
  **Rule:** A regulated base or volume casilla whose sibling cuota aggregates from
  the ledger must either aggregate from its grounded canonical ledger source
  (reusing an existing `ledger_*_aggregation` family and fact) or, when that
  exceeds a bounded mirror, be deferred to an ADR with a named mechanism — never
  left to resolve silently to zero and never force-fitted into a wrong per-period
  approximation.
