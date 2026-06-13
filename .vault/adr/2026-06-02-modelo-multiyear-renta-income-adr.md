---
tags:
  - '#adr'
  - '#modelo-multiyear-renta-income'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-income-research]]"
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
  - '[[2026-06-04-modelo-multiyear-renta-research]]'
---



# `modelo-multiyear-renta-income` adr: `income-tax prior-year cross-renta binding hooks (M200 BIN / M100 / M202)` | (**status:** `accepted`)

## Problem Statement

The multi-year-renta authorization gate requires that every modelo's calculation backend
be proven across at least two distinct renta (annual) periods before it can be authorized.
This ADR is one of several mechanism-specific ADRs co-backing that campaign plan; the
foundational gate decision (`2026-06-02-modelo-multiyear-renta-adr`) owns the gate spine
and the un-fakeable enrollment contract, and explicitly defers per-mechanism cross-year
behaviour to ADRs like this one.

Three income-tax modelos express their genuine cross-year behaviour through prior-year
data carried forward from a previously filed return:

- **Modelo 200** (Impuesto sobre Sociedades) compensates bases imponibles negativas (BIN)
  declared in a prior year against the current year's positive base.
- **Modelo 100** (IRPF) carries forward unused negative balances in the savings base
  (saldos negativos) across subsequent years.
- **Modelo 202** (IS instalment payment) modalidad art.40.2 computes the instalment from
  the cuota of a prior período impositivo.

The problem is to decide how each cross-year hook is expressed so its >=2-renta enrollment
is real (driving the registry engine across two filing years), grounded in BOE/AEAT
authority rather than author-invented numbers, and built without new runtime infrastructure
— while surfacing every legal-grounding gap honestly per the project's
no-silent-under-declaration and no-tautological-calculation-tests disciplines.

## Considerations

- A proven cross-year binding template already exists. Modelo 130's
  `revisions/2019-y-siguientes/bindings/0002-bindings.toml` declares a
  `source = "previous_filing"` binding with selector `{ source_modelo, filing_year_delta,
  period, source_casillas }` and `aggregation`, and the resolver already consumes it
  (`_binding_prefill.py`, `_bindings.py`), computing the source year as
  `filing_year + filing_year_delta + period_year_delta`. Re-using this shape means zero
  resolver code.
- The `FormulaOperator` set in `_schema.py` already provides `add / subtract / multiply /
  percent / min / max / clamp / if_then_else / sum / copy` and comparisons — enough to
  express the only non-trivial cap (M200's €1M floor / 70% ceiling) without new operators.
- Per the registry-authority-flow rule, all three bindings are registry-authoring against
  `ValidatedRegistryAuthority`-owned snapshots; none introduces a new production path that
  calls raw loaders.
- Legal grounding strength differs by modelo and must be stated honestly: M200 has reviewed
  statute plus an AEAT worked manual; M100's 4-year period is grounded only at summary
  strength in the corpus JSON; M202's 40.2 base and instalment calendar are grounded
  verbatim in the AEAT instrucciones.
- The manual→computed footprint is deliberately minimal and pinned to exact casillas. M200
  `DP200014:00552` stays manual but gains a computed consistency check (the existing advisory
  upgraded); the new computed quantity is the capped BIN-aplicada. M202 `01` flips manual →
  prior-year-bound, while `03` and its 18% rate are already computed. M100's three carryforward
  casillas become binding-fed (copy of the prior-year saldo). No other casilla changes kind.

## Constraints

- **M100 art.49 grounding is summary-strength, not verbatim statute.** The honesty flag
  carried from research is partially resolved: `ley-35-2006.json` carries article 49 as a
  structured entry whose `summary.es` states "la compensación en los cuatro años siguientes
  de los saldos negativos no aplicados, con un límite del 25 por ciento", but the JSON holds
  no verbatim BOE article body and no literal `art-49` string anchor (article 49 is keyed by
  `numero`). The 4-year period is therefore confirmed in-repo at AEAT/editorial summary
  strength only. The plan must ingest the verbatim art.48/49 statute body before any
  per-casilla numeric oracle is asserted; until then M100 enrollment asserts wiring and
  provenance, not invented Decimals.
- **M202 1/P year-offset is `-2`, not `-1`.** The honesty flag is confirmed real against the
  instrucciones: the 40.2 base is the cuota of the last período whose filing deadline was
  vencido on the 1st of the payment month, and 1/P falls in April before the prior-year M200
  (due July) is vencido. So 1/P binds two years back; 2/P (October) and 3/P (December) bind
  one year back. The per-period delta must be encoded explicitly, not assumed uniform.
- This ADR depends on the M130 binding template and resolver remaining stable; both are
  mature, shipped, and tested at the domain and application layers, so the dependency is
  low-risk.

## Implementation

Each hook is a registry binding (re-using the M130 shape) plus, where a cap is needed, a
registry formula built from the existing operator set. No resolver, schema, or CLI code
changes.

**Modelo 200 — BIN compensation.** Add a `previous_filing` binding in
`modelos/200/revisions/2024-y-siguientes/` whose `bin_disponible` input is a prior-year copy
of casilla `00671` ("Detalle compensación BIN — Pendiente de aplicación en períodos futuros"):
selector `{ source_modelo = "200", filing_year_delta = -1, period = "0A", source_output =
"00671" }`, `aggregation = { op = "copy" }`, `legal_refs = ["ley-27-2014:art-26"]`. The
unlimited carry self-accumulates through `00671` year over year, so the design uses a single
prior-year copy rather than a multi-year fan-out.

The BIN compensation amount actually applied this period is casilla
`DP200014:00547` (semantic_role `is_liquidacion_iii_compensacion_bin_aplicada`,
`intentional_singleton`). The companion `modelo-200-base-determination` ADR's base-determination
build (landed separately) makes the base chain computed — base imponible previa
`DP200014:00550 = 00501 + DP200013:00417 − DP200013:00418`, and base imponible
`DP200014:00552 = max(00550 − 01032 − 00547, 0)` — consuming `00547` as the applied-BIN
subtrahend. `00547` is the handoff point this A4 hook layers onto.

**Cap design — ELECTIVE-CAPPED, not forced-to-cap (as built).** An earlier draft proposed making
`00552` (or `00547`) *equal* the cap. That is over-specified and would ship wrong tax: LIS
art. 26.1 — «las bases imponibles negativas ... **podrán** ser compensadas ... **con el límite**
del 70 por ciento ... En todo caso ... hasta el importe de 1 millón de euros» — makes BIN
compensation a taxpayer **right bounded by a ceiling**, not a mandate. A filer may lawfully apply
**less** than the cap (to preserve BIN stock for later years, or when the base is already low).
Forcing `00547 = cap` would over-apply for every partial-compensation filer. So the implemented
design keeps `00547` **operator-elective (`input_kind = "manual"`)** and adds, on top, a
**separate computed ceiling casilla** `DP200014:bin-aplicada-maxima` (internal; no `export_refs`)
`= min(00670, max(literal(1000000), percent(70, DP200014:00550)))` — the cap base is `00550`, the
base imponible previa **before** the reserva de capitalización (`01032`) and the compensación
(`00547`), per art. 26.1 — plus **two `BLOCKING_RULE` `cap_le_when_positive` verification
predicates**: `cap_le_when_positive(["DP200014:00547", "DP200014:bin-aplicada-maxima"])` (the
applied amount must not exceed the art.26.1 ceiling) and
`cap_le_when_positive(["DP200014:00547", "00670"])` (cannot compensate more than the BIN stock
held). `cap_le_when_positive` is the existing operator (grounded in the M131 C11≤C10 / M130
C15≤C14 cap analogues); no new operator is added, and it holds vacuously when the ceiling ≤ 0.
This is the `no-silent-under-declaration` "Good" path applied to the **over-application**
direction — the gate **refuses** an over-claim while **permitting** electing less. The existing
`implies_nonzero(["00501", "DP200014:00552"])` ADVISORY (under-declaration direction) is owned by
the `modelo-200-base-determination` ADR and left as-is. `00501` (resultado contable) and the
per-origin-year BIN detail boxes (0174-0182, 00489/00504/.../00700) stay manual. The art.26.1
quitas/esperas and extinción exclusions are not modelled; they surface as an ADVISORY note plus a
profile flag, never a hard refusal.

**Modelo 100 — base-liquidable-general-negativa carryforward (as delivered).** The casilla
identifiers in the original draft of this paragraph (`0462→0393`, `0465→0396`, `1390→1391`)
were stale against the live 2025 Modelo 100 revision and never landed; the delivered
enrollment grounds against the real Anexo-C casillas. The cross-renta hook is a single
`previous_filing` binding on the base-liquidable-**general**-negativa carryforward: the
*opening* pending balance for the immediately-prior origin ejercicio — casilla **1388**
(`irpf_anexo_c_base_liq_neg_pendiente_inicio`) — is a straight `aggregation = { op = "copy" }`
of the prior filing's *generated* saldo — casilla **1391**
(`irpf_anexo_c_base_liq_neg_generado`): selector `{ source_modelo = "100",
filing_year_delta = -1, period = "0A", source_output = "1391" }`. The carry is
origin-year-matched in both the 2024 and 2025 revisions (each revision's 1388 is the
immediately-prior origin year — 2024-rev 1388 = ejercicio 2023, 2025-rev 1388 = ejercicio
2024), never a same-number copy.

**Grounding correction (art.48, not art.49).** The general-base negativa carry is established
by Ley 35/2006 **art. 48** ("Integración y compensación de rentas en la base imponible
GENERAL"), which carries its own four-following-years / 25 % rule (current consolidated text
per Ley 26/2014). The original draft cited `ley-35-2006:art-49` — but art. 49 governs the
base imponible del **AHORRO** (savings base), a different mechanism. The committed binding's
`legal_refs` are corrected `art-49 → art-48` once art. 48 is ingested into the legal
catalogue + corpus (the exact provision — art. 48 alone vs art. 48 + art. 50.3 for the
base-*liquidable* level — is adjudicated by the legal-authority pass).

**Deferred (delivered enrollment is general-base carry only).** The savings-base
(0441-family) art. 49 rolling carry, the integración-subtract that *consumes* the opening
pending into the current-year base reduction, the four-year multi-origin-year window depth,
and an explicit year-tagged expiry guard are calc-completeness follow-ons — not claimed by
the landed enrollment, which proves the general-base carry wiring/provenance across two
distinct renta years through the full `calculate_modelo_revision` engine.

**Modelo 202 — modalidad art.40.2 (cleanest of the three; no new formula).** Only casilla
`01` ("Mod.40.2 base", `required = true`, `input_kind = "manual"` today) flips manual →
prior-year-bound. Add a `previous_filing` binding in `modelos/202/revisions/2025-y-siguientes/`,
`id = "modelo-202-2025-cuota-base-ejercicio-anterior"`, that populates `01`: selector
`{ source_modelo = "200", filing_year_delta = <-2 for 1/P, -1 for 2/P and 3/P>, period = "0A",
source_output = <prior cuota-líquida casilla> }`, `aggregation = { op = "copy" }`, `legal_refs =
["ley-27-2014:art-40"]`. Casilla `03` ("Mod.40.2 a ingresar") is **already computed** by the
existing formula `modelo-202-modalidad-40-2-a-ingresar`
(`subtract(percent(01, is.modalidad_cuota.percentage), 02)`); the 18% rate is the existing
parameter `is.modalidad_cuota.percentage` (value `18`, `valid_from 2025-01-01`,
`required_text` anchor "porcentaje del 18%"). So no new formula is added — feeding `01` from
the prior year is sufficient, and `03` recomputes automatically. The binding **inherits the
existing INCN modality gate** `derive_modelo_202_modality` (driven by the
`modelo-202-2025-y-siguientes-incn-prior-12-months` binding): for an INCN > €6M entity, 40.2
is not offered (only 40.3 clave 32), so `01` must not be populated for a 40.3-mandatory entity.
The per-period `filing_year_delta` is the one design subtlety and must be encoded per
instalment key.

**Enrollment E2E (per modelo).** Each enrollment clones the proven M130 continuity pattern at
both layers — domain (`test_modelo_130_registry.py` family) and application
(`test_modelo_130_carry_forward_continuity.py`) — driving the real registry engine across two
distinct filing years so the gate's recorder observes >=2 distinct renta years. M200 seeds a
2023 BIN loss into `00671`, calculates 2024 profit, asserts the bound `bin_disponible` equals
the 2023 `00671`, asserts the capped aplicada equals `min(that, max(1M, 0.70·base_previa_2024))`,
and asserts the consistency check fires (BLOCKING) when the manually entered `DP200014:00552`
disagrees with `base_previa − aplicada`. M100 asserts the 2025 carryforward casilla equals the
2024 generated saldo and that integración reduces the 2025 savings base (wiring/provenance
oracle only). M202 seeds an M200/2023 cuota, asserts the M202/2024 1/P `01` equals that cuota
with the `-2` offset (and a 2/P/3/P case with `-1`), and that `03` recomputes as
`percent(01, 18) − 02` and the same-year 202→200 roll-up still reconciles.

## Rationale

Re-using the M130 `previous_filing` template means the cross-year mechanism for all three
modelos is expressed in data the resolver already understands, so the campaign adds tax
semantics without adding runtime surface — consistent with the foundational gate ADR's
"registry-authoring, not new infra" posture. Grounding each binding in a reviewed legal_ref
(`ley-27-2014:art-26`, `ley-35-2006:art-49`, `ley-27-2014:art-40`) keeps the calculation
non-tautological: the M200 cap is checkable against the AEAT 2024 manual, and the M100 and
M202 hooks assert wiring and reconciliation where no per-casilla numeric oracle exists, per
the no-tautological-calculation-tests rule. Recording the two grounding gaps as constraints
rather than silently shipping past them follows the no-silent-under-declaration discipline.

## Consequences

- **Three income-tax modelos gain real >=2-renta enrollment** expressed as registry data,
  unlocking their authorization in the gate campaign once the E2E tests land.
- **M200 introduces the only new formula logic** (the €1M/70% cap). It is fully grounded and
  the highest-value hook of the three.
- **Honest grounding debt is surfaced, not hidden.** M100's 4-year period rests on a corpus
  summary until the verbatim statute is ingested; the plan carries that as an explicit
  follow-up, and M100 enrollment stays at wiring/provenance strength until then.
- **M202's per-period offset is a correctness trap if missed.** Encoding `1/P → -2` and
  `2/P,3/P → -1` is mandatory; a uniform `-1` would silently bind the wrong year for the
  April instalment. The constraint is recorded so the plan and the executor cannot assume it
  away.
- **Pitfall — exclusions deferred.** M200 quitas/esperas/extinción and M100 year-tagged
  expiry are advisory/Phase-2; the advisory surface must fire so a filer is not silently led
  to over-compensate.

## Codification candidates

- **Rule slug:** `previous-filing-binding-reuse-over-new-infra`.
  **Rule:** A modelo's prior-year cross-renta hook must be expressed by re-using the proven
  `previous_filing` binding shape plus existing formula operators against
  `ValidatedRegistryAuthority` snapshots, never by adding resolver, schema, or CLI code, and
  any legal-grounding gap (summary-strength statute, period-specific year offsets) must be
  recorded as an explicit constraint rather than assumed.
