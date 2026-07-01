---
tags:
  - '#adr'
  - '#modelo-151-beckham-source-scope'
date: '2026-07-01'
modified: '2026-07-01'
related:
  - '[[2026-06-02-modelo-multiyear-renta-151-beckham-adr]]'
  - '[[2026-05-27-source-jurisdiction-axis-adr]]'
  - '[[2026-05-28-source-jurisdiction-axis-research]]'
  - '[[2026-05-27-non-resident-irnr-axis-adr]]'
  - '[[2026-05-27-m210-irnr-full-engine-adr]]'
---

# `modelo-151-beckham-source-scope` adr: `Impatriado Spanish-source base scoping for Modelo 151` | (**status:** `proposed`)

## Problem Statement

GitHub issue #527 (David round-10, `2026-05-27-david-cli-testimonial-audit`)
reports that an impatriado under the regimen especial del art. 93 LIRPF (Ley
Beckham, Ley 26/2014) is taxed only on Spanish-source income, yet the profile
and calculation engine "have no source-scope axis distinguishing Spanish-source
from worldwide income". Recomputed against HEAD, the issue is now partially
superseded: three of the four axes the audit named have since landed, but its
load-bearing residue is open, so the record must state exactly what remains.

Already shipped (do not re-decide):

- The profile eligibility axis exists: `IrpfSpecialRegime` (`general` /
  `impatriado`) plus `special_regime_start_date` on `TaxpayerProfile`
  (`2026-05-27-non-resident-irnr-axis-adr`, and the 151 window ADR).
- The per-row source axis exists: `Transaction.source_jurisdiction`
  (ISO 3166-1 alpha-2) with a CLI create-boundary gate that refuses
  `impatriado` (and non-resident IRNR) profiles that omit
  `--source-jurisdiction`, anchored to art. 93.5
  (`2026-05-27-source-jurisdiction-axis-adr`).
- The form routing exists: `derive_modelo_applicability` suppresses Modelo
  100 (and the M720 obligation) for an in-window impatriado and routes the annual
  IRPF obligation to Modelo 151.
- The M151 flat-rate engine exists and is corpus-grounded: the general escala
  24 percent up to 600.000 euros / 47 percent on the excess (art. 93.2.e.1) is
  computed by `lookup_bracket` over a two-band `bracket_table`, minus retenciones
  (`2026-06-02-modelo-multiyear-renta-151-beckham-adr`), with the bands verbatim
  in the bundled `ley-35-2006-art-93.html`.

The open residue: the M151 base casilla `impatriado.base-liquidable-general` is
`input_kind = "manual"`. The `source_jurisdiction` axis the operator was forced
to declare at ledger-add time is never consumed to compute the impatriado base.
There is no aggregation path that admits only Spanish-source ledger income into
the Beckham base and segregates foreign-source income (art. 93.5). The declared
axis is captured but inert for the one modelo whose base is legally source-scoped;
the impatriado must hand-compute the Spanish-source base with zero engine support,
and a foreign-source row the operator wrongly includes produces no signal. This
ADR decides how the M151 base becomes source-scoped from the ledger. It does not
restate the 151 engine, the window gate, or the profile axis; those are owned by
the prior ADRs and are treated here as fixed context.

## Considerations

- The base is manual today, so there is nothing to filter yet: the decision is
  first whether to bind it to the ledger at all. The M130/M100 income classifier
  (`_classify_income_transaction` in `_renta_income_ledger.py`) is the established
  ledger-to-casilla aggregation shape; it already threads `source_jurisdiction`
  onto `RentaIncomeObservation` for provenance but deliberately does NOT gate on
  it, because LIRPF art. 8 admits worldwide income into the resident-IRPF base.
  M151 is the mirror-image regime: art. 93 taxes a resident by IRNR scope rules,
  so its base admits only Spanish-source. The axis exists on the row; only the
  base-side consumer is missing.
- The Beckham base is primarily rendimientos del trabajo (nomina), which the M130
  classifier explicitly routes OUT (the `TRABAJO_INCOME` issue reason keeps
  trabajo income off the actividad-economica casillas). So the M151 base cannot be
  a thin reuse of the M130 income pipeline: it needs an income-category scope that
  admits trabajo income, precisely the class the M130 pipeline rejects. The two
  pipelines are complementary, not shared.
- `source_jurisdiction` is nullable (grandfathered). Pre-axis catalogues and the
  resident-general default carry `None`/`ES`. The impatriado CLI gate refuses a new
  row without the flag, but an aggregation that treated `None` as "assume ES" would
  silently re-admit an unattributed row into a base that must exclude
  foreign-source. The aggregation must treat an unresolved jurisdiction on an
  impatriado catalogue as a surfaced issue, not a silent ES coercion
  (`no-silent-under-declaration`).
- The savings escala (art. 93.2.e.2, the parte del ahorro at art. 25.1.f TRLIRNR)
  is out of scope of the shipped engine and is not corpus-grounded. The base
  casilla is already labelled "excluida la parte del ahorro". A source-scoped
  savings base is a separate, corpus-first build and must not be smuggled into
  this decision.
- Architecture boundaries. No new CLI root, no new profile field (the `IMPATRIADO`
  axis is canonical), typed issue reasons on a `StrEnum`, locale text only through
  the locale CLI, and every base value carries `legal_refs`/`source_refs`. The
  classifier-vs-predicate axis was already analysed in
  `2026-05-28-source-jurisdiction-axis-research` (recommendation: classifier); that
  analysis is adopted here, not repeated.

## Considered options

- Option A: M151 base ledger-binding with an aggregation-time source-scope
  classifier (CHOSEN). Turn `impatriado.base-liquidable-general` into a
  ledger-aggregated casilla fed by a dedicated impatriado income classifier that
  admits only `source_jurisdiction == ES` (art. 8 universal base does not apply;
  art. 93 scope does), admits trabajo income (unlike M130), and emits a typed
  `BECKHAM_FOREIGN_SOURCE_SEGREGATED` provenance issue for each foreign-source or
  jurisdiction-unresolved row. Pattern-parity with `_classify_income_transaction`;
  the declared axis finally does work. Kept: the only option that consumes the axis
  the operator was compelled to declare, keeps foreign rows visible for audit, and
  localises the regulatory branch to one grounded site.
- Option B: an M100 source-scoping gate. Add a Spanish-source filter to the
  M100/M130 resident-IRPF aggregation for impatriado profiles. Rejected: it
  contradicts art. 8 for every resident-general filer (the source-jurisdiction ADR
  wrote an anti-tautology test specifically to fail this mutation), and it is moot
  for impatriados because M100 is already suppressed and routed to M151. The
  scoping belongs on the form the taxpayer actually files, not on the suppressed
  one.
- Option C: reuse the M210 IRNR aggregation code path directly. M210 also taxes
  Spanish-source-only, so route impatriado income through the IRNR engine base
  aggregation. Rejected: the regimes are regulatorily distinct: art. 93.5 (Beckham
  segregation on an IRPF resident) versus TRLIRNR art. 25 (a true non-resident),
  with different base casillas, different escalas, and a different refusal anchor;
  the source-jurisdiction research already treated M210 and M151 as
  "regulatory-distinct bindings (Art 25.1 vs Art 93.5)". The M210 pattern (a
  Spanish-source-only per-row scope) is the structural template and is reused; the
  M210 code path is not.
- Option D: a registry-authored `source_jurisdiction_must_equal_es` verification
  predicate instead of a classifier. Rejected on the evidence already assembled in
  `2026-05-28-source-jurisdiction-axis-research`: a predicate produces an opaque
  aggregate BLOCKING finding with no per-row provenance, is brittle to DAG-misread
  false refusals (the S398 rollback is the worked instance), and the rule here is
  intrinsically per-row. The classifier is the loud, per-row, audit-preserving
  shape.
- Option E: a new `fiscal_regime: general|beckham` profile field. Rejected: it
  duplicates the validated `IrpfSpecialRegime.IMPATRIADO` axis and forks the
  regime-clock source of truth, the same boundary regression the 151 engine ADR
  rejected for `beckham_option_year`, and the standing codification candidate
  `regime-window-is-eligibility-gate-not-compute-input`.
- Option F: status quo, keep the base manual and rely on the CLI gate. Rejected:
  it leaves the compelled axis inert, gives the impatriado no base computation, and
  provides no signal when a foreign-source row is wrongly included, a silent
  under/over-declaration surface the project rules forbid.

## Constraints

- Corpus-first for the segregation anchor. The 24/47 bands are grounded, but the
  segregation rule (art. 93.5, and the two-rule distinction the art-93 corpus note
  already records: the letra e tax versus the letra f retencion) must anchor the
  classifier `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue and the base binding
  `legal_refs`. Verify the anchor against the bundled `ley-35-2006-art-93.html`
  before authoring; do not introduce a hand-typed scope rule.
- Depends on stable, shipped parents. This ADR relies on the source-jurisdiction
  axis (accepted, landed), the 151 engine (accepted, landed), and the M100
  suppression / M151 routing (landed). All three are green; no frontier or
  training-cutoff risk. The only unstable surface is this ADR own new classifier.
- Nullable-jurisdiction handling must fail loud, not default ES. On an impatriado
  catalogue a `None` `source_jurisdiction` is an unresolved provenance, not a
  resident-general ES default; the aggregation surfaces it as an issue.
- Savings escala is explicitly out of scope and blocked on a separate corpus
  ingest (art. 93.2.e.2 / art. 25.1.f TRLIRNR); this ADR scopes only the base
  liquidable general.
- No inter-year carry. As the 151 engine ADR established, the regimen has no BIN,
  no compensacion, no carryforward; the source-scoped base is a within-year
  aggregation only.

## Implementation

A high-level, multi-phase shape (not a plan). Phases are sequenced so the axis
becomes consumed incrementally and each phase is independently testable.

Phase 1: impatriado income classifier and base binding. Author a dedicated
impatriado income aggregation (sibling to `_renta_income_ledger.py`) whose per-row
classifier admits an INCOMING row into the impatriado base only when its
`source_jurisdiction` resolves to `ES` (art. 8 universal base does not apply;
art. 93 scope does), and emits a typed `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue,
carrying the transaction id, the rejected jurisdiction code, and the art. 93.5
anchor, for a foreign-source or unresolved-jurisdiction row. Wire the aggregated
Spanish-source total to `impatriado.base-liquidable-general` as a ledger `source`
binding, flipping the casilla from manual to ledger-bound. Register the new issue
reason on the shared issue-reason surface and scaffold its locale label across
en/es/ca/hu through the locale CLI. Anti-tautology coverage: an ES row enters the
base, a foreign row is segregated (mutate the jurisdiction and assert the base
drops and the issue fires), and a `None`-jurisdiction impatriado row surfaces the
issue rather than defaulting ES.

Phase 2: trabajo income scope. The Beckham base is predominantly rendimientos del
trabajo, which the M130 pipeline routes out via `TRABAJO_INCOME`. The impatriado
classifier must admit trabajo income into the base (the exact class M130 excludes),
so Phase 1 classifier owns a distinct income-category scope. Prove that a nomina
(`irpf_category = trabajo`) ES-source row feeds the M151 base while the same row is
still excluded from M130.

Phase 3 (deferred, corpus-first): savings escala. Ingest the art. 93.2.e.2 /
TRLIRNR art. 25.1.f savings-band schedule into the corpus, then add the
source-scoped base del ahorro and its escala. Blocked until the bands are grounded;
tracked as a follow-up, not part of the accept-to-implement scope of this ADR.

Phase 4 (optional): evidence and export parity. Bundle the segregated-row evidence
into the M151 revision and render the source-scope segregation on the workbook
export, at parity with the ledger-derived-evidence discipline the other modelos
follow.

The casilla/binding/grounding surface this implies:
`impatriado.base-liquidable-general` gains a ledger `source` binding scoped to ES;
a new `BECKHAM_FOREIGN_SOURCE_SEGREGATED` issue reason plus its four locale leaves;
base and issue both carry `ley-35-2006:art-93` and the art. 93.5 segregation
anchor, verified against `ley-35-2006-art-93.html`. No new profile field, no new
CLI root, no change to the 151 escala or the six-year window gate.

## Rationale

The classifier (Option A) is chosen because it is the only shape that makes the
`source_jurisdiction` axis do work on the one modelo whose base is legally
source-scoped: the operator is already compelled to declare the flag at ledger-add
time, and today that declaration is discarded. The classifier consumes it, keeps
foreign-source rows visible as typed provenance issues rather than silently dropped
or silently admitted, and follows the shipped `_classify_income_transaction`
template so the implementor and reviewer build against a known-good shape. The
predicate route (Option D) was already weighed and rejected in the
source-jurisdiction research for its opaque, per-row-blind, false-refusal-prone
failure mode (the S398 rollback); nothing has changed that calculus.

Rejecting the M100 gate (Option B) is forced by art. 8: the resident-IRPF base is
worldwide, and the source-jurisdiction ADR encoded that as a load-bearing
anti-tautology test. For impatriados specifically the gate is also moot, since M100
is already suppressed and routed to M151: the scoping must live on the form the
taxpayer files. Reusing the M210 code path (Option C) is rejected because art. 93.5
(a resident taxed by IRNR scope) and TRLIRNR art. 25 (a true non-resident) are
regulatorily distinct with different base casillas; the M210 Spanish-source-only
pattern is the template, and that pattern is what Phase 1 reuses. Keeping the
`IMPATRIADO` profile axis (rejecting Option E) preserves the single regime-clock
truth the 151 engine ADR established.

## Consequences

- The compelled axis finally pays off. An impatriado who imports a mixed ES/foreign
  ledger gets a computed Spanish-source base and an explicit, per-row, audit-visible
  list of the foreign-source amounts that were excluded, the exact art. 93.5
  segregation the CLI gate promised but the engine never delivered.
- A new aggregation surface to maintain. Phase 1 adds a second income classifier
  alongside the M130 one; the two must stay coherent on the trabajo-vs-actividad
  split. This is the per-modelo duplication cost the source-jurisdiction research
  accepted as small and mechanical, now realised.
- The base flips from manual to computed. Operators who previously typed the base
  liquidable general directly will see it derived from the ledger; the manual entry
  path is superseded, not preserved (no legacy dual path). This is a behaviour
  change for existing impatriado work-units and must be communicated in the phase
  that lands it.
- Nullable jurisdiction is now load-bearing on the impatriado path. Treating `None`
  as an issue rather than an ES default is the safe choice but will surface
  advisories on any impatriado catalogue holding pre-gate or imported rows without a
  jurisdiction; that is the correct honest signal, not a defect.
- Savings-base scope remains a visible gap. Until Phase 3 corpus ingest, the
  source-scoped base del ahorro is unmodelled; the base casilla "excluida la parte
  del ahorro" label keeps that honest, and the deferral is explicit rather than
  silent.
- Pathway opened. A grounded, per-row, ES-scoped income classifier is the template
  the eventual M210 IRNR base aggregation (still a manual-base engine) can follow,
  closing the symmetric non-resident gap the source-jurisdiction ADR also left
  deferred.

## Codification candidates

- Rule slug: `declared-source-axis-must-be-consumed-by-its-scoped-modelo`.
  Rule: When a per-row axis (e.g. `source_jurisdiction`) is compelled at the input
  boundary for a given regime, the modelo whose base that axis legally scopes MUST
  consume it in aggregation (admit in-scope rows, segregate out-of-scope rows as
  typed provenance issues); a compelled-but-inert axis is a silent
  under/over-declaration surface.
