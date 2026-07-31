---
tags:
  - '#adr'
  - '#counterpart-source-provider'
date: '2026-07-04'
modified: '2026-07-10'
body_hash: 'sha256:37a4a077c480344af308fb290b29e627a58f7c50edaca86dd06410517375b1e8'
related:
  - '[[2026-06-26-binding-resolver-contract-unification-adr]]'
  - '[[2026-06-26-binding-resolver-contract-unification-research]]'
  - '[[2026-06-26-binding-source-kind-taxonomy-unification-adr]]'
  - '[[2026-07-02-arch-remediation-source-kind-deferrals-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `counterpart-source-provider` adr: `counterpart source provider design and enrollment` | (**status:** `accepted`)

## Problem Statement

The counterpart (Modelo 347/349 operaciones-con-terceros / intracomunitarias)
aggregation surface is half-connected to the live calculate mesh, and the
stale connectivity plan step `W02.P05.S29` ("enroll counterpart aggregation
registry provider through source mesh;
`src/aeat/application/aggregation/_registry_provider.py`") names a module
that does not exist and a design that predates three later rulings. Current
ground truth:

- `CounterpartAggregationSourceResolver`
  (`src/aeat/application/aggregation/_counterpart.py`) is authored (step
  `P03.S10` of the binding-resolver contract unification) but NOT enrolled in
  `merge_source_resolutions`; it is repository-free (the caller supplies
  `CounterpartObservation` rows via the constructor) so on the live
  calculate path it has no observation source. Its production reach today is
  the shape-C per-modelo aggregate CLI verb (`aggregate_counterpart_347/349`
  via `application/aggregation/_service.py`), which the 2026-06-26 scope
  refinement adjudicated as CLI-reachable, not a dormant mesh resolver.
- Of the four `CounterpartSourceKind` members, `collectible_invoice` and
  `payable_invoice` are ALREADY ENROLLED: exclusively owned by
  `InvoiceCatalogueSourceResolver`, which reads the encrypted invoice
  catalogue for the only registry revision that declares them (M349
  `2020-y-siguientes`). `ledger_transaction` and `purchase_invoice_evidence`
  are `RESERVED_SOURCE_KINDS` (`_source_mesh.py`): no registry binding
  declares them and no resolver owns them.
- M347's sole revision (`2008-y-siguientes`) declares NO bindings at all,
  so the M347 counterpart value cannot silently blank on the calculate path
  (nothing on that path asks for it); the gap is registry build-out,
  not an unrouted resolver.
- The deferrals re-ratification ADR (register D5) kept the counterpart
  RESERVED tier but ruled a reserved kind cannot be consumed without
  promotion and that promotion requires its own grounded design ADR. The
  binding-resolver unification scoped the counterpart fold out to a grounded
  follow-up (task #36). This ADR is that grounded design: it decides the
  provider shape, the ownership split, the enrollment condition, and the
  fail-closed behaviour, and it supersedes the `S29` framing.

## Considerations

- Mesh ownership is exclusive: the merge guard adjudicates a binding claimed
  by two resolutions loudly. Enrolling `CounterpartAggregationSourceResolver`
  with its current `owned_sources` (all four counterpart kinds) collides
  with `InvoiceCatalogueSourceResolver` on
  `payable_invoice`/`collectible_invoice`.
- `calculation-source-canonical-mechanism`: one canonical mechanism per
  calculation type. M349 counterpart values already have one (the invoice
  catalogue projection). A second resolver producing the same M349 binding
  values would re-create the dual-modelling that rule exists to prevent.
- `no-dormant-source-resolvers`: every merged resolver is enrolled or
  deleted; every binding source kind is enrolled, explicitly deferred, or
  reserved-unconsumable, and `collect_unhandled_source_diagnostics` runs live
  so a declared-but-unrouted source surfaces an advisory, never a blank. The
  mesh gate (`test_source_mesh_missing_sources.py`) fails if a
  registry-declared kind classifies RESERVED.
- The unification plan's correctness doctrine: a folded source RESOLVES
  rather than advisory-defers, so an enrolled-but-wrong resolver
  under-declares silently, worse than a visible deferral. Every fold
  therefore carries a per-source correctness gate (the parked `S21` gate:
  live-mesh value equals prior `aggregate_counterpart_347/349` output
  exactly, on a 347 and a 349 fixture).
- Domain-side counterpart machinery already follows the per-family pattern
  (`registry-resolver-family-extraction`):
  `domain/calculations/registry/_counterpart_bindings.py` carries
  `CounterpartAggregationObservation`, `validate_counterpart_binding` in the
  one validator dispatch table, and `resolve_counterpart_binding_values`.
  Nothing new is needed on the domain side.
- The arch-remediation program's Wave-1 freeze bars NEW source kinds and
  resolver conventions until the bindings campaigns close; this decision
  must work entirely within the existing taxonomy and mesh contract.
- Counterpart evidence is sensitive financial data: any repository-backed
  observation provider must read the encrypted invoice catalogue and the
  bucket ledger through the existing secure-storage repositories
  (`sensitive-financial-data-secure-storage-only`).

## Considered options

- **Option A: enroll `CounterpartAggregationSourceResolver` now, as
  authored (all four owned kinds).** Rejected: collides with the invoice
  catalogue resolver's exclusive claim on `payable_invoice` /
  `collectible_invoice`; duplicates the canonical M349 mechanism; and with a
  constructor-empty observation set it resolves empty on the live path, an
  enrolled resolver whose value is structurally blank, the silent
  under-declaration shape the correctness doctrine forbids.
- **Option B: build the `_registry_provider.py` module of plan step `S29`
  as a generic registry-provider shim now, deferred-enrolled.** Rejected:
  the module name encodes no family (violates the per-family module shape);
  moving `ledger_transaction`/`purchase_invoice_evidence` from RESERVED to
  DEFERRED buys nothing today (no registry binding declares them, so the
  deferral advisory can never fire) while weakening the RESERVED tier's
  cannot-be-consumed-without-promotion gate that the deferrals ADR
  deliberately kept.
- **Option C: collapse the counterpart kinds; retire
  `ledger_transaction`/`purchase_invoice_evidence` and model all counterpart
  input as invoice-catalogue projections.** Rejected: M347 counterparty
  totals legitimately settle against bank-ledger movements that never have a
  catalogued invoice; retiring the kinds forfeits the taxonomy headroom the
  unification ADR deliberately preserved, and retirement has its own
  consumer-reconciliation cost
  (`retired-enum-members-need-consumer-reconciliation`) for no gain.
- **Option D (chosen): condition-triggered promotion with a narrowed,
  repository-backed provider.** Keep the RESERVED disposition today; define
  the provider design and the promotion condition now so the eventual
  enrollment is mechanical and gated, not improvised.

## Constraints

- No new `BindingSourceKind` member and no renamed stored token
  (behaviour-preserving-lift contract on the enum; Wave-1 freeze).
- `payable_invoice` / `collectible_invoice` remain exclusively owned by
  `InvoiceCatalogueSourceResolver`; the counterpart provider never claims
  them. `CounterpartAggregationSourceResolver.owned_sources` must be
  narrowed to `(ledger_transaction, purchase_invoice_evidence)` before any
  enrollment.
- Enrollment cannot precede a declaring registry binding: the disposition
  parity machinery (`build_binding_source_dispositions`) requires each kind
  in exactly one state, and the mesh gate fails a registry-declared kind
  with no live resolver. Conversely a declaring binding cannot land before
  the resolver enrolls. The two must co-land in one change.
- The M349 GROI / NIF-IVA declarable-readiness gates and the
  single-country-per-cohort refusal in `_counterpart.py` are load-bearing
  fail-closed behaviour and must survive the provider unchanged.
- Depends on stable parents: the mesh ownership contract and disposition
  registry (landed, bindings campaigns phase 2.1/2.4) and the counterpart
  registry family (landed). No frontier risk; every mechanism exists
  in-tree.

## Implementation

Taxonomy: no enum change. The counterpart provider's owned kinds are
exactly the two reserved members `BindingSourceKind.LEDGER_TRANSACTION`
and `BindingSourceKind.PURCHASE_INVOICE_EVIDENCE`. The
`CounterpartSourceKind` subset and `COUNTERPART_SOURCE_KINDS` stay as the
observation-level vocabulary (a `CounterpartObservation` may still carry
any of the four kinds when fed through the aggregate CLI verb).

Provider module: the repository-backed observation provider lands in the
existing family module `application/aggregation/_counterpart.py` (or a
`_counterpart_provider.py` sibling if size demands), NOT a generic
`_registry_provider.py`; the `S29` module path is superseded. The provider
projects, per `CalculationSourceContext`, the bucket ledger (via the
transaction repository, for `ledger_transaction`-sourced cohorts) and the
encrypted purchase-invoice evidence store (for
`purchase_invoice_evidence`) into `CounterpartObservation` rows, and feeds
the existing `CounterpartAggregationSourceResolver.resolve`, which already
routes through the domain family (`resolve_counterpart_binding_values`).

Enrollment condition (the promotion trigger): the provider enrolls in the
`merge_source_resolutions` tuple in the SAME change that lands the first
registry revision declaring a `ledger_transaction` or
`purchase_invoice_evidence` binding — in practice the M347 binding
build-out, or an operator filing need, whichever comes first. At that
moment the two kinds leave `RESERVED_SOURCE_KINDS` for ENROLLED in one
commit; they never pass through DEFERRED because no window exists in which
a declared binding lacks a resolver.

Correctness gate: the enrollment commit carries the parked `S21`-shape
gate, asserting the live-mesh resolution equals the prior
`aggregate_counterpart_347` / `aggregate_counterpart_349` output exactly
against a 347 and a 349 fixture, plus the M347 declaration-floor
(`M347_THRESHOLD_EUR`) behaviour on the binding consumer side.

Fail-closed behaviour: empty observation projection on a declaring
revision surfaces the standing no-silent advisory (the retenciones /
withholding precedent) while materialising explicit values through the
binding channel; storage degradation raises rather than resolving blank
(the invoice-resolver `_STORAGE_DEGRADATION_ERRORS` precedent);
conflicting counterparty-country cohorts keep raising; M349 readiness
gates keep blocking declarability. On enrollment the counterpart kinds
join the `deterministic_lock` tier of the caller-override precedence
ladder: bucket-owned deterministic sources reject caller overrides.

Until the trigger fires the disposition is unchanged: RESERVED, not
deferred, with the enrollment-status gate continuing to refuse
consumption; the shape-C aggregate CLI verb remains the operator surface
for counterpart preview, per the unification ADR's thin-projection ruling.

## Rationale

The decision extends the pattern that already governs every enrolled
source: mechanism ownership is declared data, one canonical resolver per
value, and a source is either live-and-proven or visibly not-live. Option
D is the only shape that satisfies all three gates simultaneously — no
ownership collision (narrowed `owned_sources`), no dual mechanism (M349
stays on the invoice catalogue), and no silent blank or dormant resolver
(co-landing makes the declared-implies-enrolled invariant hold by
construction, enforced mechanically by the mesh gate and the disposition
parity check). It also honours the deferrals ADR's explicit division of
labour: that ADR kept the RESERVED tier and demanded a grounded design ADR
before consumption; this is that ADR, and RESERVED remains the honest
disposition until a binding exists for the provider to serve.

## Consequences

- The `W02.P05.S29` blocker is adjudicated: the step is satisfied by this
  design, not by authoring `_registry_provider.py`; the connectivity plan
  step should be closed against this ADR (per
  `plan-closure-requires-exec-records`, with the close note naming this
  decision). Binding-resolver steps `S20`/`S21` inherit their gate shape
  from here when task #36 acts.
- M347 calculate-path support is honestly sequenced: registry casilla /
  binding build-out first, provider enrollment co-landing — no interim
  half-live state to audit around.
- `CounterpartAggregationSourceResolver.owned_sources` narrowing is a small
  pre-enrollment code change (plus its test sweep) that must not be
  forgotten; until it lands the resolver remains unenrollable. This is the
  cost of having authored `S10` before the #36 grounding.
- The two reserved kinds stay unconsumable indefinitely if M347 build-out
  never happens — accepted; the aggregate CLI verb keeps serving the
  operator need, and the swarm-audit cadence re-reads the RESERVED tier.
- A future third counterpart-shaped modelo enrolls under the same provider
  by declaring bindings with the existing kinds — no new mechanism, per the
  canonical-mechanism rule.
