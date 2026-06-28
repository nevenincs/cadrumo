---
tags:
  - '#audit'
  - '#eoy-final-calculation'
date: '2026-06-21'
modified: '2026-06-21'
related: []
---



# `eoy-final-calculation` audit: `End-of-year annual final-calculation aggregation gaps (M100 income, M200 cuota)`

## Scope

Round-2 persona-driven cross-period correctness audit. The operator directive was: verify that
Modelo base calculations stay correct when deductibles, expenses, and IVA are carried from prior
periods into future periods, and that the **aggregate end-of-year final calculations are correct**.

Method: real CLI only (`uv run --no-sync aeat ...`), per-persona isolated encrypted storage
(`AEAT_LOCAL_STORAGE_ROOT` + `AEAT_SECRET_STORE_DIR` + file backend + custom passphrase), no mocks,
no fakes. A single autónomo profile (estimación directa, GENERAL IVA, actividad económica) was given
a full 2024 ledger (four quarterly invoices + four deductible expenses) and driven through Modelo 130
1T–4T, Modelo 303 1T–4T, the annual Modelo 100 and Modelo 390; a separate `legal_entity` (SL)
profile was driven through Modelo 200. Expected values were derived from the AEAT rule (RD 439/2007
art. 110 for M130; LIVA / LIS), never from the registry formula under test.

In scope: cross-period carry of deductibles/expenses/IVA, and the year-end annual aggregates
(M100, M390, M200). Out of scope (documented as by-design, not audited as bugs): `export` is the
local finish line, `work file` is window-gated, and the cross-period clean-state gate blocks a
dependent period that lacks official prior-filing evidence — see
`2026-05-21-work-verify-deadline-independence-adr` and the cross-period clean-state ADRs.

## Findings

### What is CORRECT (the per-period / cross-period engine is sound)

- **M130 cross-period deductibles — CORRECT.** Cumulative YTD figures across 1T–4T: casilla 01
  (income) 6000/10000/15000/20000, casilla 02 (gastos) 1000/1800/3000/4000, casilla 03 (rendimiento
  neto) 5000/8200/12000/16000 — every quarter exact. Deductible expenses auto-aggregate into casilla
  02 from the ledger (the former "expense drop" gap is fixed; no manual `--casilla 02` needed). The
  pago-fraccionado carry casilla 05 equals the sum of prior quarters' casilla 07 (RD 439/2007
  art. 110.3 — the gross positive results, NOT casilla 19), confirmed independently by persona
  `r2-autonomo-130-eoy` and the committed continuity tests.
- **M390 end-of-year IVA aggregate — CORRECT.** The annual summary aggregates the four M303 quarters
  exactly from the ledger: cuota devengada total 4200.00 (= 1260+840+1050+1050), cuota deducible
  total 840.00 (= 210+168+252+210), resultado régimen general 3360.00. (The M390→M303
  reconciliation-against-filed-quarters casillas read 0 — by-design, they require filed M303
  evidence.)
- **M303 per-quarter results — CORRECT.** resultado (casilla 71) 1050/672/798/840; cuota devengada
  and deducible correct each quarter.

### F1 — CRITICAL — Modelo 100 does not aggregate annual rendimiento de actividades económicas

**Update 2026-06-21 — INCOME HALF FIXED (M100 2024).** The income side has been remediated: a new
registry binding `renta-2024-ledger-income-0171` (source `ledger_renta_income_aggregation`, grounded
in art-27/28 + the lirpf-cuota-chain authority) plus casilla 0171 bound and wired into the 2024
mini-model construct, reaching parity with the 2025 revision (the app resolver
`aggregate_renta_m100_income_ledger` was already enrolled in the calc mesh; only the 2024 registry
wiring was missing). Verified: M100 2024 casilla 0171 = 20000 (was 0), rendimiento 0224 = 19000
(estimación directa simplificada, automatic 5% deduction). The three M100/2024 fold-in test helpers
were brought to parity with the 2025 `_AUTO_RESOLVED` exclusion; M100 registry/drift/wiring and
renta-income-aggregation suites green. **STILL OPEN:** the EXPENSE half (first-slice deductible
bindings `0186/0192/0199/0203`) requires a `2024.toml` category-profile registry (~970 lines of
FY-specific statutory caps with per-category legal grounding) — deferred as out of safe autonomous
scope; tracked under this audit's fix campaign. The original finding text below stands as the
as-discovered record.

**Update 2026-06-21 (later) — F1 FULLY RESOLVED for 2024 (income + expense).** The expense half
also landed: a new `categories/profiles/2024.toml` (41 categories at parity with the reviewed 2025
profile; first-slice categories `full_deductible` per LIRPF art. 28.1, dietas/seguro caps per RD
439/2007 art. 9 / LIRPF art. 30.2.5ª — framework values, no fabricated FY-specific figures) plus the
four first-slice expense bindings `0186/0192/0199/0203` with casillas bound and construct wired.
Verified: M100 2024 casilla 0199 = 2662 (asesoría routed), rendimiento 0224 = 16471.10; non-first-slice
gastos correctly advisory/manual (first-slice is intentionally incomplete in both 2024 and 2025). All
six M100 revisions build; full suite 1148 passed. F1 is closed for 2024; the remaining residue is the
deliberately-advisory non-first-slice gastos (by-design, parity with 2025).

An autónomo who declares actividad económica and has a full year of ledger income/expenses (annual
rendimiento neto 16000) finds that the **annual Modelo 100 carries none of it**. The full
`bindings list --modelo 100 --year 2024 --period 0A --missing` set contains only retenciones
(`renta-2024-modelo-111/115/123/193-...`), pagos fraccionados
(`renta-2024-modelo-130/131-pagos-fraccionados`), profile demographics, and carry-forward
base-liquidable bindings — **there is no binding or relation that feeds the rendimiento neto de
actividades económicas (the business income) into the return**. Casilla 0224 (rendimiento neto act.
económicas) resolves to 0.00; the only non-zero figure produced is the personal minimum (≈5550).
Only the *payments* (pagos fraccionados) fold in — never the income they were payments against.

Net effect: a year-end IRPF return that silently omits the entire business income — a silent
under-declaration of the headline figure. Corroborated three ways: the missing-binding list (no
income binding), persona `r2-autonomo-130-eoy`'s full M100 calc (casilla 0224 = 0), and the earlier
`renta-100-fullyear` persona. Currently masked only because the dependent-period verify is separately
blocked by the evidence gate — i.e. the safety net is incidental, not designed for this.

Reproduction: profile = natural_person + `--irpf-income-categories actividad_economica`, full-year
M130 ledger, then `aeat app modelo work calculate --modelo 100 --year 2024 --period 0A`; inspect
casilla 0224.

### F2 — CRITICAL — Modelo 200 cuota íntegra does not propagate to cuota a ingresar

For an SL with resultado contable 80000 (micro-empresa, tipo 23%), the IS chain computes the base
and cuota íntegra correctly but the final amount-to-pay collapses to zero:

- `DP200014:00552` base imponible = 80000.00 (correct)
- `DP200014:00558` tipo de gravamen = 23 (correct)
- `DP200014:00562` cuota íntegra = 18400.00 (correct, = 80000 × 23%)
- `DP200014B:00599` cuota del ejercicio a ingresar = **0.00** (WRONG — expected ≈18400)

A company with €80 000 of taxable profit shows €0 to pay at year-end. The cuota íntegra never
reaches cuota líquida / cuota del ejercicio a ingresar.

**Root cause (confirmed 2026-06-21 at HEAD, after task #5's M202→M200 pagos fix — F2 is distinct and
still open):** casilla `DP200014B:00592` (cuota líquida) is declared `input_kind = "manual"` — it is
NOT computed from cuota íntegra (`DP200014:00562`) minus bonificaciones/deducciones. The downstream
chain is sound: supplying `--casilla DP200014B:00592=18400` makes `DP200014B:00599` (cuota a ingresar)
compute correctly to 18400.00. So the single defect is the missing cuota-íntegra → cuota-líquida
derivation: 00562 computes (18400) but 00592 stays a hand-entry box at 0, silently zeroing the final
result. The recommended fix is to make 00592 a computed casilla (cuota íntegra − the bonificación /
deducción casillas) rather than a bare manual input — the F2 analogue of F1 (a load-bearing casilla
left unbound). Commit `b06cf499f` added a non-blocking
*advisory* for the positive-íntegra / zero-líquida case (honouring no-silent-under-declaration at the
notice level), but the underlying number is still wrong. The M202 pagos-fraccionados fold-in is
separately gated (needs filed M202 1P/2P/3P), and is moot here because the chain breaks before it.

Reproduction: profile = legal_entity `--legal-entity-form sl` `--incn-prior-12-months 250000`;
`aeat app modelo work calculate --modelo 200 --year 2024 --period 0A --casilla 00500=80000
--casilla 00501=80000` plus the required `modelo-200-2024-profile-*` bindings; inspect 00562 vs 00599.

### F3 — HIGH — Modelo 303 base casilla 03 = 0 while cuotas populate (cuota-without-base)

On the audited profile's M303 revision, every quarter shows casilla 03 (base imponible devengado
general) = 0.00 while casilla 27 (cuota devengada) is correctly populated — a cuota-without-base form
AEAT rejects. The ledger IVA *base* aggregation binding (`0004-domestic-base...`) is present only on
the `2023-y-siguientes` 303 revision; revisions this profile resolves to have no base aggregation, so
the C2 base-aggregation remediation is only partially landed across revisions.

## Recommendations

- **F1 (M100 income):** add the missing aggregation surface that feeds the annual rendimiento neto de
  actividades económicas into Modelo 100 (casilla 0224 and the income chain) — either a ledger
  aggregation binding analogous to the M130 income/gasto resolvers, or an M130→M100 rendimiento
  relation (distinct from the existing pagos-fraccionados relation). Must enroll under the
  calculation-aggregation taxonomy, not a parallel mechanism. Pair with a no-silent-under-declaration
  guard so a year with declared activity income cannot produce a zero annual rendimiento.
- **F2 (M200 cuota):** repair the cuota íntegra → cuota líquida → cuota del ejercicio a ingresar
  (00562 → … → 00599) propagation so a positive cuota íntegra reaches the final box; upgrade the
  existing `b06cf499f` advisory to a computed value (or a blocking consistency check) once the chain
  is wired.
- **F3 (M303 base):** extend the `0004-domestic-base` ledger base aggregation to every supported 303
  revision (not only `2023-y-siguientes`) so casilla 03/07/28 never populate cuota without base.
- Add real end-to-end regression coverage that asserts the **annual** returns reproduce their
  headline figure from quarterly/ledger inputs (M100 annual rendimiento = Σ activity income − gastos;
  M200 cuota a ingresar = cuota íntegra − pagos), mirroring the M130/M390 continuity tests that
  already hold.

## Codification candidates

- **Source:** findings F1 (M100 annual income) and F2 (M200 cuota a ingresar).
  **Rule slug:** `annual-return-aggregates-its-headline-figure`.
  **Rule:** Every annual self-assessment modelo MUST derive its headline figure (the annual
  rendimiento / base and the final cuota a ingresar) from the period/ledger inputs, never leave it at
  an un-aggregated zero; when a positive economic input is declared but the headline annual figure
  resolves to zero, the verify gate MUST surface at least an advisory (no silent year-end
  under-declaration). This extends `no-silent-under-declaration` from the per-period verify gate to
  the end-of-year aggregate. Hold promotion until F1/F2 are fixed and the lesson has held across one
  execution cycle (per the codify discipline — first encounter is a finding, not yet a rule).
