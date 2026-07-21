---
tags:
  - '#adr'
  - '#m210-plazo-keying'
date: '2026-07-09'
modified: '2026-07-09'
related:
  - "[[2026-07-09-m210-irnr-phase-2-engine-adr]]"
  - "[[2026-06-04-m210-irnr-phase-2-engine-research]]"
---

# `m210-plazo-keying` adr: `M210 resultado and tipo-dependent plazo keying` | (**status:** `proposed`)

## Problem Statement

M210 Slice B (the phase-2 agrupacion axis) landed the GENERAL "resto de rentas
con resultado a ingresar" quarterly deadline windows (1T-4T closing 20 Apr / 20
Jul / 20 Oct / 20 Jan of the devengo quarter's following month) as registry
`deadline_windows` TOML, grounded verbatim in the bundled consolidated Orden
EHA/3316/2010 art 5 (`corpus/normatives/html/orden-eha-3316-2010.html#a5`, en
vigor 24/06/2026, incorporating the Orden HAC/56/2024 art 4.2 amendment). That
covered only ONE of the six art-5 plazo cases: the current-law M210 plazo is
both RESULTADO-dependent (a ingresar / cuota cero / a devolver) AND TIPO-de-renta
dependent (arrendamiento tipos 01/35, rentas imputadas tipo 02, transmisiones de
inmuebles tipo 28). The `DeadlineWindowDefinition` model keys a window on
`(filing_year, period, applicability_conditions)`, where `applicability_conditions`
are `ProfilePredicateDefinition`s evaluated against the `TaxpayerProfile`. Neither
axis this ADR must model is expressible in that shape: the RESULTADO is a value
the calculation engine COMPUTES (not a profile fact, not a devengo period token),
and the TIPO de renta is declared PER WORK UNIT (the tipo_renta casilla / the
Slice-A `OfficialTipoRentaCode` axis), not a profile-static census fact. The
annual/resultado cases therefore cannot be period-keyed nor profile-condition
keyed as the schema stands. This ADR decides how to attach the two qualifiers,
how they resolve, whether to widen the M210 `period_selector`, and how the work
sequences against Slice C.

The Slice-B builder's working plazo table carried one grounding error this ADR
corrects: it stated the rentas-imputadas tipo-02 window as "del 1 de abril al 31
de diciembre del ano natural siguiente". The bundled art-5 text states the
PRESENTATION plazo for tipo 02 is "todo el ano natural siguiente al devengo" (the
whole natural year, i.e. 1 January - 31 December of the year following devengo);
the "1 de abril hasta el 23 de diciembre" range is the narrower DOMICILIACION
(direct-debit payment) sub-window, a distinct payment-modality concept, not the
presentation close. The corrected figures below are used throughout.

## Considerations

- **Corpus-verified art-5 plazo cases** (verbatim from the bundled consolidated
  Orden EHA/3316/2010 art 5, cross-checked against Orden HAC/56/2024 art 4.2 /
  BOE-A-2024-1772):
  - General "resto" a ingresar (separada o agrupacion trimestral): "los veinte
    primeros dias naturales de los meses de abril, julio, octubre y enero, en
    relacion con las rentas cuya fecha de devengo este comprendida en el
    trimestre natural anterior." **[ALREADY LANDED, stable.]**
  - Arrendamiento/subarrendamiento a ingresar (tipos de renta 01 / 35): "el plazo
    de presentacion e ingreso sera los veinte primeros dias naturales del mes de
    abril del ano siguiente al de devengo, tanto para declarar de forma separada
    como agrupada." **TIPO + RESULTADO, annual-April.**
  - Cuota cero: "del 1 al 20 de enero del ano siguiente al de devengo." **RESULTADO,
    annual-January.**
  - A devolver: "a partir del 1 de febrero del ano siguiente al de devengo",
    exercisable "en el plazo de cuatro anos contados desde el termino del periodo
    de declaracion e ingreso de la retencion" (art 16.4 RD 1776/2004). **RESULTADO,
    opens 1-Feb of year+1, closes 4 years later.**
  - Rentas imputadas de inmuebles urbanos (tipo 02): presentacion "todo el ano
    natural siguiente al devengo" = 1 Jan - 31 Dec of year+1. **TIPO, annual,
    resultado-independent.** (Domiciliacion payment sub-window 1 Apr - 23 Dec of
    year+1 is a distinct modality, out of scope for the presentation window.)
  - Transmisiones de bienes inmuebles (tipo 28): "se mantiene el plazo del
    anterior modelo 212, fijado en el articulo 14 del Reglamento del IRNR (RD
    1776/2004)" = event-relative (three months following the one month from the
    transmission date). **TIPO, event/per-devengo (EVENT-N-shaped), NOT a fixed
    calendar window.**
- **`applicability_conditions` are profile-keyed only.** `DeadlineEngine`
  evaluates them via `_evaluate_conditions(profile, window.applicability_conditions,
  ...)` against the `TaxpayerProfile` (`_engine.py`). They exist to gate windows on
  profile-static facts (ROI enrolment, activity dates). The RESULTADO is computed;
  the TIPO de renta is a per-declaration input. Neither is a profile fact, so
  reusing `applicability_conditions` for them would be a category error and would
  misclassify a filer who files several tipos/resultados in one year.
- **`resolve_filing_closes_on(modelo, filing_year, period)`** (`domain/deadlines/
  _plazo.py`) returns the `closes_on` of the first window matching
  `(filing_year, registry_token)`. It is resultado- and tipo-agnostic today. It
  feeds the extemporaneidad surface at work-unit creation, BEFORE any calculation
  has run, so it structurally cannot know the resultado.
- **`period_selector = ["EVENT-N"]`** on the M210 2025 revision is hard-pinned by
  `test_modelo_210_registry.py:110` (`... .periods == ("EVENT-N",)`). It gates
  operator WORK-UNIT CREATION, which is a separate concern from deadline-window
  AUTHORITY: the landed quarterly windows already resolve via
  `resolve_filing_closes_on` without any period_selector change.
- **Slice C dependency.** The agrupacion grouped-rentas Type-2 detail-row model is
  Slice C, fetch-gated on the official diseno de registro. Agrupacion work units,
  and a calculate path that PRODUCES a resultado, both depend on Slice C. Slice A
  (the `OfficialTipoRentaCode` / `TipoRentaIrnr` axis) is in progress and owns the
  tipo axis this ADR's tipo qualifier reuses.
- **Codified constraints in play.** `aeat-schema-central-config` (regulatory dates
  live in the registry, never inline in code); `period-filter-single-boundary-
  authority` (the period grammar is a devengo-period identity, not a computed
  outcome); `cli-notices-are-the-only-diagnostic-channel` (a post-calculation
  advisory rides the typed `Notice` channel); `aeat-calculation-grounding` /
  `legal-grounding-verifies-bundled-authoritative-corpus` (every date grounded in
  the bundled corpus).

## Considered options

Decision 1 - how to attach the RESULTADO qualifier:

- **O1a resultado-tagged window variants resolved POST-calculation (chosen half).**
  Add an optional typed `resultado_scope` to `DeadlineWindowDefinition`
  (default `None`); the annual resultado cases declare it; a resultado-aware
  resolver picks the tagged variant after the engine computes the resultado. Pro:
  dates stay registry-declared and grounded; the qualifier lives where the value
  is known. Con: one new optional field + a second resolver entry point.
- **O1b surface the resultado plazo as a post-calculation deadline advisory Notice
  (chosen half).** The resolved annual close is emitted as an `info` `Notice` on
  the M210 calculate/verify envelope, not injected into the creation-time
  extemporaneidad line (which runs pre-calculation). Pro: honest timing; rides the
  single diagnostic channel. Accepted together with O1a as the hybrid.
- **O1c resultado -> period-token synthesis.** Encode the resultado into a synthetic
  period token so `resolve_filing_closes_on` disambiguates. Rejected: the period
  grammar is a devengo-period identity (`period-filter-single-boundary-authority`);
  minting resultado-flavoured tokens forks the boundary authority and lets a
  computed outcome masquerade as a filing period.
- **O1d put the annual dates in code as a pure advisory, no registry window.**
  Rejected: violates `aeat-schema-central-config` - regulatory dates are registry
  authority, gate-checked against corpus, not Python literals.
- **O1e reuse `applicability_conditions` for the resultado.** Rejected: those are
  profile-keyed; the resultado is not a profile fact.

Decision 2 - the TIPO-dependent cases:

- **O2a tipo-scoped window variants (chosen).** Add an optional typed
  `tipo_renta_scope` to `DeadlineWindowDefinition` (default `None`), reusing the
  Slice-A tipo axis; resolved post-declaration alongside the resultado qualifier.
  Arrendamiento-April composes `tipo_renta_scope in {01,35}` with
  `resultado_scope = a_ingresar`; imputadas-02 is `tipo_renta_scope = 02` alone.
  Pro: matches the form (tipo is a declared per-unit axis) and keeps
  `applicability_conditions` for its profile-static purpose. Accepted.
- **O2b key tipo cases via `applicability_conditions`.** Rejected: tipo de renta is
  per-work-unit, not a profile-static census fact; the same non-resident files
  several tipos in one year, so a profile predicate would mis-gate.
- **O2c model transmisiones-28 as a fixed calendar window.** Rejected: the tipo-28
  plazo is event-relative (devengo + offset per RD 1776/2004 art 14); it has no
  fixed calendar date. It stays in the EVENT-N per-devengo work model (already the
  M210 mode) and is NOT a `deadline_windows` row. The exact offset is NEEDS-FETCH
  (the RD 1776/2004 reglamento is not bundled).

Decision 3 - the `period_selector` widen:

- **O3a widen `period_selector` now to add 1T-4T + 0A.** Rejected for this
  addendum: work-unit creation for the quarterly/agrupacion modes needs the Slice-C
  detail-row model and a calculate path that yields a resultado; widening the
  selector before that ships would expose creatable periods with no work model
  behind them, and would break the pin-test with nothing consuming the new tokens.
- **O3b keep `period_selector = ["EVENT-N"]`; land the annual windows as authority
  only; sequence the widen with Slice C (chosen).** The `deadline_windows` are
  calendar authority resolvable independent of `period_selector`; the widen (and
  the pin-test update) is a Slice-C precondition. Accepted - keeps the pin and the
  landed windows stable now.

Decision 4 - relationship to Slice C:

- **O4a land the registry window DATA now (bundled-groundable), sequence the
  RESOLUTION WIRING after Slice A + Slice C (chosen).** The annual resultado/tipo
  window rows are groundable from bundled art-5 today and land independently; their
  post-calc resolver, the `period_selector` widen, and the tipo/resultado work-unit
  axis depend on Slice A (tipo axis) and Slice C (detail rows + agrupacion work
  model + resultado-producing calculate). Accepted.
- **O4b block all annual-plazo work behind Slice C.** Rejected: the registry window
  DATA needs no fetch and no detail-row model; blocking it wastes bundled grounding
  and bloats Slice C.

## Constraints

- **STABLE (must not change):** the 8 landed a-ingresar quarterly windows
  (`modelo-210-2025-1t..4t`, `modelo-210-2026-1t..4t`, commit `0c6689e068`). The
  two new qualifier fields default `None`, so those rows stay byte-identical; this
  addendum ADDS annual variants and the qualifier axes and changes no quarterly
  date. Confirmed against the landed
  `.../210/revisions/2025/deadline_windows/0001-deadline_windows.toml`.
- **NEEDS-FETCH (gates only the tipo-28 event offset):** RD 1776/2004 (Reglamento
  del IRNR) art 14 for the exact transmisiones-28 plazo offset. Absent from the
  bundled corpus; the EVENT-N event-shape and the deferral-to-RD-1776/2004 fact are
  bundled (art-5 recital), but the "3 months after 1 month" numeral is not
  corpus-groundable and must not be authored from memory. Until fetched, tipo-28
  carries the event-shape only, no numeric offset.
- **Parent stability:** Slice A (`OfficialTipoRentaCode` axis) is in progress and
  owns the tipo axis reused here; the resolution wiring waits on it and on Slice C.
  The Slice-B quarterly windows and `resolve_filing_closes_on` are landed and
  test-pinned.
- **Grounding discipline:** every date is verbatim-grounded in the bundled
  consolidated Orden EHA/3316/2010 art 5; the imputadas-02 figure is CORRECTED to
  the bundled "todo el ano natural siguiente" (1 Jan - 31 Dec of year+1), not the
  Slice-B builder's erroneous "1 abril - 31 diciembre".

## Implementation

**Two new optional qualifier axes on `DeadlineWindowDefinition`
(`domain/calculations/registry/_schema.py`).** Add `resultado_scope:
M210ResultadoScope | None = None` and `tipo_renta_scope: TipoRentaIrnr | None =
None` (or the `OfficialTipoRentaCode`-projected value; the loader hydrates the
authoring token at the boundary per the enum-at-boundary rule). Both default
`None`, preserving every existing window (M210 quarterly + every other modelo's
windows) byte-identical. `M210ResultadoScope` is a new core `StrEnum`
(`A_INGRESAR` / `CUOTA_CERO` / `A_DEVOLVER`) declared in `core/` per the
closed-value-set rule.

**Annual resultado/tipo window rows** are authored on the 2025 revision
`deadline_windows` fragment (grounded `legal_refs = ["orden-eha-3316-2010:art-5"]`):
arrendamiento a-ingresar (`tipo_renta_scope in {arrendamiento tipos 01/35}`,
`resultado_scope = A_INGRESAR`, opens 1-Apr / closes 20-Apr of year+1); cuota cero
(`resultado_scope = CUOTA_CERO`, opens 1-Jan / closes 20-Jan of year+1); a devolver
(`resultado_scope = A_DEVOLVER`, opens 1-Feb of year+1 / closes four years later);
rentas imputadas tipo 02 (`tipo_renta_scope = 02`, opens 1-Jan / closes 31-Dec of
year+1). Transmisiones tipo 28 is NOT authored as a window (event-relative, offset
NEEDS-FETCH).

**Resolution is two-tier.** `resolve_filing_closes_on` stays resultado/tipo-agnostic
for the general period-keyed path. A new resultado/tipo-aware resolver (in
`domain/deadlines/`) is called AFTER `calculate` produces the resultado; it selects
the tagged annual variant by `(filing_year, resultado_scope, tipo_renta_scope)` and
surfaces the close as an `info` `Notice` on the M210 calculate/verify envelope
(the plazo advisory), never mutating the pre-calculation extemporaneidad line. The
deadline-window section validator (`_validate_surfaces.validate_deadline_window_
section`) keeps enforcing `legal_refs`/`source_refs` coverage on the new rows.

**`period_selector` is unchanged in this addendum.** The widen to add the
quarterly + `0A` tokens (and the `test_modelo_210_registry.py:110` pin update from
`== ("EVENT-N",)` to "EVENT-N present AND the quarterly/0A tokens present") is a
Slice-C task, co-landed with the agrupacion work model.

**Code-surface footprint** (for the implementation plan):
- `src/aeat/core/_irnr.py` - new `M210ResultadoScope` StrEnum; reuse
  `TipoRentaIrnr` / `OfficialTipoRentaCode` for the tipo axis.
- `src/aeat/domain/calculations/registry/_schema.py` - two optional qualifier
  fields on `DeadlineWindowDefinition` (default `None`).
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/deadline_windows/`
  - the four annual resultado/tipo window rows (art-5 grounded).
- `src/aeat/domain/deadlines/_plazo.py` (+ a new resultado/tipo-aware resolver
  entry point in `domain/deadlines/`) - post-calculation annual-plazo resolution.
- `src/aeat/application/modelo/` (calculate/verify emit) +
  `core/json_contract.Notice` - the post-calculation plazo advisory.
- `src/aeat/_data/registry/aeat/legal/irnr.toml` - `orden-eha-3316-2010:art-5`
  legal entry already present; extend `required_text` only if the annual clauses
  need distinct corpus phrases.
- **Slice-C-sequenced (not this addendum):** `period_selector` widen +
  `test_modelo_210_registry.py:110` pin update; the tipo/resultado work-unit axis
  and the resultado-producing calculate path.
- **NEEDS-FETCH-gated:** transmisiones tipo-28 event offset (RD 1776/2004 art 14).

## Rationale

The two qualifiers this ADR introduces are the two axes the current
`DeadlineWindowDefinition` genuinely cannot express: a COMPUTED resultado and a
PER-WORK-UNIT tipo de renta. Both fail the `applicability_conditions` shape for the
same structural reason - that shape keys on the profile, and neither is a profile
fact - which is why the ADR adds them as first-class typed window qualifiers rather
than bending the profile-predicate mechanism (mirroring the profile-vs-computed
distinction codified in `cross-period-suppression-grounded-in-registry-
classification`). Keeping the DATES in the registry (O1a) honours
`aeat-schema-central-config` and keeps them under the corpus-grounding gate;
resolving them POST-calculation and surfacing them as a `Notice` (O1b) puts the
resolution where the resultado is actually known and rides the single diagnostic
channel (`cli-notices-are-the-only-diagnostic-channel`), instead of the
creation-time extemporaneidad line that runs before any value exists. Rejecting the
period-token synthesis (O1c) preserves the single period-boundary authority.
Splitting the registry DATA (land now) from the resolution WIRING (sequence after
Slice A + C) follows the phase-2 ADR's grounding-honesty through-line: no slice
waits on a blocker it does not need, and the landed quarterly windows and the
EVENT-N pin stay stable. The imputadas-02 correction is the corpus-verification
rule in action: the Slice-B table's "1 abril - 31 diciembre" was a
domiciliacion/presentation conflation the bundled art-5 text refutes.

## Consequences

- **Gain:** all six art-5 plazo cases are decided and (five of six) groundable now;
  only the tipo-28 event offset carries a named fetch, replacing vague "resultado-
  dependent" language with concrete registry rows.
- **Gain:** the two qualifier fields are additive and generalisable - any future
  modelo with resultado/tipo-dependent windows reuses them without a new mechanism.
- **Correction shipped:** the imputadas-02 presentation window is set to the bundled
  "todo el ano natural siguiente" (1 Jan - 31 Dec of year+1); the 1-Apr/23-Dec range
  is recorded as the domiciliacion sub-window, not the presentation close.
- **Cost (accepted):** a second deadline-resolution entry point (post-calculation)
  beside `resolve_filing_closes_on`; the two are kept distinct by timing (pre- vs
  post-calculation) rather than merged, because only the post-calc path can know the
  resultado.
- **Sequenced, not blocked:** the registry window rows land in this addendum's
  implementation slice; the `period_selector` widen, the pin-test update, and the
  operator-facing resolution wiring co-land with Slice A + Slice C.
- **Bounded:** transmisiones tipo-28's numeric offset stays out until RD 1776/2004
  art 14 is fetched and bundled; until then tipo-28 carries the EVENT-N event-shape
  with no fabricated offset.
- **Stability confirmed:** the 8 landed a-ingresar quarterly windows are unchanged;
  the new qualifier fields default `None`.
