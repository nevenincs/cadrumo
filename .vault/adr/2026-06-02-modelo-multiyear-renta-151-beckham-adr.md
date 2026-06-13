---
tags:
  - '#adr'
  - '#modelo-multiyear-renta-151-beckham'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-151-beckham-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - '[[2026-06-04-modelo-multiyear-renta-research]]'
---

# `modelo-multiyear-renta-151-beckham` adr: `151 Beckham flat-rate engine and six-year window gate` | (**status:** `accepted`)

## Problem Statement

Modelo 151 — the autoliquidación for taxpayers under the régimen especial de
impatriados (LIRPF Art. 93, "Ley Beckham") — has no calculation backend today:
it is an empty registry scaffold with no casillas, formulas, parameters, or
calculation-registry entry (research F1). The foundational authorization-gate ADR
mandates that every modelo enroll through a ≥2-renta end-to-end test before its
backend is treated as functional, so 151 is one of the engine-build modelos the
gate's sub-decision flags. This ADR decides what that engine is, how the régimen's
six-year time limit is modelled, what the cross-renta invariant is, and the
build's mandatory corpus-first sequencing.

The defining question is the régimen's six-year window: the régimen applies for
the option year and the five following, after which the taxpayer reverts to
general IRPF (Modelo 100). The decision is whether that window enters the cuota
computation or governs eligibility. It is an eligibility property — the flat rate
does not vary across the six years — so modelling it as a compute input would be
wrong. It must be a gate, and per the project's `no-silent-under-declaration`
discipline an out-of-window filing must be surfaced as an ADVISORY finding, not a
silent grant nor a hard refusal.

## Considerations

- **Small single-phase engine (research F4, F5).** Unlike the heavier 714
  Patrimonio build, 151 is one rate schedule applied to one base minus
  retenciones. The structural sibling is Modelo 210 IRNR (already shipped:
  base → tipo → `multiply` → cuota diferencial). 151 reuses that skeleton with a
  numeric two-band `bracket_table` + `lookup_bracket` instead of 210's enum-keyed
  `keyed_bracket_table`, because the Beckham rate is a numeric threshold schedule
  (€0→24%, €600,000→47%).
- **The bands fit the existing `BracketEntry` shape exactly (research F5).**
  Row 1 `[0, 600000)` `marginal_rate=0.24` `fixed_addition=0`; row 2 `[600000, ∞)`
  `marginal_rate=0.47` `fixed_addition=144000` (= 0.24 × 600000, derived from the
  lower band, not asserted independently). The documented evaluation
  `cuota = fixed_addition + marginal_rate × (base − lower_bound)` reproduces the
  Art. 93.2.a schedule.
- **The eligibility axis already exists (research F3).** `core/profile.py`
  carries `irpf_special_regime` (validated to `IrpfSpecialRegime`, whose only
  members are `GENERAL` and `IMPATRIADO`) and `irpf_special_regime_start_date`
  (validated ISO-8601). The `IMPATRIADO` member's docstring explicitly ties itself
  to Modelo 151 and states the six-year window is "triggered by the opt-in
  election date (`special_regime_start_date` on the profile)". No new profile
  field is needed; the scratch's proposed `beckham_option_year` would duplicate a
  validated axis and fork the régime-clock source of truth.
- **Corpus gap is a hard blocker (research F2).** `legal/irpf-impatriados.toml`
  grounds Art. 93, the six-year window ("y los cinco siguientes"), RIRPF
  Art. 113-120, and Orden EHA/2887/2008 — but NOT the 24%/47%/€600k bands of
  Art. 93.2.a. The anonymised `il`/`ilos` corpus tokens do not recover the
  figures. The bands must be ingested from BOE-A-2006-20764 before any formula is
  authored.
- **Architecture boundaries.** `IrpfSpecialRegime` already lives in a domain
  module as a closed StrEnum; the bracket parameter is registry TOML hydrated at
  the loader boundary; no new CLI root verb or module root. The advisory predicate
  follows the established `verification_predicate` shape.

## Constraints

- **Corpus-first sequencing is mandatory.** Authoring the cuota formula or the
  bracket parameter before the Art. 93.2.a bands are in the legal corpus would
  produce hand-typed, ungrounded brackets — a direct violation of the
  calculation-grounding and no-tautological-test rules. Phase A (band ingest from
  BOE-A-2006-20764) MUST precede Phase B (engine). This mirrors the A5 714 build's
  corpus-first constraint.
- **The window gate must stay ADVISORY, not BLOCKING.** A BLOCKING_RULE that
  refuses computation outside the window would contradict the foundational gate's
  ADVISORY-not-refusal posture (an existing engine computes and informs) and could
  wrongly refuse legitimate transition or late-filing scenarios. The advisory
  fires only on the suspicious shape (`filing_year > option_year + 5`), consistent
  with the Modelo 200 `implies_nonzero` precedent.
- **No inter-year value carry exists.** 151 has no BIN, no compensación, no
  carryforward. The cross-renta invariant is régime-clock continuity, not a sum;
  the build must not invent a value carry that the régimen does not have.
- **Depends on the foundational gate spine.** The recorder and
  `authorization.toml` manifest are the enrollment surface; this ADR assumes they
  exist (the foundational ADR's sub-decision already budgets 151 as engine-build).

## Implementation

Two phases, sequenced.

**Phase A — corpus population (no calc).** Ingest the Art. 93.2.a flat-band
schedule (24% to €600,000, 47% on the excess) from BOE-A-2006-20764 into the
legal corpus and extend `legal/irpf-impatriados.toml` so the rate figures carry a
real `corpus_ref` and `legal_refs` anchor. No formula is authored in this phase.
This unblocks grounded bracket authoring.

**Phase B — the engine.** Author the 151 registry under revision
`2024-y-siguientes`:
- Casillas for the base (rendimientos del trabajo + Spanish-source income taxed
  per IRNR rules), the retenciones input, the cuota íntegra, and the cuota
  diferencial, each carrying `legal_refs`/`source_refs` provenance.
- A `bracket_table` parameter holding the two grounded Beckham bands (F5), dated
  `valid_from` for the ejercicio, citing `ley-35-2006:art-93`.
- A cuota-íntegra formula `cuota = lookup_bracket(base, <bracket-param>)` and a
  cuota-diferencial formula `cuota_integra − retenciones`, mirroring the 210
  base→tipo→cuota→diferencial chain (F4).
- An application_link wiring 151 into `calculate_registry_snapshot` (the consumer
  210 already uses), so the engine runs through the validated authority.

**The six-year window gate.** Model eligibility as a profile-driven predicate, not
a formula term (F6). Applicability: `profile.irpf_special_regime == IMPATRIADO`.
The option year is `irpf_special_regime_start_date`'s year. An ADVISORY
`verification_predicate` fires when `filing_year > option_year + 5`, surfacing a
non-blocking WARNING that the régimen window has lapsed, grounded with
`ley-35-2006:art-93`. Inside the window the engine computes normally. This is the
Modelo 200 `implies_nonzero` advisory shape transplanted to a time-window
predicate.

**Cross-renta enrollment.** Model régime-clock continuity (F7) as a
`previous_filing`-style binding with `filing_year_delta = -1` reading the prior
year's option-year context to confirm the régimen persists with the same option
year (the Modelo 130 prior-period read is the wiring precedent). The ≥2-renta
enrollment test (cloning the real-SQLite/real-authority/real-resolver shape used
across the carry tests) drives two consecutive in-window ejercicios for an
`IMPATRIADO` profile: it asserts (i) cuota = `lookup_bracket(base) − retenciones`
each year against the BOE-grounded bands; (ii) the continuity hook confirms both
years lie in `[option_year, option_year+5]` with one fixed option year; (iii) a
third scenario at `option_year + 6` surfaces the ADVISORY window-lapsed finding
rather than a silent grant. Spanning N and N+1 satisfies the ≥2-distinct-renta
contract and the recorder observes both years.

## Rationale

A flat two-band `bracket_table` with `lookup_bracket` is chosen over an
enum-keyed table because the Beckham rate is a numeric threshold schedule, not a
categorical dispatch — the `BracketEntry`'s `lower_bound`/`fixed_addition`/
`marginal_rate` shape reproduces Art. 93.2.a exactly (research F5), and reusing
the shipped 210 skeleton (research F4) keeps the engine small and proven rather
than bespoke.

Keying the gate on the existing `irpf_special_regime`/`irpf_special_regime_start_date`
profile fields (research F3) is chosen over a new `beckham_option_year` field
because the `IMPATRIADO` enum member is already the canonical Modelo-151 axis and
its docstring already designates `special_regime_start_date` as the window
trigger. Adding a parallel field would fork the régime-clock truth and duplicate
validated state — a boundary regression.

Modelling the window as an ADVISORY gate rather than a compute input or a hard
refusal is grounded in two project disciplines: the flat rate is window-invariant
so the window cannot be a formula term (it would be inert at best, wrong at
worst), and `no-silent-under-declaration` plus the foundational gate's
ADVISORY-not-refusal posture together require a non-blocking signal on the
suspicious out-of-window shape rather than either silence or a refusal that breaks
legitimate edge filings.

Corpus-first sequencing is non-negotiable under the calculation-grounding rule: a
hand-typed 24%/47% bracket with no `corpus_ref` is exactly the ungrounded
constant the no-tautological-test discipline forbids. Phase A removes that risk
before Phase B can author a single bracket.

## Consequences

- **151 becomes enrollable as a small, grounded engine.** Once Phase A lands, the
  engine is a thin reuse of the 210 skeleton and can pass a real ≥2-renta test,
  then be authorized in `authorization.toml` against recorded evidence.
- **The régime-clock gate is reusable.** A profile-driven, option-year-anchored
  ADVISORY window predicate is a pattern other time-limited régimes (and the 720
  / 721 re-declaration advisories) share in spirit; expressing it as a
  `verification_predicate` keeps it consistent with the existing advisory surface.
- **No profile-model change.** Because eligibility rides existing validated fields,
  the build touches the registry and the legal corpus only — no widening of the
  core profile aggregate.
- **Corpus debt is surfaced, not hidden.** The build cannot start its engine phase
  until the BOE band ingest completes; the `authorized N/30` line will visibly lag
  151 until Phase A lands. That visible lag is the correct honest signal, not a
  defect to paper over.
- **Pitfall — the derived top-band `fixed_addition`.** The €144,000 accumulation
  on the second bracket is derived from the first band (0.24 × 600,000). If the
  ingested figures ever change, that derivation must be recomputed, not left
  stale. The bracket parameter's grounding and the enrollment test's
  statute-checked cuota guard against a stale `fixed_addition`.

This ADR is a mechanism-specific ADR co-backing the `modelo-multiyear-renta` plan
alongside the foundational gate ADR. It owns the 151 engine and its window gate;
it does not restate the gate spine, and it corrects the foundational ADR's
implicit "new profile field" assumption to "reuse the existing `IMPATRIADO` axis".

## Codification candidates

- **Rule slug:** `regime-window-is-eligibility-gate-not-compute-input`.
  **Rule:** A tax régime's time-limited eligibility window (e.g. the Beckham
  six-year window) must be modelled as a profile-driven ADVISORY eligibility
  predicate anchored to an existing régime-start profile field, never as a term in
  the cuota formula and never as a new parallel option-year field.
