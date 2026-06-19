# Testimonial — TechVentura SL · Modelo 200 (IS) · 2024 · 0A

> **Re-verified 2026-06-19** against the live CLI. All six findings reproduce
> unchanged from the prior pass (no peer commit altered the behaviour):
> bindings-only calculate still yields a single non-zero casilla
> `DP200014:00558 = 23`; manual `00500/00501=80000` still propagates to
> `DP200014:00552=80000` → `00558=23` → `00562=18400` but `00592=0`/`00599=0`;
> M200 verify still `blocked` with 3× M202 `cross_period_dependency_unclean`
> (`missing_required_casilla_count=0`); `work file` on M202 still refused
> `NO_PENDING_OBLIGATION`; M202 export still `No se pudo escribir...`; M200
> export still refused `current revision is still draft`. No `.boe` produced.


## 0. Re-grounding & fixes (2026-06-19)

Each finding was re-grounded with `vaultspec-rag search --type code` and one
owner-clean fix was landed:

- **Finding 2 — FIXED.** Root cause grounded: the registry has a formula for cuota
  íntegra (`DP200014:00562`) and for cuota a ingresar (`00599`, which consumes
  `00592`), but **no formula links cuota íntegra → cuota líquida (`00592`)** —
  `00592` is `input_kind="manual"` (operator enters it after computing their own
  bonificaciones/deducciones, by design). The gap was a *silent grant*: a positive
  computed cuota íntegra (€18.400) could sit beside a zero cuota líquida and pass
  verify. Fix (mirrors the existing `00501→00552` base-determination advisory and
  the `no-silent-under-declaration` rule): added ADVISORY predicate
  `modelo-200-cuota-liquida-determinada-cuando-cuota-integra-positiva` =
  `implies_nonzero(["DP200014:00562", "DP200014B:00592"])` to
  `…/modelos/200/revisions/2024-y-siguientes/verification_expectations/0001-verification_predicates.toml`,
  plus a grounding registry test in `test_modelo_200_registry.py`. Re-running my
  verify now surfaces *"Modelo 200 cuota liquida determinada cuando cuota integra
  positiva"* (finding_count 6→7) — the silent zero-cuota is no longer silent.
  Kept ADVISORY (non-blocking) because deductions can legitimately absorb the
  cuota. 60/60 M200 + verification tests pass.
- **Finding 1 — by design + peer in progress.** M200 P&L (resultado contable) is
  operator-entered, like the M130 gastos case; the existing `00501→00552`
  advisory already guards the base stage and my new predicate now guards the cuota
  stage. A peer agent is concurrently implementing M130 gastos auto-aggregation
  (`modelo-130-gastos-total`, new `0004-m130-gastos-cumulative.toml`) — the F2
  surface. Not safe to also touch M130 here.
- **Finding 5 — root-caused, large campaign.** The M202 `.boe` export fails because
  `src/aeat/_data/registry/aeat/modelos/202/.../export/` **does not exist** (no
  Diseño de Registros authored for M202); `export_draft` raises `FilingExportError`
  which `_export.py:570` masks behind the generic `export_draft_write_failed`
  message. Real fix = authoring the official M202 fichero layout (M202-owned
  registry campaign). Out of scope for this pass.
- **Findings 3 (M202 cross-period gate) and 4 (new-entity scope-out)** are correct
  tax logic / a deeper cross-period-engine change in peer-WIP-adjacent files;
  grounded but not edited here to avoid colliding with concurrent peer work.

## 1. Persona

I am the administrator of **TechVentura SL**, a small software company (CIF
B12345674, "Desarrollo de software", started 2024-01-01). My job this session was
the annual **Impuesto sobre Sociedades, Modelo 200, ejercicio 2024**. The company
billed €200.000 of services (4 invoices of €50.000 base + 21% IVA) and incurred
€120.000 of deductible expenses, so the accounting result (resultado contable) is
about **€80.000**. I expected the tool to take my books and arrive at a corporate
tax cuota of roughly €80.000 × the IS rate. I wanted a compliant `.boe` to hand to
my gestor for filing.

> Simplification: I declared activity-start-date 2024-01-01 so the harness would
> scope out 2023 prior-year dependencies. That worked for 2023, but NOT for the
> in-year Modelo 202 fractional-payment dependency (see Findings 3-4).

## 2. What worked (first or second try)

- **Profile creation** — worked on the second try. First attempt failed only
  because I guessed `--legal-entity-form sociedad_limitada`; the CLI listed the
  valid choices (`sl, sa, sal, sll, cooperativa, ...`) and `sl` succeeded. Good
  instructive error.
- **Ledger import** — 8 rows, 8 imported, 0 skipped, first try.
- **Classification** — all 8 transactions (4 income + 4 expense) classified
  BUSINESS/reviewed first try. All four expense category-ids existed
  (`asesoria_contable`, `arrendamiento_local`, `software_suscripcion`,
  `material_oficina`).
- **Preflight** `--year 2024 --period 0A` — `checked 8, issues 0, ready true`,
  first try.
- **M200 work create / calculate** — created and calculated; calculate correctly
  refused until I supplied the 8 missing bindings, naming each one.
- **M202 1P sub-lifecycle** — create → calculate → verify reached
  `granted_verificado_completo true` cleanly (modality `art_40_2_optional`, all
  zeros — correct for a new entity with no prior cuota).

## 3. Friction / breakage

- **The books never reached the tax return.** After a full, clean calculate, the
  ENTIRE Modelo 200 was zero except the tax-rate casilla. My €200.000 income and
  €120.000 expenses did not aggregate into the cuenta de pérdidas y ganancias
  (casilla 00500) at all. A real taxpayer who trusted the tool here would file a
  €0 return on €80.000 of profit. This is the single most dangerous behaviour I hit
  (Finding 1).
- **Manual rescue only goes halfway.** When I hand-entered the resultado contable
  (`--casilla 00500=80000 --casilla 00501=80000`), the engine DID compute base
  imponible (€80.000) and cuota íntegra (€18.400 at the 23% micro-empresa rate).
  But the final "cuota del ejercicio a ingresar" (00599) stayed €0 — the íntegra
  never flowed down the liquidación chain (Finding 2).
- **Cross-period dead-end.** Verify is blocked by three `cross_period_dependency_unclean`
  findings for Modelo 202 (1P/2P/3P 2024). I filed M202 1P to verified-complete,
  but `work file` refused with `NO_PENDING_OBLIGATION` (the 2024 window is closed in
  2026), and the M200 gate explicitly needs *official* AEAT justificante evidence
  (`missing_observation, missing_current_filing_record`), which a local-only,
  first-party workflow cannot produce. There is no local path to clear it
  (Finding 3).
- **M202 export crashes.** Exporting the verified-complete M202 1P revision failed
  with `No se pudo escribir el archivo de exportacion` — no file written, no
  diagnostic cause (Finding 5).

## 4. Input → Output reconciliation

| Input | Amount | Target casilla | Auto-computed? | Value |
|---|---|---|---|---|
| Income (4 × €50.000 base) | 200.000 | P&G ingresos / 00500 | **NO** | 0 |
| Expenses (20k+40k+30k+30k) | 120.000 | P&G gastos / 00500 | **NO** | 0 |
| Resultado contable (derived) | 80.000 | 00500 | **NO** (manual only) | 0 → 80.000 when entered by hand |
| Base imponible previa | 80.000 | 00501 | manual (blocking-required) | 80.000 |
| Base imponible | 80.000 | DP200014:00552 | **YES**, from 00501 | 80.000 ✓ |
| Tipo de gravamen | 23% | DP200014:00558 | **YES** (micro-empresa, INCN<1M) | 23 ✓ |
| Cuota íntegra | 80.000 × 23% = 18.400 | DP200014:00562 | **YES**, from base × tipo | 18.400 ✓ |
| Cuota del ejercicio a ingresar | 18.400 (expected) | DP200014B:00599 | **NO** — chain breaks | 0 ✗ |

Expected cuota íntegra **€18.400** (micro-empresa tipo reducido 23%, INCN
€250.000 < €1M) — **matches** once resultado contable is hand-entered. The final
cuota a ingresar (00599) does **not** match: it stays €0.

## 5. Final artefact

**No `.boe` produced.** M200 export refused:
`current revision is still draft; verify it before exporting` — because verify never
granted (blocked by the M202 cross-period gate). M202 1P export also failed to write.
There is no compliant artefact to report sha256/byte_size for.

## 6. Findings

### Finding 1 — CRITICAL — Ledger P&L is NOT aggregated into Modelo 200 (silent under-declaration)
After a clean `calculate` with all 8 bindings supplied, the only non-zero casilla in
the whole form was the tax rate. Resultado contable (00500), base (00552) and cuota
(00562) were all `0` despite €200.000 income / €120.000 expenses / €80.000 profit in
the classified, preflight-clean ledger.
Proof:
```
$ aeat app modelo work revision --modelo 200 --year 2024 --period 0A | grep -v "\t0$"
casilla  DP200014:00558  23     # ONLY non-zero casilla
```
A taxpayer who exported here (if verify allowed it) would file a €0 IS return on
€80.000 of profit. This is the M200 analogue of the harness F2 expense-drop note,
but far worse: for IS the *entire* P&L, not just expenses, is dropped. **Works as
coded, but the number is catastrophically wrong for an unaided filer.**

### Finding 2 — HIGH — Cuota íntegra does not propagate to cuota a ingresar
Hand-entering resultado contable propagates base→tipo→cuota íntegra correctly
(€18.400), but the íntegra never reaches cuota líquida / cuota del ejercicio a
ingresar (00599 = 0).
Proof:
```
$ ... calculate --casilla 00500=80000 --casilla 00501=80000 ...
casilla  DP200014:00562  18400.00   # cuota íntegra OK
casilla  DP200014B:00599 0.00       # cuota a ingresar still ZERO
```
The liquidación chain (00562 → 00592 → 00599) is incomplete, so the headline
amount-to-pay is always €0. Data-loss / wrong-number, not just confusing.

### Finding 3 — HIGH (blocking) — M202 cross-period gate is unclearable in local-only mode
M200 verify is blocked by three `cross_period_dependency_unclean` findings
(modelo=202, 2024, 1P/2P/3P). The gate demands official AEAT evidence
(`blockers=missing_observation, missing_current_filing_record`). I verified M202 1P
to complete, but:
- `aeat app modelo work file --modelo 202 ... 1P` → refused `NO_PENDING_OBLIGATION`
  (2024 window closed in 2026).
- Local "file" observations are `app_filing` (non-official by the
  `local-filed-observations-are-non-official-evidence` rule) and cannot satisfy the
  clean-state gate anyway.
- No live AEAT pull and no real justificante PDF exist in a first-party simulation.
There is **no local path** to a verified M200. This is the documented hard stop.

### Finding 4 — MEDIUM — New-entity first-year M202 obligation is not scoped out
The engine correctly scoped out the 2023 M200 dependency as
`no-prior-obligation (pre-activity)`, but did NOT apply the same reasoning to the
2024 M202 fractional payments. A company created 2024-01-01 under modalidad cuota
(art. 40.2) has **no prior cuota and therefore no M202 obligation in its first
year** — yet the gate treats the absence of M202 filings as an unclean dependency
rather than "no obligation". The pre-activity scope-out logic should extend to
"obligation legally does not arise" cases, not just date-before-activity.

### Finding 5 — MEDIUM — M202 export write failure on a verified-complete revision
```
$ aeat app modelo export --modelo 202 --year 2024 --period 1P --output .../m202-1p.boe
Failed. No se pudo escribir el archivo de exportacion para la revision ...
```
No file written, no root-cause in the message. A verified-complete revision should
export or give an actionable reason.

### Finding 6 — LOW / INFO — Overdue recargo advisory fires correctly
Creating/calculating M200 for 2024 in 2026 surfaced `days_overdue 328`,
`recargo_band within_12_months`, `recargo_pct 12.00`, `ley-58-2003:art-27.2`. This
is correct, helpful behaviour — noted only for completeness.

## 7. Verdict

**No compliant `.boe` reached.** A real TechVentura administrator would **fail
unaided**, for two independent reasons:
1. Even if the cross-period gate were cleared, the tool produces a €0 return unless
   the operator manually keys resultado contable and base imponible previa — the
   ledger is never used for the IS P&L (Finding 1), and the cuota-a-ingresar chain
   is broken (Finding 2).
2. The M202 cross-period gate cannot be satisfied locally (Finding 3); for a
   genuinely-not-obligated first-year entity it arguably should not fire at all
   (Finding 4).

The KEY QUESTION is answered: **the IS engine does NOT compute base imponible or
cuota from the ledger.** It leaves resultado contable manual/zero (silent
under-declaration). It *does* compute cuota íntegra from a hand-entered base
(€80.000 × 23% = €18.400, correct), but stops short of the final cuota a ingresar.
