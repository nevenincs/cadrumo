# Batch 2 — persona queue (dispatch once C0+C2 land on a stable tree)

Two purposes: (A) **re-verify** the C0/C1/C2/H1 fixes via fresh personas (not just coordinator spot-checks); (B) **extend coverage** to untrodden modelos/entity types. Each follows HARNESS.md (isolated `AEAT_SECRET_STORE_DIR` + custom passphrase, file backend). Max 6 concurrent. Watch for report-stage freezes — read the testimonial file directly if a persona goes idle without a summary.

## A. Re-verification personas (highest value — confirm the fixes hold end-to-end)
1. **reverify-130-cumulative** (slug `reverify-130-cumulative`) — repeat Marco: €20k/yr, 5000 base/quarter, no expenses, M130 1T→2T→3T→4T then M100. EXPECT (post-C0): all 4 quarters `work file` succeeds (extemporáneo marker), casilla 05 auto-carries 0/900/1900/2900 with NO manual `--binding`, each quarter verifies (non-official-local-chain advisory, non-blocking) and exports → **4 of 4 + M100 fold-in** (was 1 of 5). Pass/fail the cross-period carry + fold-in.
2. **reverify-iva-compensacion** (slug `reverify-iva-compensacion`) — repeat Pablo: M303 1T (income base 1000, expense base 3000 → −420 a compensar) then 2T (income 5000, expense 500). EXPECT (post-C0+C1+C2): 1T exports unaided; 2T auto-carries the 420 into casilla 110 → resultado **525** (not 945); both export with ZERO manual `--binding`/`--casilla`. Pass/fail compensación carry.
3. **reverify-303-full-unaided** (slug `reverify-303-full-unaided`) — repeat Lucía: M303 2T income bases 3000/2000/1500, expenses 200/100. EXPECT (post-C1+C2): casilla 03/07 base devengado = 6500, casilla 28 base soportado = 300, repercutido 1365, soportado 63, prorrata 100, resultado 1302, verify grants, `.boe` exports — with ZERO workarounds (no manual casilla 07/28/65, no prorrata trick). Confirms H1-M303 + C1 + C2 together.

## B. Coverage-extension personas (new surfaces)
4. **atribucion-cb-184** (slug `atribucion-cb-184`) — a Comunidad de Bienes, entity-type `attribution_entity`, CIF E-form. Files **Modelo 184** (entidades en atribución de rentas, informativa anual) for 2024. Income base 40000 across the year, 2 comuneros at 50/50. Tests the attribution_entity path + an informative modelo. Report how member attribution is modelled and whether M184 exports.
5. **retenciones-111-115** (slug `retenciones-111-115`) — an autónomo who is also an employer + rents a local. Files **Modelo 111** (retenciones del trabajo, 1T: paid an employee 6000 gross, retención 900) and **Modelo 115** (retenciones alquiler, 1T: paid local rent 3000, retención 19% = 570). Tests profile_based/quarterly retención modelos. Report whether retención amounts aggregate or are manual.
6. **m390-annual-iva** (slug `m390-annual-iva`) — autónomo files 4× M303 (income base 5000/quarter, expense base 500/quarter, 21%) then the **Modelo 390** annual IVA resumen for 2024. Tests the annual-IVA cross-calculation: does M390 fold in / reconcile against the four M303 quarters? Report the M390←M303 aggregation and whether M390 exports. (Also a second cross-period/annual reconciliation data point alongside M130→M100.)

## Notes for dispatch
- Personas 1-3 are the priority — they are the acceptance test for the whole hardening campaign. If any fails, that fix regressed.
- M210 IRNR deferred to a later batch (ad_hoc, non-resident — lower overlap with the fixes).
- Each persona: full lifecycle to `.boe`, input→output reconciliation table, numbered findings w/ severity, short final summary + full testimonial in `.agents/testimonials/<slug>.md`.
