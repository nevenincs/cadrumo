---
tags:
  - '#adr'
  - '#m210-irnr-full-engine'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-non-resident-irnr-axis-adr]]"
  - "[[2026-04-21-calc-verification-adr]]"
  - "[[2026-04-17-modelo-303-formulas-adr]]"
  - "[[2026-05-26-cross-domain-continuity-adr]]"
  - '[[2026-06-04-m210-irnr-full-engine-research]]'
---


# `m210-irnr-full-engine` adr: Modelo 210 IRNR full calculation engine (post Path-B stub) | (**status:** `accepted`)

## D1 — Context

Modelo 210 is the autoliquidación for IRNR (Impuesto sobre la Renta
de no Residentes) without establishment-permanent. It is the only
filing surface available to non-resident taxpayers (Olivia post-
Brexit UK, Khadija Marruecos, Felipe Argentina; the round-16, -25
and -26 personas confirmed three distinct shapes).

Current state (post task #196 Path-B refusal stub):
- Profile axis exists per `non-resident-irnr-axis` ADR
  (`fiscal_residency`, `country_of_fiscal_residence`, derived
  `ue_eee_status`).
- `aeat app modelo work create --modelo 210` and downstream verbs
  refuse with a documented Path-B stub message.
- No registry directory exists under
  `src/aeat/_data/registry/aeat/modelos/210/`; no casillas, no
  formulas, no bindings, no deadline windows, no extraction profiles.
- Persona testimonials surface real cuota arithmetic blocked by the
  stub: Olivia's rental of a Marbella flat (rendimientos
  inmobiliarios at 24% under Art 25.1.a TRLIRNR), Khadija's
  seasonal-worker salary (Art 25.1.a with Convenio España-Marruecos
  treaty-rate override), Felipe's freelance services to Spanish
  clients (Art 25.1.f if treaty-resident in a UE/EEA equivalent).

This ADR scopes the engine work to lift the M210 refusal stub
into a working calculation surface. It is the authorising decision
for plan Step W09.P41.S380 (M210 IRNR full calculation engine,
task #256).

## D2 — Decision

### D2.1 — Two-phase engine landing

Phase 1 (this campaign): registry skeleton + base-rate routing
+ Convenio dispatch + representante fiscal surface. Sufficient to
remove the Path-B refusal and produce correct cuota for the three
testimonial personas under the residual general-rate flow.

Phase 2 (follow-on L3 sub-plan, deferred): full casilla schema
authoring per AEAT M210 diseño de registro, every tipo de renta
slot (Arts 25.1.b pensiones, 25.1.f UE residentes, 25.2 rentas
inmobiliarias, 25.3 plusvalías, 25.5 pagos a cuenta), every
Convenio rate table per country roster, agrupación anual support
per Orden HAC/56/2024.

The Phase 1 / Phase 2 split is required because the full diseño de
registro is ~80 casillas across 12 tipo-de-renta variants; landing
it inside the cross-domain-continuity epic would dwarf the rest of
the campaign. The Path-B refusal lift is a single engine surface
delivering correct arithmetic for the testimonial shapes; the full
casilla schema is a separate substantial work item with its own
plan + ADR + audit trail.

### D2.2 — Base computation per Art 24 TRLIRNR

`base_imponible = rendimientos_íntegros - gastos_deducibles`
where:
- For Art 25.1.a (general 24% rate): no deducibles permitted under
  TRLIRNR Art 24.1 — the base equals gross income. Phase 1 wires
  this branch only.
- For Art 25.1.f (residentes UE 19% rate): TRLIRNR Art 24.6
  permits the LIRPF deduction catalogue. Phase 1 declares the
  binding shape; Phase 2 wires the full LIRPF cross-references.
- For Art 25.2 (rentas inmobiliarias): TRLIRNR Art 24.5 routes to
  LIRPF Capítulo III rules. Deferred to Phase 2.
- For Art 25.3 (ganancias patrimoniales): TRLIRNR Art 24.4 routes
  to LIRPF Título X. Deferred to Phase 2.

### D2.3 — Tipo gravamen registry parameter

Author a `bracket_table` parameter `m210-tipo-gravamen-2025` keyed
on `tipo_renta` (Literal of `general` | `ue_residente` | `pension`
| `inmobiliaria` | `ganancia_patrimonial`) returning:
- `general` → Decimal("0.24") (TRLIRNR Art 25.1.a).
- `ue_residente` → Decimal("0.19") (TRLIRNR Art 25.1.f).
- `pension` → bracket table from Art 25.1.b (deferred to task #229
  follow-on, but the registry entry exists with NOT_YET_AUTHORED
  marker per the Path-B pattern).
- `inmobiliaria` → Decimal("0.24") with deduction routing per
  Art 24.5 (Phase 2).
- `ganancia_patrimonial` → Decimal("0.19") (TRLIRNR Art 25.1.f
  treats plusvalías at the savings-base rate).

The bracket table is keyed on `tipo_renta` and time-windowed for
2025; revisions for 2024 and earlier years carry the historical
rates verbatim per BOE publication dates.

### D2.4 — Convenio doble imposición dispatch

Profile carries `convenio_doble_imposicion_country` (ISO 3166-1
alpha-2, optional, defaults to None — means no treaty override).
When present, the calculate path looks up the treaty rate from a
registry parameter `m210-convenio-rates` keyed on
`(country, tipo_renta)` and applies it INSTEAD of the
TRLIRNR-baseline rate from D2.3. Phase 1 populates the parameter
shape and three test rows (España-UK, España-Marruecos, España-
Argentina); Phase 2 backfills the full Convenios España bibliography
per task #225 (Khadija) and #229 (Felipe).

The treaty-rate override is BLOCKING when the operator declares
`convenio_doble_imposicion_country` but the country has no row in
`m210-convenio-rates` — emit a ModeloVerificationFinding with
`kind=BLOCKING_RULE`, legal_refs threading the country code, and
next_action `Author Convenio España-<CC> rate row in
m210-convenio-rates or unset convenio_doble_imposicion_country to
fall back to the TRLIRNR baseline.`

### D2.5 — Representante fiscal surface

TRLIRNR Art 10 requires non-EU residents (other than residents
of EU Member States, with the EEA scope refined by TRLIRNR Art
10.1 second paragraph) to designate a representante fiscal
(Spanish-resident agent) for IRNR correspondence. (Earlier
drafts of this ADR mis-cited TRLIRNR Art 47; Art 47 of
TRLIRNR governs sucesión en la deuda tributaria — successor-
tax-liability — and is out of M210 Phase 1 scope. The
representante mandate lives in Art 10. Ley 58/2003 LGT Art 47
provides a parallel general-LGT representante rule for any
non-resident, but the IRNR-specific authority is TRLIRNR Art
10.) Phase 1 surfaces the requirement as:
- Profile field `representante_fiscal_nif: str | None` (already
  partially modelled under task #197 / #198, harmonise the field
  shape here).
- M210 verification predicate `implies_nonzero(["fiscal_residency",
  "representante_fiscal_nif"])` GATED on a profile-conditional
  guard that fires only when `ue_eee_status is False` (using the
  new `implies_nonzero` operator from the dsl-conditional-predicate
  ADR — this M210 work is the first non-M131 use site).
- Refusal message: `Non-EU residents must declare a representante
  fiscal per TRLIRNR Art 10; set --representante-fiscal-nif on the
  profile.`

Scope note: TRLIRNR Art 10's letter excepts only EU Member State
residents from the representante obligation, not the wider EEA.
Phase 1 deliberately consults the broader `ue_eee_status`
property (EU + Norway + Iceland + Liechtenstein), which gives
a slightly over-permissive exemption (EEA-non-EU residents are
excused even though Art 10 letter would require them to name a
representante). The over-permissive direction is conservative
for AEAT-correspondence purposes because mutual-assistance
treaties under TRLIRNR Art 24.6 + the EEA-Spain administrative-
cooperation agreements treat EEA equivalently. A future ADR
refinement could split the gate to consult an `is_eu_member`
property (narrower) instead. Documented inline as a follow-on
hygiene item; Phase 1 leaves the broader gate in place.

The conditional-on-derived-property gating cannot be expressed by
the current implies_nonzero alone because `ue_eee_status` is a
property not a casilla. Phase 1 patch: emit the predicate
unconditionally at the registry level and let the runtime
`_evaluate_verification_predicates` consult the profile flag to
skip the predicate for EEA residents. The escape hatch is
documented inline as a follow-on item; a future
`implies_nonzero_when_profile_flag` operator can subsume it cleanly.

## D3 — Alternatives considered

**Alternative A: lift the Path-B refusal in one campaign.** Land
the full M210 diseño de registro (~80 casillas + 12 tipo-de-renta
branches + full Convenio roster) under this epic. Rejected:
incompatible with the open-ended-correctness-campaign cadence;
~3 weeks of casilla authoring work would starve every other in-
flight task. The two-phase split delivers arithmetic correctness
for the three testimonial personas now and defers the
diseño-de-registro paperwork to a dedicated sub-plan.

**Alternative B: hand-author cuota formulas without a bracket
table.** Each `tipo_renta` branch gets its own formula with a
hardcoded Decimal rate. Rejected: violates the
registry-authority-flow rule (rates must live in registry
parameters with time-windowed BOE/AEAT grounding, not in
formula bodies). Also blocks the Convenio override dispatch from
operating at parameter-lookup time.

**Alternative C: Convenio override via formula conditional.**
Express the treaty rate as a per-formula
`if profile.convenio_doble_imposicion_country == "MA" then 0.10
else 0.24`. Rejected: forces formula bodies to enumerate every
treaty country (currently ~92 active Convenios España); blows up
the formula DSL surface; conflicts with the no-conditional-
DSL-in-formulas rule established by the calc-verification ADR.
Parameter-lookup dispatch is the canonical pattern.

## D4 — Trade-offs

- **Refusal-lift completeness vs casilla coverage.** Phase 1
  produces correct cuota for the three testimonial personas under
  Art 25.1.a / 25.1.f / Convenio dispatch but does not handle
  rentas inmobiliarias, plusvalías, pensiones, or
  agrupación anual. Operators in those scopes will still receive
  a partial-coverage warning. Acceptable because the alternative
  (no engine at all) is strictly worse.
- **Parameter-shape compatibility.** The `bracket_table` keyed on
  string `tipo_renta` (rather than the more common time-and-CCAA
  keying) requires `_validate_revision_rules.py` to accept the new
  key shape. The validator change is in scope for Phase 1.
- **Conditional-on-property gating escape hatch.** Routing the
  EEA-exemption check through the runtime predicate evaluator
  (rather than the registry DSL) is a one-site escape that future
  predicate work can subsume. Acceptable trade-off: documenting
  the escape inline is cheaper than designing
  implies_nonzero_when_profile_flag pre-emptively.

## D5 — Consequences

- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/`
  scaffold lands with parameters, casillas, formulas, bindings,
  deadline_windows, verification_predicates per Phase 1 scope.
- M210 work create / calculate / verify operate end-to-end for
  Art 25.1.a / 25.1.f / Convenio-override personas.
- The implies_nonzero operator from the dsl-conditional-predicate
  ADR gains its first non-M131 use site.
- Task #225 (183-day Khadija + Convenio España-Marruecos) and
  #229 / #230 (Felipe Art 25.1.b + Art 13.1.h) become unblocked:
  their TaskList rows can be re-targeted to populate Convenio
  rate rows in the new `m210-convenio-rates` parameter rather
  than building parallel arithmetic.
- Phase 2 lands as a separate L3 sub-plan
  (`.vault/plan/<date>-m210-full-casilla-schema-plan.md`) covering
  the diseño-de-registro + agrupación-anual + full Convenios
  roster + the every-tipo-de-renta branch wiring. The sub-plan
  is referenced from a future W09.P41 anchor Step authored by
  PM once Phase 1 lands.
- Path-B refusal stub from task #196 is removed only after Phase 1
  passes the persona-replay gates for Olivia / Khadija / Felipe.
  Until then the refusal stays and Phase 1 wiring is gated behind
  an `_M210_ENGINE_LIVE` feature flag that defaults to False; tests
  set it to True to exercise the engine in isolation.

## D6 — Tests

Phase 1 acceptance tests (under
`src/aeat/_data/registry/aeat/modelos/210/test_modelo_210_phase1.py`):

- `test_olivia_marbella_rental_general_rate` — UK profile,
  rendimiento bruto 12000 EUR, no Convenio override, expects
  cuota = 0.24 × 12000 = 2880 EUR. Cited against TRLIRNR Art
  25.1.a + Olivia round-16 testimonial.
- `test_khadija_marruecos_convenio_override` — Marruecos profile,
  rendimiento 8000 EUR, Convenio España-Marruecos override at the
  treaty rate (Art 14 Convenio MA), expects cuota at the treaty
  rate. Cited against BOE-A-1985-... Convenio España-Marruecos.
- `test_felipe_argentina_ue_residente_path` — Argentina profile,
  rendimiento 15000 EUR, NOT in UE/EEA, no Convenio AR override
  authored → BLOCKING finding emitted with next_action pointing
  at the Convenio rate-row authoring gap.
- `test_representante_fiscal_required_for_non_eea` —
  non-EEA profile with `representante_fiscal_nif=None` →
  BLOCKING finding via implies_nonzero predicate.
- `test_eea_resident_skips_representante_fiscal_check` —
  ue_eee_status=True profile passes the verification gate even
  with `representante_fiscal_nif=None`.

Anti-tautology proof: mutate the `m210-convenio-rates` row for
ES-MA to 0.99, re-run Khadija test, assert the cuota diverges
from the prior assertion. Confirms the test consumes the
registry parameter rather than a hardcoded Decimal.

## D7 — Out of scope (Phase 2 / follow-on)

- M210 full diseño de registro (80+ casillas across 12 tipo-de-
  renta variants).
- Agrupación anual presentation mode per Orden HAC/56/2024.
- Rentas inmobiliarias / plusvalías / pensiones tipo-de-renta
  branches (deferred to tasks #229, #230, and the L3 sub-plan).
- Full Convenios España rate roster (~92 countries) — Phase 1
  ships three rows (UK, MA, AR) as testimonial coverage.
- M216 (IRNR retenedor) and M247 (IRNR renta inmobiliaria) —
  separate modelos with their own forthcoming ADRs.
- M210 export to AEAT registro-de-presentación format.
