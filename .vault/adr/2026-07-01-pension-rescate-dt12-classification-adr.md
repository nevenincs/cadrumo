---
tags:
  - '#adr'
  - '#pension-rescate-dt12-classification'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:773d3ff7dd33290779acc7e0d73838c0a0070db8502a783e6d8263aa67a22dfe'
related:
  - '[[2026-07-01-pension-rescate-dt12-classification-research]]'
  - '[[2026-05-27-dt-12-rescate-plan-pensiones-adr]]'
  - '[[2026-06-15-art20-trabajo-reduccion-compute-adr]]'
---

# `pension-rescate-dt12-classification` adr: `DT 12a rescate-type axis and apartado-4 time-window eligibility` | (**status:** `accepted`)

## Problem Statement

The DT 12a LIRPF 40% reduccion on a lump-sum plan-de-pensiones capital rescate is
already computed and injected: `compute_dt12_reduccion_plan_pensiones` applies
`pre_2007 / totales * gross_rescate * 0.40` and the three `work calculate` shortcut
flags feed it (prior ADR `2026-05-27-dt-12-rescate-plan-pensiones-adr`). Two guided
classification concerns remain unmodelled. First, there is no rescate-type axis: the
regime differs in guidance between a total rescate (whole capital at once) and a parcial
rescate (staged withdrawals). Second, and materially, DT 12a apartado 4 (added by Ley
26/2014, `BOE-A-2014-12327`) restricts the whole transitional regime -- and therefore the
40% reduccion -- to prestaciones percibidas within a time window measured from the
contingencia year. Today the 40% applies unconditionally whenever the split is supplied,
so an out-of-window rescate receives a reduccion the law no longer grants: a silent
over-reduction, i.e. under-declaration of tax that the verify gate cannot surface. Issue
#544 (P1) requires the guided classification channel that closes this gap.

## Considerations

- The contingencia-year and rescate-year facts exist only at the calculate-shortcut
  moment; they are neither casillas nor profile facts, and the prior ADR deliberately
  refused to persist DT12 election facts on the profile (research F4). The verify-time
  advisory collectors read only `casilla_values`, so they cannot evaluate the window.
  The gate must therefore live on the calculate-shortcut path, beside the existing
  injection.
- Two precedents bound the posture. Art. 20 (`2026-06-15-art20-trabajo-reduccion-compute-adr`)
  keeps its finding ADVISORY because its eligibility gate is a fact-uncertain
  cross-section aggregate the engine cannot evaluate. The DT12 apartado-4 window, by
  contrast, is certain date arithmetic over two declared years -- so once the operator
  declares the years, the determination is unambiguous, unlike art. 20.
- `no-silent-under-declaration` treats an over-reduction as under-declaration of tax:
  applying the 40% to a proven out-of-window rescate and only warning would let the
  verify gate still grant `verified_complete` on an over-reduced return.
- `aeat-safety-legal-gates` requires grounding in BOE/AEAT; the window rule and the 40%
  rate are grounded against the bundled consolidated LIRPF (research F5, F7).
- `aeat-architecture-boundaries` requires closed value sets to be core StrEnum members
  surfaced at the Typer boundary as `Choice([...])`.
- The existing three-flag path must keep working (backward compatibility within the
  unreleased app is not legacy; it is the current contract other tests exercise).

## Considered options

- **Option A - Calculate-shortcut window gate with fact-gated non-application + advisory
  (chosen).** Add optional `contingencia_year` / `rescate_year` (default `filing_year`)
  and a `rescate_type` enum to the shortcut path. A pure domain predicate evaluates the
  apartado-4 window. When declared years prove the window closed, withhold the 40%
  injection and emit a non-blocking advisory; when in-window, inject as today; when years
  are absent, inject as today plus an unverified-window advisory. Calculate never aborts.
  Pro: closes the silent over-reduction with a certain determination, stays advisory
  (non-blocking), grounds in law, no fork of the core compute. Con: widens the shortcut
  return shape to carry advisories; "supplying more facts can lower your reduccion"
  surprises a naive operator (mitigated by the advisory text).
- **Option B - Pure advisory, always apply the 40% (rejected).** Keep injecting the 40%
  unconditionally; emit a warning when years are out-of-window. Pro: never changes the
  number, simplest, mirrors art. 20 exactly. Con: the verify gate can still grant
  `verified_complete` on a proven over-reduction -- a silent under-declaration of tax the
  window facts already disprove; the art. 20 analogy fails because that gate is uncertain
  and this one is certain.
- **Option C - Blocking refusal when out-of-window (rejected).** Refuse `work calculate`
  when the declared years fall outside the window. Pro: impossible to file an
  out-of-window 40%. Con: eligibility can hinge on facts the operator has not fully
  captured (exact contingencia date within the year, prior partial rescates), and a hard
  refusal contradicts the project-wide advisory-first posture for fact-dependent
  reductions; the brief and the art. 20 precedent both favour advisory over refusal.
- **Option D - Persist year facts and gate at verify time (rejected).** Store
  contingencia/rescate years on the revision so the verify collector evaluates the
  window. Pro: reuses the verify-advisory channel. Con: reintroduces the persisted-DT12
  election the prior ADR rejected, and the facts still originate at calculate time, so
  this adds a persistence hop for no gain over Option A.
- **Option E - Rescate-type as a computed arithmetic fork (rejected).** Branch the
  formula on total vs parcial. Con: the type does not change the arithmetic (research
  F6); the 40% applies to the pre-2007 share of whatever is percibida. The axis is a
  guidance/provenance signal, not a formula input.

## Constraints

- Depends only on mature, in-tree surfaces: the shortcut-input path, the domain compute,
  the calculate-time `CalculationSourceDiagnostic` advisory channel, the core StrEnum
  convention, and the `Notice` envelope spine. No frontier or external dependency.
- The `apply_calculation_shortcut_inputs` return contract (`(casilla_values,
  binding_values)`) must widen to carry advisory records, or the caller must gain a
  parallel advisory accumulator. This is the single structural change and it touches the
  one call site in `build_work_calculate_input_bundle` plus the calculate action that
  assembles `source_advisories`.
- The window predicate must be a pure function with no I/O so the calculation-test rule
  (`no-tautological-calculation-tests`) can exercise its branches against the verbatim
  apartado-4 rule, and the 40% rate stays the single `external_constants` figure.
- Legal grounding must extend the existing `ley-35-2006:dt-12` entry `required_text` with
  an apartado-4 phrase so the evidence gate cross-checks the window clause; the reviewer
  provenance is honest (`reviewed_by` records the agent preparing the entry, pending an
  operator re-stamp per `legal-grounding-verifies-bundled-authoritative-corpus`).

## Implementation

Add a typed `RescateType` StrEnum (`total`, `parcial`) in `core`, surfaced at the Typer
boundary as a `Choice`. Add three optional `work calculate` inputs alongside the existing
rescate flags: the rescate type, the contingencia year, and the rescate (percepcion)
year, the last defaulting to the work unit filing year. A new pure domain function
(sibling to `compute_dt12_reduccion_plan_pensiones`, e.g.
`dt12_regime_window_eligibility(contingencia_year, rescate_year)`) returns a typed
eligibility verdict implementing the three apartado-4 branches from research F5: the
general contingencia-plus-two window, the 2011-2014 eighth-ejercicio window, and the
2010-or-earlier 31-12-2018 cliff.

The shortcut-input path calls the predicate before the existing compute. When both years
are supplied and the verdict is ineligible, the path withholds the 40% injection (the
DT12 slot resolves to the legally-correct no-regime value) and records a grounded
advisory naming the closed window and the eligible range. When eligible, it injects the
40% exactly as today. When the years are absent, it injects as today and records an
unverified-window advisory prompting the operator to confirm the contingencia fell inside
the window. The parcial type adds an advisory clause: each partial cobro shares one
window measured from the contingencia year, and a mixed capital/renta rescate may forfeit
the regime. The core `compute_dt12_reduccion_plan_pensiones` is unchanged -- the window
predicate wraps it, it does not fork it.

Advisories flow through the calculate-time `CalculationSourceDiagnostic` /
`source_advisories` channel (research F3), consistent with the other post-calculate
advisories and with `cli-notices-are-the-only-diagnostic-channel`; the shortcut path is
widened to return its advisory records to the caller. Grounding extends the
`ley-35-2006:dt-12` catalogue `required_text` with an apartado-4 phrase; a dedicated
`BOE-A-2014-12327` (Ley 26/2014) catalogue entry for the establishing law is a candidate
follow-up per `registry-calculation-legal-grounding`.

Bounded first slice: a single total-or-parcial rescate, the two year inputs, the window
predicate, the advisory, and the type axis captured for guidance and provenance.
Deferred to a full channel: a per-partial multi-cobro rescate ledger evaluating one
window across several filing years, a computed DGT todo-o-nada parcial gate, and the
separate Ley 26/2014 catalogue entry.

## Rationale

Option A is chosen because the apartado-4 window is a certain date-arithmetic
determination once the operator declares the two years, which distinguishes it from the
fact-uncertain art. 20 gate and makes fact-gated non-application both correct and safe
(research F5, F6). Withholding the reduccion when the window is proven closed is the only
choice that honours `no-silent-under-declaration` -- Option B would let the verify gate
grant a clean pass on an over-reduced return. Keeping the posture advisory rather than
blocking (rejecting Option C) follows the brief and the established advisory-first
precedent for fact-dependent reductions, and preserves calculate as non-aborting. Siting
the gate on the calculate-shortcut path (rejecting Option D) is forced by research F4:
the year facts exist only there, and persisting them revives the profile election the
prior ADR refused. Treating the rescate type as a guidance/provenance axis rather than an
arithmetic fork (rejecting Option E) matches the law -- the 40% applies to the pre-2007
share of whatever is percibida regardless of total-vs-parcial.

## Consequences

- Closes the silent over-reduction: an out-of-window rescate with declared years no
  longer receives the 40%, and the operator sees a grounded advisory explaining the
  closed window and the eligible range.
- An operator who declares the contingencia and rescate years can see a lower reduccion
  than the current unconditional behaviour. This is legally correct but is a visible
  behaviour change that the advisory text must explain clearly.
- The existing three-flag path keeps working unchanged; absent year inputs it injects the
  40% as today, now paired with an unverified-window advisory so the outcome is never
  silent.
- The shortcut-input return contract widens to carry advisories, a small structural
  change isolated to one call site and the calculate action.
- The rescate-type axis records operator intent and enables correct parcial guidance, but
  the first slice does not yet enforce the per-partial multi-cobro window or the DGT
  todo-o-nada criterion; those remain a documented deferred surface.
- Grounding the window against the bundled corpus strengthens the DT12 legal entry; the
  Ley 26/2014 establishing-law entry is a follow-up, not a blocker for the first slice.
- A latent inconsistency is surfaced but not resolved here: the pre-existing DT12 verify
  advisory uses `BLOCKING_RULE` kind where the art. 20 sibling uses `ADVISORY`; a future
  cleanup should align them.

## Codification candidates

No project rule is promoted at proposed stage. If the fact-gated non-application pattern
(withhold a reduction when a certain date-arithmetic eligibility gate is proven false,
advise when unverified) recurs beyond DT12, it is a candidate for codification after one
full execution cycle per the `vaultspec-codify` discipline.
