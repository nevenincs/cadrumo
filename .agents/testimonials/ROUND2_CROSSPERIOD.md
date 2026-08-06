# Round 2 — cross-period NUMBER-correctness addendum (read with HARNESS.md)

Round 2 focus (operator directive): **the Modelo base calculations must be correct when we carry
deductibles, expenses, and IVA from prior periods into future periods, and the aggregate
end-of-year final calculations must be correct.** Your headline deliverable is a reconciliation
table proving the carried and aggregated NUMBERS are right — and flagging any that are wrong.

## Grounded design facts — DO NOT re-report these as bugs (already RAG-grounded + ADR-backed)
- **`export` is the local finish line; `work file` is OPTIONAL and only works while the obligation
  window is open** (`_engine.py`, `2026-05-21-work-verify-deadline-independence-adr`). Each period
  reaches its `.boe` via `export` independently of the window.
- **A dependent period's `verify` correctly BLOCKS** when the prior period has no official AEAT
  evidence — this is the safety gate (`local-filed-observations-are-non-official-evidence`,
  test `test_local_cross_period_carry.py` D1). It is BY DESIGN, not a deadlock bug.
- The CLI has **no `today` override**, so you cannot drive the in-window auto-carry file-chain end
  to end. That is fine: verify the **calculation numbers**, not the filing gate.

## How to exercise cross-period correctness via the CLI
Auto-carry from a filed prior needs in-window filing (not CLI-drivable here). Instead:
1. Per period, `calculate` supplying the prior-period carried value via `--binding KEY=VALUE`
   (previous_filing bindings accept `--binding`; discover keys with
   `aeat app modelo bindings list --modelo M --year Y --period P --missing`).
2. Read the `revision` casilla table and VERIFY the resulting base/cuota against the expected value
   you derive from the AEAT rule (NOT from the registry formula — no tautology).
3. For end-of-year, calculate the annual modelo (M100/M390/M200) and verify it correctly
   aggregates/folds the quarterly results.
- Profiles must DECLARE the modelo (autónomo M130 needs `--irpf-income-categories actividad_economica`
  + `--no-...objective`/estimación directa; IVA needs `iva.regime`; set `--activity-start-date` to the
  start of the declared year).

## Carry mechanisms + canonical casillas to check (verify the math)
- **M130 cumulative (deductibles/expenses carry):** casilla 01 = YTD income base, 02 = YTD gastos,
  03 = rendimiento neto (01−02), 04 = 20% of 03, **05 = Σ prior quarters' casilla 07** (RD 439/2007
  art. 110 — the GROSS positive results, NOT Σ casilla 19), 07 = result of apartado I, 19 = result.
  EOY: **M100** folds Σ pagos fraccionados (the four casilla-19 payments) as payments on account and
  the annual rendimiento neto de actividades económicas must equal the year's (Σ income − Σ gastos).
- **M303 (IVA carry):** 03/07 base devengado, 27 cuota devengada, 28 base soportado, 45 cuota
  deducible, 65 % atribución Estado, 71 resultado; **compensación**: a negative quarter produces
  "cuota a compensar" carried into the next quarter's casilla 110 ("a compensar de periodos
  anteriores"). EOY: **M390** annual IVA summary must reconcile to Σ of the four M303 quarters.
- **Recargo de equivalencia (retail regime):** the supplier-charged recargo cuota aggregates via the
  `recargo_amount_sum` fact into the M303 recargo casillas; verify it carries/sums correctly across
  periods (this aggregation landed recently — confirm the numbers).
- **Small company IS:** M202 quarterly pagos fraccionados → **M200** annual: cuota íntegra − Σ M202
  pagos = resultado a ingresar/devolver. (Known prior finding: cuota íntegra may not propagate to
  cuota a ingresar — re-check whether that's fixed.)

## Your testimonial (`.agents/testimonials/<slug>.md`) MUST include
1. A per-period reconciliation table: each input (income/gastos/IVA bases) → resulting casillas, with
   **expected vs actual** and a ✅/❌ per row. Derive expected from the AEAT rule, cited.
2. An explicit **carry-correctness** check: does period N+1 correctly use period N's carried value
   (deductible/expense/IVA/recargo/compensación)? expected vs actual.
3. An **end-of-year aggregate** check: does the annual modelo (M100/M390/M200) correctly fold/sum the
   quarters? expected vs actual.
4. Numbered findings with severity. A WRONG carried or aggregated number is **CRITICAL** (silent
   mis-declaration) — that is the primary thing this round hunts. Distinguish it from the
   already-grounded by-design gate behaviour above (do not re-file that as a bug).
Return a SHORT final message: verdict, the carry-correctness result (numbers), the EOY-aggregate
result (numbers), and your top findings. Full detail in the file.
