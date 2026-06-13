---
tags:
  - '#adr'
  - '#modelo-multiyear-renta-353-grupo-aggregation'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-353-grupo-aggregation-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - '[[2026-06-04-modelo-multiyear-renta-research]]'
---

# `modelo-multiyear-renta-353-grupo-aggregation` adr: `353 grupo-entidades monthly aggregation mechanism` | (**status:** `accepted`)

## Problem Statement

The foundational authorization-gate ADR mandates that every modelo enroll through
a ≥2-renta end-to-end test before its backend is treated as functional. The IVA
*grupo de entidades* pair — Modelo 322 (modelo individual, one filed per group
member, monthly) and Modelo 353 (modelo agregado, filed by the entidad dominante,
monthly) — cannot be enrolled today because the aggregation that defines the
pair's relationship does not exist in the registry, and the binding machinery that
would express it is structurally unable to.

353 must equal, each month, the sum of its members' 322 result casillas:
`353[M].resultado = Σ member-322[M].resultado` across `iva.cuota-devengada-total`,
`iva.cuota-deducible-total`, and `iva.resultado-regimen-general` (the three result
casillas both modelos share identically — research F1). This is the **monthly,
cross-MEMBER** analogue of the already-shipped 390←303 reconciliation, which is
**annual, cross-PERIOD, single-filer**. The 390 precedent uses
`source = "previous_filing"` bindings; cloning that shape is the obvious starting
point (research F2).

But the existing `previous_filing` machinery is single-filer by construction. The
selector `_PreviousModeloSelector` carries no member / declarant axis (research
F3), the resolver hard-rejects more than one matching observation with a
`len(matches) != 1` guard (research F4), and the observation envelope
`RegistryModeloObservation` carries no NIF / member identity, so two members'
322s for the same modelo+year+period are indistinguishable duplicates (research
F5). Cross-member aggregation is therefore blocked three ways. **This is the only
mechanism in the entire multi-year-renta campaign that requires a registry-schema
extension** — every sibling mechanism (the A4 income-tax prior-year hooks, the A3
720 baseline) reuses existing schema fields. That singularity must be stated
prominently so the plan budgets the schema change and the swarm does not assume a
pure registry-authoring task.

A second, independent axis — the group's cross-renta month-boundary carry (saldo a
compensar from mes 12/N to mes 01/N+1) — does NOT need new code: it reuses the
already-tested monthly period wrap (research F7).

## Considerations

- **Two axes, kept strictly separate (research F9).** Axis 1 is cross-MEMBER,
  same month, and is the gap needing the schema extension. Axis 2 is cross-RENTA,
  month boundary, and is satisfied by existing tested machinery. Conflating them
  would over-scope the schema work.
- **Identical source/target casilla shape (research F1).** Because 322 and 353
  declare the same three result-casilla ids, the aggregation is a same-shape sum,
  exactly like 390←303. No casilla remapping is needed; only the per-member fan-in
  is novel.
- **A per-member precedent already exists (research F6).** Modelo 184's
  `atribucion_member` bindings select per-member rows via a free-form
  `grouping = "per_atribucion_member"` selector string (NOT a `RowSetGroupingKind`
  enum value — that enum has only `WITHHOLDING / RELATED_PARTY / FOREIGN_ASSET /
  ATRIBUCION / REFUND`). The 184 path pairs that grouping axis with a member-keyed
  `AtributionMemberObservation` carrying `member_tax_id`. This is the template to
  mirror, not invent.
- **Strict-frozen-forbid models everywhere (research F3, F5).** Both the selector
  and the observation are `ConfigDict(strict=True, frozen=True, extra="forbid")`.
  A new axis cannot be smuggled through `extra`; it must be an explicit declared
  field. This makes the extension surface small, auditable, and impossible to
  shadow.
- **Architecture boundaries.** `RowSetGroupingKind` and any new closed value set
  live in `core/` per the core-authority ADR. The registry TOML stays free-form;
  the loader hydrates the typed selector at the boundary. No new CLI root verb, no
  new module root.
- **Legal grounding must resolve in-corpus (research F8).** The grupo-de-entidades
  articles cited by the coordinator scratch (`art-163-sexies / -quinquies /
  -nonies`) do NOT exist as corpus files. The resolvable refs are
  `orden-eha-3434-2007:art-1` (322), `:art-2` (353), `:art-8` (monthly cadence),
  plus the standard `ley-37-1992:art-88 / art-92 / art-84` and
  `rd-1624-1992:art-71` already on both modelos' casillas. The new bindings MUST
  cite only from this set.

## Constraints

- **One small schema extension is unavoidable and is the campaign's only one.**
  The cross-member fan-in cannot be expressed with current fields. This ADR scopes
  that extension; the plan must budget it as code work, not registry authoring.
- **The `!= 1` resolver guard is load-bearing for every other previous_filing
  binding.** It is the contract that catches a missing or duplicated prior filing
  (390←303 relies on it). The extension MUST NOT weaken that guard for the
  single-filer case; it may only relax it on the explicit opt-in path where the
  new grouping axis is present. A blanket relaxation would silently mask
  duplicate-filing bugs across the whole previous_filing surface.
- **No public AEAT grupo workbook exists (research F9).** There is no external
  numeric oracle for the aggregated figures, so the enrollment test asserts
  structure / wiring / provenance / the cross-member sum identity, per the
  no-tautological-calculation-tests discipline. The test must NOT hand-compute a
  figure and assert the engine reproduces it.
- **Depends on the foundational gate landing first.** The recorder and the
  `authorization.toml` manifest from the foundational ADR are the enrollment
  surface this mechanism plugs into; this ADR assumes that spine exists.

## Implementation

A two-part design, one part per axis.

**Part 1 — cross-member fan-in (the schema extension).** Mirror the 184
per-member precedent on the `previous_filing` path:

- Extend `_PreviousModeloSelector` with one optional declared field,
  `grouping: Literal["per_grupo_member"] | None = None` (a closed value set; the
  Literal is the small typed extension, kept in the schema module next to the
  selector, with the canonical string also enrolled where the project keeps its
  grouping vocabulary). Absent `grouping` preserves today's exact single-filer
  behaviour bit-for-bit.
- Give the observation a member identity. The minimal, boundary-respecting move is
  to let the resolver enumerate multiple matches **only when** the binding's
  selector declares `grouping = "per_grupo_member"`: in that branch the resolver
  collects every observation matching `(modelo, filing_year, period)`, reads the
  requested `source_casillas` from each, and sums across members via the existing
  `aggregation = { op = "sum" }`. The `len(matches) != 1` guard stays exactly as
  is on the default (no-grouping) path, so 390←303 and every other single-filer
  binding are untouched. Member distinctness is carried by the observation's
  identity (each member's 322 is a distinct `RegistryModeloObservation` instance
  tagged with the member NIF on the enrollment side); the resolver does not need
  the NIF to sum, only to enumerate, which removes the need to widen the frozen
  observation's matching key.
- Author three `source = "previous_filing"` bindings on 353, cloning the 390
  prev-303 trio: `modelo-353-prev-322-cuota-devengada-total`,
  `-cuota-deducible-total`, `-resultado-regimen-general`. Each selector reads
  `{ source_modelo = "322", filing_year_delta = 0, period = "<mes>",
  grouping = "per_grupo_member", source_casillas = ["iva.<...>"] }` with
  `aggregation = { op = "sum" }`. Legal refs drawn from the resolvable set
  (`orden-eha-3434-2007:art-2`, `ley-37-1992:art-88 / art-92`,
  `rd-1624-1992:art-71`). Surface each as a bound casilla on 353 so the aggregate
  appears in `engine_result.values` with full provenance.

**Part 2 — cross-renta month-boundary carry (no new code).** Model the group's
saldo a compensar carry on the 353 **aggregate** (never on a member 322) as a
relation/binding using `source_period_offset_from_target = -1`. For mes 01 the
existing `_derive_offset_source_anchor` already returns `(-1, "12")` — month 12 of
the prior year — and this is the tested wrap (research F7). The carry rides
machinery that is already green; the only authoring is the relation declaration on
353.

**Enrollment test.** Two members file 322 for mes 12/N and mes 01/N+1; the entidad
dominante files 353 for both months. The test (cloning the real-SQLite,
real-authority, real-resolver shape of `test_modelo_130_carry_forward_continuity`)
asserts: Inv1 (cross-member) `353[12/N].resultado == Σ member-322[12/N].resultado`
for each of the three result casillas; Inv2 (cross-renta) the group saldo at
12/N carries into 353 01/N+1 via the monthly wrap. Spanning N and N+1 satisfies the
foundational gate's ≥2-distinct-renta-years requirement, and the recorder observes
both years.

## Rationale

Approach (a) — the `per_grupo_member` grouping axis with an opt-in
enumerate-then-sum resolver branch — is recommended over approach (b)
(group-as-one-bucket) for three reasons grounded in the research.

First, **it has a working precedent**: 184's `atribucion_member` path already
expresses "fan out to N members and aggregate" through a free-form `grouping`
selector string paired with a member-keyed observation (research F6). Approach (a)
is that exact pattern transplanted onto the `previous_filing` path; approach (b)
would invent a new "stuff every member into one observation's `observations`
tuple" convention with no precedent and a confusing identity model (one
`RegistryModeloObservation` standing for many filers).

Second, **it preserves the load-bearing `!= 1` guard** (research F4, constraints).
Because the multi-match branch is gated on the explicit `grouping` opt-in, every
existing single-filer binding keeps its duplicate-detection contract unchanged.
Approach (b) would either need the same opt-in anyway, or would relax matching
globally — the latter silently weakening 390←303's safety net.

Third, **it keeps the schema extension genuinely small** (research F3): one
optional `Literal`-typed field on an already-`extra="forbid"` model, plus a
guarded resolver branch. The frozen observation's matching key does not widen,
because the resolver sums by enumeration, not by NIF lookup. Approach (b) by
contrast pushes complexity into the observation envelope (a member-keyed internal
map) and into every consumer that reads `casilla_values`.

The cross-renta carry reuses tested code precisely because the research proved the
monthly wrap already returns `(-1, "12")` (research F7); re-deriving it would be
redundant risk.

The legal refs are drawn from the corpus-resolvable set (research F8) rather than
the scratch's `art-163-sexies`, so the new bindings will not introduce dangling
legal references that the grounding gates would (correctly) reject.

## Consequences

- **The pair becomes enrollable.** Once Part 1 lands, 353 and 322 can pass a real
  ≥2-renta cross-member + cross-renta test and be authorized in
  `authorization.toml` against recorded evidence.
- **One schema field, broadly reusable.** The `per_grupo_member` grouping axis is
  the first cross-filer aggregation primitive on the `previous_filing` path. Any
  future grupo / consolidación aggregation (and the conceptual cousin in
  consolidated IS filings) can reuse it rather than re-deriving fan-in. This is the
  campaign's single schema investment and it compounds.
- **Risk is concentrated and contained.** Because the multi-match branch is opt-in,
  the blast radius of the resolver change is exactly the bindings that declare the
  new grouping — zero impact on the ~dozen existing single-filer previous_filing
  bindings. The structural audit swarm should still re-run the full
  previous_filing suite to confirm the default path is byte-identical.
- **Member identity lives on the enrollment side, not the matching key.** Tagging
  each member 322 observation with its NIF at enrollment is an enrollment-fixture
  responsibility; the resolver stays NIF-agnostic. The pitfall to watch is an
  enrollment that accidentally files two observations for the SAME member+month —
  the sum would double-count. The enrollment test should assert member-count ==
  expected to guard this, since the resolver intentionally no longer enforces
  uniqueness on this path.
- **No numeric oracle.** The enrollment test proves the sum identity and provenance
  flow, not an externally-sourced figure. That is the correct ceiling given no
  public grupo workbook exists; a future live-oracle replay could strengthen it.

This ADR is a mechanism-specific ADR co-backing the `modelo-multiyear-renta` plan
alongside the foundational gate ADR. It owns the 353←322 cross-member aggregation
decision and the campaign's sole schema extension; it does not restate the gate
spine.

## Codification candidates

- **Rule slug:** `previous-filing-multimatch-requires-explicit-grouping`.
  **Rule:** The `previous_filing` resolver's `len(matches) == 1` uniqueness guard
  may only be relaxed on a binding that explicitly declares a cross-filer
  `grouping` axis; no change may relax duplicate-filing detection for the default
  single-filer path.
