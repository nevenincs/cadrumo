---
tags:
  - '#adr'
  - '#modelo-131-eo-modulos-engine'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-04-27-modelo-131-calc-verify-adr]]"
  - "[[2026-04-27-modelo-100-renta-full-calc-adr]]"
  - "[[2026-05-27-khalid-cli-testimonial-audit]]"
  - '[[2026-07-10-modelo-131-eo-modulos-engine-research]]'
---

# `modelo-131-eo-modulos-engine` adr: `Modelo 131 EO modulos table-driven rendimiento engine` | (**status:** `accepted`)

## Problem Statement

Modelo 131 (IRPF pago fraccionado, estimación objetiva / módulos) computes every
downstream casilla from a single upstream figure — the rendimiento neto por módulos —
that the registry currently sources as a **manual operator input**, not as a computed
value. On the 2025 revision, casilla `01` "Suma de rendimientos netos" is
`input_kind = "manual"`; the fichero-BOE form fields `actividad-N-rendimiento-neto`
(and the 2024 generic `modulo-N-unidades` / `modulo-N-rendimiento-neto` slots) are all
`source = "manual_input"`. Only the 2% pago-fraccionado rate is table-driven (parameters
`irpf.objective_no_base_fractional_payment_rate` / `..._agriculture_...`), and casillas
`04/06/07/10/13/15` are computed strictly downstream of the manual rendimiento.

Consequence, reproduced in `2026-05-27-khalid-cli-testimonial-audit` (round 11, P0):
`aeat app modelo work calculate --modelo 131 --year 2024 --period 2T` with módulo unit
counts informed returns casillas `01/04/13/15` all `0.00` — no error, no advisory. The
motor cannot turn units into a rendimiento because the per-unit coefficient
(rendimiento anual por unidad antes de amortización, fixed by Hacienda) is itself an
operator field defaulting to zero. A zero coefficient silently zeroes the cuota. This is
a `no-silent-under-declaration` breach on positive economic activity, plus a black-box
UX (the `modulo-N-*` slots are unlabeled generic decimals with no signo semantics).

The same gap exists on **Modelo 100 annual renta**: the 2025 EO casillas
`irpf_eo_modulo_num_unidades` and `irpf_eo_modulo_rdto_antes_amort` ("Rendimiento por
módulo antes de amortización") are manual inputs (no `input_kind = "computed"`). The
coefficient is hand-entered in both the quarterly (M131) and annual (M100) surfaces.

This ADR decides the design, the data strategy, and the phasing for a table-driven
estimación-objetiva rendimiento engine. It does not implement it and does not close the
issue.

## Considerations

- **The mechanism is fully published law, not a modelling choice.** The signos-índices-
  módulos determination is fixed by LIRPF art. 31 (estimación objetiva) and, per filing
  year, by the annual Orden de módulos (Orden HFP/1359/2023 for 2024, Orden HAC/1347/2024
  for 2025, Orden HAC/1425/2025 for 2026), each carrying the per-activity coefficient
  tables in its Anexos. The AEAT Manual práctico de Renta reproduces the chain and the
  tables (bundled at `corpus/manuals/renta/2024/part1/source.pdf.extracted.md`, Fase 1ª
  at the "Determinación del rendimiento neto previo" section; chapters 8 no-agrícola /
  9 agrícola). LIRPF is bundled consolidated at `corpus/normatives/html/ley-35-2006.html`.

- **The chain has four fases, not one product.** (1) Rendimiento neto **previo** =
  Σ(unidades_módulo × rendimiento anual por unidad antes de amortización). (2)
  Rendimiento neto **minorado** = previo − minoración por incentivos al empleo −
  amortizaciones (incentivos a la inversión). (3) Rendimiento neto **de módulos** =
  minorado × Π(índices correctores) — por actividad, población, temporada, empresas de
  reducida dimensión, inicio de actividad, exceso. (4) Rendimiento neto **de la
  actividad** = módulos − reducción general (5% for 2024, roll-forward per RD-Ley) −
  gastos extraordinarios por circunstancias excepcionales + otras percepciones
  empresariales (subvenciones) − reducciones especiales (jóvenes agricultores), then the
  art. 32 reducción for rendimientos irregulares. A coefficient-only product (fase 1
  alone) is not the filing figure and would over-state it.

- **Agrarian activities are a distinct engine.** Chapter 9 (Anexo I) computes agrarian
  rendimiento as índice de rendimiento neto × volumen de ingresos, then applies a
  different índices-correctores set — not the signos/units product. The ADR scopes both
  but treats them as two engines sharing the fases 3–4 tail.

- **The dataset is large, per-activity, and per-year.** The 2024 manual reproduces
  coefficient tables across ~80+ IAE activity groups, each with several signos plus its
  índices-correctores set and the incentivos-al-empleo tramos; every figure is
  re-published (and can change) each year by a new Orden. Authoring all activities × all
  supported years into registry TOML is a multi-month data campaign in its own right,
  each entry requiring `registry-calculation-legal-grounding` (cite the binding Orden
  Anexo article + corpus cross-check).

- **Governing rules.** `aeat-schema-central-config` (coefficients are registry data, not
  inline literals); `registry-calculation-legal-grounding` + `legal-grounding-verifies-
  bundled-authoritative-corpus` (each coefficient cites its Orden Anexo and is cross-
  checked against the bundled corpus); `no-tautological-calculation-tests` (expected
  values from AEAT manual worked examples, not re-derived from the same table);
  `no-silent-under-declaration` (a zero rendimiento on positive units must surface an
  advisory, never a silent grant); `calculation-source-canonical-mechanism` (one
  canonical mechanism shared by M131 and M100); `aeat-registry-authority-flow` (the
  compiled snapshot is the authority).

## Considered options

- **Option A — Full engine + full annual dataset, all activities and all supported
  years, in one campaign.** Complete and correct at landing. Rejected as the primary
  path: it is a very large, high-grounding-burden data-transcription effort that blocks
  any engine delivery on the entire Orden Anexo backlog, and stalls the P0 silent-zero
  fix behind months of data authoring.

- **Option B — Table-driven engine + a bounded first-slice dataset (a small set of the
  highest-prevalence IAE activities for the most recent completed year), long tail
  phased; un-tabled activities keep manual entry behind a visible advisory.**
  Recommended. Delivers the full four-fase engine and the coefficient-registry schema
  now, grounds a verifiable subset against AEAT worked examples, closes the silent-zero
  immediately (advisory guard), and phases the remaining activities and years without a
  wrong-figure risk.

- **Option C — No engine; label the módulo slots by signo and add a non-zero advisory
  guard only.** Cheapest. Addresses the black-box UX and the silent-zero
  (`no-silent-under-declaration`) but not the table-driven computation the issue
  requires. Kept as the *interim mitigation embedded in Phase 1*, not as the resolution.

- **Option D — Coefficient table for fase 1 only (rendimiento neto previo), leaving
  minoración, índices correctores, and reducciones manual.** Rejected: emits a figure
  that looks computed but omits the correcting stages, so it over-states the rendimiento
  and would file a wrong pago fraccionado — worse than an honest manual input.

## Constraints

- **Data authority and grounding burden is the binding constraint, not engine
  complexity.** The four-fase arithmetic is modest; the risk and the effort live in
  transcribing ~80+ activities × per-year Ordenes and grounding each figure to its Orden
  Anexo with a corpus cross-check. The bundled corpus currently carries the AEAT *manual*
  reproduction of the tables and consolidated LIRPF, but not the Orden Anexo PDFs
  themselves; first-slice authoring must confirm each figure against the manual and,
  where a figure is an amount/rate, against live BOE per `legal-grounding-verifies-
  bundled-authoritative-corpus` (the bundled corpus is a strong default, not infallible).

- **Depends on stable parent surfaces.** The M131 calc/verify chain
  (`2026-04-27-modelo-131-calc-verify-adr`) and the M100 renta full-calc surface
  (`2026-04-27-modelo-100-renta-full-calc-adr`) are accepted and in place; this engine
  feeds their existing casillas (M131 `01`, the M100 EO rendimiento) rather than adding a
  new modelo surface. Wiring casilla `01` from manual to computed must preserve the
  downstream formulas unchanged.

- **Per-year roll-forward is permanent maintenance, not a one-off.** Each new Orden de
  módulos (published each December for the following year) adds a revision-scoped
  coefficient set. This is forward-function AEAT variability (`no-legacy-compatibility`:
  each year's Orden is current law for its year), not legacy.

- **Índices correctores and reducciones are conditional on taxpayer facts** (población
  <5000, temporada, inicio de actividad, empresa de reducida dimensión) that the profile
  / operator must supply; the engine must model them as declared inputs with grounded
  defaults, not silently assume the neutral case.

## Implementation

A three-layer design, delivered across a multi-phase data+engine campaign.

**1. Módulo coefficient registry (data surface).** A new per-revision authoring surface
keyed by (IAE epígrafe, signo/módulo) → rendimiento anual por unidad antes de
amortización, plus the per-activity índices-correctores set and the incentivos-al-empleo
minoración tramos. Authored as registry TOML under the modelo revision tree
(`aeat-schema-central-config`), each entry grounded in the year's Orden Anexo article and
cross-checked against the bundled corpus (`registry-calculation-legal-grounding`). Shared
by M131 and M100 so the coefficient has a single home
(`calculation-source-canonical-mechanism`).

**2. Units × coefficient engine (four-fase chain).** Registry formulas/resolvers that
compute: fase 1 rendimiento neto previo (Σ product), fase 2 minorado (− incentivos al
empleo, − amortizaciones), fase 3 de módulos (× índices correctores), fase 4 de la
actividad (− reducción general, ± gastos/percepciones), then art. 32. The final figure
feeds M131 casilla `01` (re-typed `computed`) and the M100 EO rendimiento. A separate
agrarian variant (índice de rendimiento neto × volumen) shares fases 3–4. For M131 the
pago fraccionado percentage (existing 2% parameter) then applies unchanged.

**3. Interim advisory guard + signo labeling (Phase 1, ships before full data).** An
advisory that fires when units are informed but the resolved rendimiento is zero
(`no-silent-under-declaration`), and semantic labels on the módulo slots resolving IAE
epígrafe → signo names (the audit's black-box finding). For an activity not yet in the
coefficient registry, the engine keeps manual rendimiento entry behind a visible
"activity not yet table-driven" advisory — never a silent zero.

**Recommended first slice.** The highest-prevalence estimación-objetiva IAE activities
for the most recent completed year (2024 or 2025), grounded and tested against the AEAT
manual worked examples: peluquería (972.1), café-bar / restaurante (671/672), comercio
al por menor (several 64x/65x epígrafes), transporte de mercancías por carretera (722),
and transporte por autotaxi (721.2). These cover the persona set the audit names
(hospitality, transport, comercio) and each has a worked example in the manual usable as
an external numeric oracle (`no-tautological-calculation-tests`).

**Phasing.**
- **Phase 1 — engine + schema + first slice + guard.** Coefficient-registry schema, the
  four-fase no-agrícola engine, the first-slice activities for one year, M131 casilla `01`
  wired computed, the silent-zero advisory, and signo labeling.
- **Phase 2 — índices correctores breadth + agrarian engine.** Full correctores set and
  the agrarian (Chapter 9) variant.
- **Phase 3 — activity breadth + M100 annual wiring.** Remaining IAE activities; wire the
  M100 EO rendimiento to the shared engine.
- **Phase 4 — per-year roll-forward.** Each new Orden de módulos as a revision-scoped
  coefficient set.

## Rationale

Option B is chosen because the binding risk is data grounding, not engine design: the
four-fase chain is small and fully specified by law, so building it once and feeding it a
verifiable subset removes the P0 silent-zero and delivers real computation now, while the
long tail of ~80+ activities is authored incrementally without gating the engine. Options
A (all-at-once) stalls the P0 fix behind a months-long transcription; D (fase-1-only)
ships an over-stated wrong figure — the exact `registry-calculation-legal-grounding`
failure mode; C alone leaves the manual-input gap the issue exists to close. Grounding
the mechanism in LIRPF art. 31 + the annual Orden Anexos (both partially bundled) and
testing against the manual's worked examples satisfies the calculation-grounding and
no-tautological-test rules. Sharing one coefficient home across M131 and M100 satisfies
`calculation-source-canonical-mechanism` and closes the identical M100 EO gap on the same
engine.

## Consequences

- **Positive.** Closes the P0 silent-zero for the first-slice activities with a real
  computed rendimiento; makes the módulos chain auditable and grounded end-to-end;
  eliminates the black-box slot UX via signo labeling; and closes the mirror M100 EO gap
  on one shared engine. The advisory guard closes the `no-silent-under-declaration`
  breach for *all* activities in Phase 1, ahead of full data.
- **Negative / cost accepted.** A large, ongoing data-authoring commitment: ~80+
  activities × per-year Ordenes, each needing grounded transcription. Until an activity
  is tabled it stays manual (with advisory), so full coverage is deliberately deferred —
  an operator under an un-tabled epígrafe sees no computed figure yet. Per-year Orden
  roll-forward is permanent maintenance.
- **Neutral / open.** The Orden Anexo PDFs are not yet bundled as corpus; first-slice
  grounding leans on the bundled AEAT manual reproduction plus live BOE cross-check for
  amounts. Índices-correctores and reducciones depend on taxpayer-fact inputs whose
  profile plumbing is scoped in Phase 2. The agrarian engine (Chapter 9) is a separate
  mechanism deferred to Phase 2. Prevalence ranking of "most common" activities should be
  confirmed with the operator before Phase 1 data authoring locks the first slice.
