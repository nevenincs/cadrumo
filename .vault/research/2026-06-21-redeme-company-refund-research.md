---
tags:
  - '#research'
  - '#redeme-company-refund'
date: '2026-06-21'
modified: '2026-06-21'
related:
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
---

# `redeme-company-refund` research: `REDEME monthly-refund (devolución) disposition for Modelo 303`

A persona verification from the company (legal-entity) prism found that Modelo 303
can only ever express a negative result as "a compensar" (carry forward); it has
no "a devolver" (refund) path. This blocks the defining provision of a REDEME
company — the monthly refund (devolución mensual) — and the last-period refund
election available to any taxpayer. This research specifies the refund disposition
grounded in the bundled AEAT diseño de registros and the law, maps the enrolment
surface, and defines a multi-persona verification plan.

## Findings

### F1 — The gap, confirmed in code

`_DISPOSITION_SPEC[Modelo.M303]` (in `src/aeat/core/_result_disposition.py`) sets
`negative = ResultDisposition.COMPENSACION` unconditionally. The
`ResultDisposition` enum ALREADY defines `DEVOLUCION = "D"`, but no M303 path elects
it. The 303 registry has no refund result casilla (only "a compensar" casillas;
casilla 109 "Devoluciones acordadas por la AEAT" is an unrelated input). The
profile axis `iva_redeme_enrolled` is accepted at profile-create and persisted but
is NOT consumed by the 303 calculation or disposition (the SII axis IS consumed,
for the monthly cadence, which works).

### F2 — Authoritative AEAT diseño de registros grounding (bundled corpus)

The bundled Modelo 303 diseño (ejercicio 2026 y siguientes) defines the refund
expression directly:

- **Field "Tipo Declaración" (Nota 1)** — the result-disposition code: `C`
  (solicitud de compensación) / **`D` (devolución)** / `G` (cuenta corriente
  tributaria-ingreso) / `I` (ingreso) / `N` (sin actividad / resultado cero) / `V`
  (cuenta corriente tributaria-devolución) / `U` (domiciliación del ingreso) / `X`
  (devolución por transferencia al extranjero). A refund is **`D`**.
- **Field "Sujeto pasivo inscrito en el Registro de devolución mensual (art. 30
  RIVA)"** — `"1"` SÍ / `"2"` NO. This is the REDEME enrolment flag carried IN the
  fichero, sourced from the profile `iva_redeme_enrolled` axis.
- **Refund bank fields** — Devolución IBAN (Spanish IBAN starts `ES`, 24 positions),
  SWIFT-BIC, bank name, address, city, country code. Required when Tipo
  Declaración = `D` (and `X` for foreign transfer).
- The refund AMOUNT is the signed result itself (casilla `[69]` "Resultado de la
  autoliquidación" / casilla `71` "Resultado final" when negative); there is no
  separate "importe a devolver" casilla — the Tipo Declaración code plus the signed
  result and the IBAN express the refund.

### F3 — Legal basis

- **Art. 30 RD 1624/1992 (RIVA)** — Registro de devolución mensual (REDEME); the
  diseño field cites it verbatim.
- **LIVA art. 116 (Ley 37/1992)** — the monthly-refund right for REDEME-inscribed
  taxpayers.
- A REDEME taxpayer files Modelo 303 **monthly** (already working — SII/REDEME
  cadence is consumed by the deadline engine) and, for a negative period, requests
  a **monthly refund** (`D`) rather than carrying the credit forward (`C`).
- Any taxpayer (REDEME or not) may elect `D` in the **last period of the year**
  (4T or 12) for the annual refund; outside the last period a non-REDEME taxpayer
  may only carry forward (`C`).

### F4 — Affected profiles (the "all affected profiles" scope)

- **REDEME-inscribed taxpayers of every entity type** — `iva_redeme_enrolled =
  true` (companies most commonly, but autónomos and attribution entities may be
  REDEME too). Negative period → refund (`D`) is available every period.
- **Any profile in its last filing period** (4T quarterly, or 12 monthly) — refund
  (`D`) is an operator election for the annual liquidation.
- **Ordinary (non-REDEME, non-final-period) profiles** — unaffected: refund is not
  available; carry-forward (`C`) remains the only negative disposition. This is the
  control case that must keep behaving exactly as today.

### F5 — Enrolment surface (and the active-peer-WIP sequencing constraint)

The schema touches: (a) the disposition election — `ResultDisposition.DEVOLUCION`
already exists; the docstring states elections like `D` are "operator elections
layered on a base disposition, recorded by the caller", so the M303 spec table may
not need editing — the election is layered by the calc/export caller from the
REDEME axis + last-period; (b) the REDEME fichero field + IBAN/SWIFT-BIC refund
fields in the 303 registry/export; (c) consumption of `iva_redeme_enrolled` in the
calc/disposition; (d) a refund-account input (IBAN) surface; (e) the disposition
gate (refund only when REDEME or last-period); (f) locales, error-code registry,
and tests.

**Sequencing constraint (discovered before editing):** the 303 registry casilla
fragments (`0001-casillas.part-001/002.toml`), the completeness manifest, and
`revision.toml` are under ACTIVE peer WIP (a recargo-de-equivalencia + base
aggregation change), and `_result_disposition.py` is an untracked peer file. Per
the worktree abort-on-WIP discipline, enrolment MUST NOT edit those files mid-flight.
Mitigations: add refund casillas/bindings via NEW registry fragment files (the
loader merges fragments) rather than editing the peer's parts; layer the `D`
election in a calc/export caller rather than mutating the peer's disposition table;
coordinate the manifest entry once the peer's manifest edit settles. Where a clean
non-colliding fragment is impossible (the shared completeness manifest), enrolment
of that slice waits for the peer change to land.

## Multi-persona cross-period verification plan

Run after enrolment; each persona files Modelo 303 across two consecutive periods.

1. **REDEME company, monthly refund (primary).** Legal entity (SL), SII + REDEME
   enrolled, monthly. Period 01 negative (input > output) → assert disposition `D`,
   fichero REDEME field `1`, refund amount = the negative result, IBAN present, and
   that the credit is NOT carried into 02 (no casilla 110 in 02). Period 02 positive
   → ingreso `I`.
2. **Last-period refund, autónomo.** Natural person, quarterly, non-REDEME. 1T-3T
   carry forward (`C`); 4T negative → refund (`D`) permitted only because it is the
   last period.
3. **Ordinary carry-forward control (must not regress).** Non-REDEME company,
   quarterly, negative non-final period → `C` only; electing `D` is refused. This is
   the regression guard that the refund path did not loosen the ordinary gate.
4. **Cross-entity attribution.** Confirm casilla 65 (state attribution) and the
   refund election compose for legal_entity and attribution_entity, not only natural
   person.

Each persona asserts the FINAL fichero disposition code and the result amount (not
just an intermediate casilla), with a negative control, per the no-tautology and
honest-test disciplines.

## Open decisions for the ADR

- Whether the `D` election is automatic from `iva_redeme_enrolled` (+ last-period)
  or an explicit operator flag (e.g. `--disposition devolver`) gated by eligibility.
- Where the refund IBAN/SWIFT-BIC lives: a profile axis (refund account) vs a
  per-filing input.
- The disposition eligibility gate: refuse `D` when neither REDEME nor last-period,
  with a grounded refusal naming art. 30 RIVA / LIVA art. 116.
- Interaction with the IVA-wallet carry: a refunded period generates no carry
  forward; reconcile with the `iva-compensation-override` decision so a period is
  either refunded OR compensated, never both.
