# Testimonial — Marco Ruiz, autónomo (Modelo 130 cumulative + Modelo 100 fold-in)

**Slug:** `autonomo-130-cumulative` · **Profile:** `marco` · **NIF:** 34567890V
(see Finding 1) · **Entity:** natural_person · **Activity:** "Consultoría
informática", start 2024-01-01.

## Remediation status (code fixes landed this session)
- **Finding 7 (CRITICAL) — FIXED.** `project_modelo_100_from_m130`
  (`src/aeat/application/modelo/_projection.py`) now reads the **latest quarter's
  cumulative** casilla 03/01/02 (extrapolated by `4 / latest_ordinal` for a
  partial year) instead of summing the per-quarter cumulative snapshots.
  Verified on Marco's profile: M100 income input is now `0171 = 20000.00`
  (was 50000.00); the pagos-fraccionados fold-in stays correct at 3900.00.
- **Finding 8 (HIGH) — FIXED.** The projection CLI
  (`_modelo_projection_cli.py`) now routes `RegistryValidationError` through
  `bad_parameter_from_error`, surfacing the actionable
  *"Falta el valor de la vinculacion de fecha"* instead of the opaque
  *"Error interno: el cálculo del Modelo 100 ha fallado"*. Orphaned locale key
  `cli.app.modelo.project.m100_calculation_error` retired via `aeat.locales scaffold`.
- **Finding 5 (MEDIUM) — FIXED.** The calculate path
  (`src/aeat/application/modelo/_calculate_input.py`) now detects a date-valued
  (profile-sourced) binding supplied via `--binding` and refuses it with an
  actionable message — *"…is a date-valued binding sourced from the active
  profile … Set it as a profile fact (e.g. `--taxpayer-birth-date YYYY-MM-DD`)"*
  — instead of the misleading *"is not a decimal"* coercion failure. New
  `_date_binding_ids(revision)` helper (reuses `expression_date_binding_refs`);
  new localized key `application.modelo.errors.calculate_binding_is_date_sourced`
  in all 4 locales; unit test in `test_calculate_binding_channel.py`.
- **Finding 2 (MEDIUM) — RESOLVED by peer.** M130 casilla 02 (gastos) is now
  `input_kind = "computed"` (`02-libro + 02-ajuste`); a zero-expense filer no
  longer needs to declare `--casilla 02=0`.
- **Finding 1 (LOW) — NOT A DEFECT.** The NIF control-letter validation is
  correct; the briefed NIF (`…B`) was simply invalid (`…V`). No code change.
- **Uniqueness / canonical-source audit (RAG axis 7).** The F5 fix initially
  duplicated a date-binding-id walk already present in `application/filing`
  (`_date_binding_ids`). Consolidated to a single canonical
  `revision_date_binding_ids(revision)` in
  `domain/calculations/registry/_runtime_graph.py` (sibling of
  `enum_consumed_binding_ids`), exported via the registry package `__all__`; both
  the modelo calculate-input path and the filing replay path now consume it
  through the top-level re-export (no cross-package private import). Audit also
  confirmed the projection annualization is the only M130-quarterly→annual site
  and the cumulative-sum income bug existed nowhere else (the live pagos-fold-in
  path sums only the incremental casilla 19, which is correct).
- Regression test `test_modelo_project_m130_to_m100_full_year_aggregation`
  rewritten to a realistic growing-cumulative scenario (4 quarterly cobros →
  cumulative 12k/24k/36k/48k, annual basis 48k, Σ pagos 9600). All 4 tests in
  `test_modelo_projection.py` pass; all 4 in `test_calculate_binding_channel.py`
  pass; my locale key registered clean in all 4 catalogues.
- **Finding 6 — NOT A DEFECT (RAG-grounded).** RAG/code grounding
  (`test_modelo_130_multiyear_renta_enrollment.py`) shows casilla 13 is
  *"Minoración por aplicación del artículo 110.3.b RD 439/2007"* and is **correctly**
  bound to `irpf.previous_year_economic_activity_net_income` — it is the prior-year
  minoración fold-in of the multi-year renta chain, not the current-cumulative
  basis I initially suspected. `test_modelo_calculation_through_real_cli.py`
  confirms the 12.000 threshold applies to that prior-year value. For Marco
  (first-year, €0 prior → ≤9.000 → €100) the flat €100 is correct. No change; my
  original suspicion was wrong — grounding it (rather than editing the formula)
  was the right call per `registry-calculation-legal-grounding`.
- **Finding 4 — BY DESIGN (RAG-grounded safety).** `test_local_cross_period_carry.py`
  documents the exact invariant: "a locally-filed 1T does NOT let 2T FILE — it
  still blocks on evidence … the non-official source is the single decision that
  keeps the carry from laundering an unevidenced chain past the filing gate."
  Auto-carry feeds calculate/draft; verifying/filing a dependent period requires
  real external AEAT evidence. Intentional per
  `local-filed-observations-are-non-official-evidence` / `aeat-safety-legal-gates`.
  Not an autonomous change.
- **Finding 3 — ALREADY BEING FIXED BY A PEER (RAG-grounded).** The workflow
  engine now carries **Decision A** (`src/aeat/application/workflow/_engine.py:425-442`):
  for an explicitly-targeted closed-window prior period it resolves the schedule
  in the *target* period's filing year and records a late local filing
  (*extemporánea, con recargo*) — "the late-filer / prior-year reconstruction path
  that seeds the cross-period carry." Re-tested at HEAD: `work file` no longer
  refuses with `NO_PENDING_OBLIGATION`; it now reaches the filing path (currently
  blocked only by a transient peer gap — `ModeloExportOutputPathError` not yet in
  the error-code registry, mid-flight peer work). F3 is therefore owned by an
  in-progress peer change, not an open defect for this campaign.
- **Pre-existing peer regressions noted (not mine):** `test_modelo_compare.py`
  (2 tests) and `test_modelo_work_natural_key.py` (1 test) fail with "Computed
  casillas cannot be supplied as inputs: 02" — collateral of the casilla-02
  flip. The locale codebase-to-locale parity gate is red on 5 keys from an
  in-flight invoice-lifecycle feature (`application.invoices.lifecycle.errors.*`,
  `cli.app.ledger.invoice.catalogue.operation_type_unsupported`). Both are owned
  by their respective peer changes; left untouched to avoid colliding with their
  sweeps.

## 1. Persona
I am Marco, an IT consultant working as an autónomo. In 2024 I invoiced exactly
€20,000 (four invoices of €5,000 base + 21% IVA = €6,050 gross each, one per
quarter) with **no expenses**. I needed to file my four cumulative **Modelo 130**
pagos fraccionados (1T–4T 2024) and then my annual **Modelo 100 (Renta)** that
folds those four payments in as payments on account. I am the flagship
cross-period reconciliation case.

## 2. What worked (first try)
- Profile creation (once the NIF letter was fixed), `--activity-start-date`
  scoping out the 2023 pre-activity dependency.
- CSV import (semicolon/Spanish/comma-decimals) — 4 rows, 0 skipped.
- Classification of all 4 invoices (base 5000 / iva 1050 / domestic_general_21).
- Preflight: 0 issues, ready=true for every quarter.
- **Cumulative income auto-aggregation (casilla 01)**: M130 aggregates ledger
  income cumulatively by date window. Each quarter the AVISO lines correctly
  drop the future-quarter invoices from the cumulative window. 1T=5000,
  2T=10000, 3T=15000, 4T=20000 — exactly as a cumulative M130 should.
- 1T full lifecycle: create → calculate → verify (granted) → export `.boe`.

## 3. Friction / breakage
- **NIF control letter (Finding 1):** the briefed NIF `34567890B` was refused —
  the CLI computed the correct control letter is `V`. The error was precise and
  actionable (named the expected letter). I used `34567890V`.
- **Casilla 02 mandatory even at zero (Finding 2):** first verify of 1T blocked
  with `missing_required_casilla 02` (Gastos). With *no expenses* I still had to
  re-calculate with `--casilla 02=0`. Actionable message, but a real
  zero-expense taxpayer would not expect to declare an empty box manually. This
  matches the harness F2 note.
- **`work file` refused for the closed window (Finding 3):** `work file` aborts
  with `NO_PENDING_OBLIGATION` ("the AEAT filing-obligation window is not open")
  for any 2024 period at the 2026 clock. The message says export is the finish
  line — true for a *single* period, but `work file` is the step that persists
  the local filed observation the *next* quarter needs (see Finding 4).
- **Cross-period carry does NOT auto-resolve (Finding 4 — CRITICAL):** 2T
  calculate errored `la vinculación modelo-130-pagos-fraccionados-anteriores no
  tiene valor asignado`. `work dependencies` shows 1T as
  `clean=False, blockers=missing_observation, missing_current_filing_record`. So
  the prior-payments carry could not read 1T automatically. I had to supply it
  by hand (`--binding modelo-130-pagos-fraccionados-anteriores=<sum>`).
- **Export of 2T/3T/4T blocked (Finding 4):** even with the carry supplied
  manually, 2T verify is `completeness_status=blocked` with blocking finding
  `cross_period_dependency_unclean` (1T `missing_observation,
  missing_current_filing_record`). Export refuses a non-verified revision, so
  **no `.boe` for 2T, 3T, 4T**. The only remedy offered is to pull/reconcile an
  official AEAT justificante for 1T — impossible for a never-officially-filed
  local reconstruction.
- **M100 date binding can't be supplied via `--binding` (Finding 5):** the
  `profile`-source date bindings (e.g. `renta-2024-profile-taxpayer-birth-date`)
  reject `--binding`: `=0` → "Falta el valor de la vinculacion de fecha"; a date
  string → "is not a decimal: '1980-01-01'". The `--binding` channel is
  decimal-only, so date-typed profile bindings are unsatisfiable that way; they
  must be on the profile, set at creation (`profile create` refuses to overwrite
  an existing profile; only the interactive `edit` wizard remains).

## 4. Input → Output reconciliation

### Per-quarter M130 casilla table (all carries supplied manually)
| Casilla | label | 1T | 2T | 3T | 4T |
|---|---|---|---|---|---|
| 01 | Ingresos (cumulative) | 5000 | 10000 | 15000 | 20000 |
| 02 | Gastos | 0 | 0 | 0 | 0 |
| 03 | Rendimiento neto | 5000 | 10000 | 15000 | 20000 |
| 04 | Pago fraccionado (20%) | 1000 | 2000 | 3000 | 4000 |
| 05 | Pagos fraccionados anteriores (carry) | 0 | 900 | 1900 | 2900 |
| 07 | Resultado parcial apartado I | 1000 | 1100 | 1100 | 1100 |
| 12 | Suma resultados parciales | 1000 | 1100 | 1100 | 1100 |
| 13 | Minoración rendimientos netos | 100 | 100 | 100 | 100 |
| 14 | Neto tras minoración | 900 | 1000 | 1000 | 1000 |
| 19 | **Resultado final** | **900** | **1000** | **1000** | **1000** |

### Cross-period carry verification (casilla 05 = Σ prior resultados)
| Quarter | expected prior-payments | actual casilla 05 | match |
|---|---|---|---|
| 2T | 900 (1T) | 900 | ✅ |
| 3T | 1900 (900+1000) | 1900 | ✅ |
| 4T | 2900 (900+1000+1000) | 2900 | ✅ |

The carry **arithmetic is correct and internally consistent** — *but only because
I computed and supplied each carry by hand*. The tool did **not** carry
automatically and **cannot** verify/export the dependent quarters (Finding 4).
Total annual pagos fraccionados Σ(casilla 19) = 900+1000+1000+1000 = **€3,900**.

### Minoración observation (Finding 6)
Casilla 13 stays a flat **100** for every quarter (cumulative income 5000 →
20000). The registry formula `modelo-130-minoracion-rendimientos-netos` gates the
gradation (100/75/50/25/0) on the binding
`irpf.previous_year_economic_activity_net_income`, which I set to 0 (first year)
→ always 100. If the AEAT casilla-13 basis is the *current-period cumulative*
rendimiento neto (the form text the formula cites says "igual o inferior a 12.000
euros"), then at 3T/4T (cumulative 15000/20000 > 12000) the minoración should be
**0**, and the flat 100 under-declares the pago. For a genuine first-year filer
with €0 prior income the flat 100 may be defensible, but a €20k earner receiving
any art.110.3.c minoración is questionable. **Grounding check recommended.**

### M130 → M100 fold-in (re-reviewed — corrected)
Two paths exist and they behave differently:

**(a) M100 work-unit lifecycle** (`work create/calculate/verify/export`): the
fold-in binding `renta-2024-modelo-130-pagos-fraccionados` (source
`relation_prefill`) is gated by clean state. `work dependencies` for M100 2024 0A
lists **all four M130 quarters + M100/2023 0A** as
`missing_observation, missing_current_filing_record`. So the work-unit path
cannot verify/export (same deadlock as Finding 4), and it additionally needs
~17 bindings incl. date-typed profile data unsatisfiable via the CLI (Finding 5).

**(b) `aeat app modelo project --year 2024 --ccaa madrid`** (annual projection):
this path reads the latest M130 calculation revisions **directly, with no filing
records required**, and **the pagos-fraccionados fold-in resolves correctly**:
`relations={'renta-2024-rel-130-pagos-fraccionados': 3900.00}` = Σ(casilla 19) =
900+1000+1000+1000. ✅ The €3,900 of payments-on-account IS folded in correctly.

BUT path (b) has two serious defects:
- **Income overstated 2.5× (Finding 7, CRITICAL):** `project` sums the
  **cumulative** M130 casilla 03 across the four quarters →
  5000+10000+15000+20000 = **50000**, and feeds that as M100 income
  (`inputs={'0171': 50000.00}`). The true annual net income is **20000**
  (the 4T cumulative value). M130 casilla 03/01 are year-to-date cumulative, so
  summing them quadruple-counts. The extrapolation branch
  (`total_rendimiento_neto * 4 / quarters_filed`, `_projection.py:244`) confirms
  the code assumes per-quarter *incremental* income — wrong for cumulative M130.
  casilla 19 (pago) is genuinely incremental, so the 3900 credit is right; the
  income basis is not.
- **Opaque crash on missing birth-date (Finding 8, HIGH):** with the above
  income, `project` then aborts. The real cause (logged traceback) is
  `RegistryValidationError: date_binding
  'renta-2024-profile-taxpayer-birth-date' has no supplied value; required by
  age_at_year_end` (`_projection.py:316` → `_formula_runtime.py:848`). It is
  swallowed and surfaced to the operator only as `Invalid value: Error interno:
  el cálculo del Modelo 100 ha fallado` — no hint to set the birth date.

Net: the fold-in *credit* is correct (3900), but no M100 `.boe` is reachable —
work-unit path is clean-state-blocked, projection path crashes and would in any
case compute renta on a 50000 phantom income.

## 5. Final artefacts (`.boe`)
| Modelo/period | output | byte_size | sha256 |
|---|---|---|---|
| 130 1T 2024 | `tmp/personas/autonomo-130-cumulative/m130-1T.boe` | 946 | `8c79cfd1cf193c9a119097f66daa92afcd0e36081542fb0eecf6772c5367b1fb` |
| 130 2T 2024 | **BLOCKED** (cross_period_dependency_unclean) | — | — |
| 130 3T 2024 | **BLOCKED** | — | — |
| 130 4T 2024 | **BLOCKED** | — | — |
| 100 0A 2024 | **BLOCKED** (fold-in deps unclean + profile data gap) | — | — |

**1 of 5 `.boe` files produced.**

## 6. Findings (numbered, with severity)
1. **NIF control-letter rejection — LOW (works as designed):** briefed NIF
   `34567890B` invalid; CLI named correct letter `V`. Used `34567890V`.
2. **Mandatory casilla 02 at zero — MEDIUM (UX):** zero-expense M130 still
   blocks verify until `--casilla 02=0` supplied. Confirms harness F2.
3. **`work file` refuses closed/overdue windows — MEDIUM:** `NO_PENDING_OBLIGATION`
   for past 2024 periods at 2026 clock, while M100 create itself shows
   "plazo voluntario vencido… presenta con recargo" — i.e. the system
   acknowledges overdue filing but `work file` blocks it. Inconsistent messaging.
4. **Cross-period carry chain is deadlocked for historical reconstruction —
   CRITICAL:** the prior-payments carry (a) does not auto-resolve and (b) the
   dependent quarter's verify is hard-blocked by `cross_period_dependency_unclean`
   because the prior quarter has no observation/filing record. The only thing
   that creates that local observation is `work file`, which is itself refused
   for closed windows (Finding 3). Net effect: a first-time/local-only taxpayer
   reconstructing a past year can export **only the first quarter**; 2T–4T and
   the M100 fold-in are unreachable without official AEAT justificante evidence
   they never produced. Proof: `work verify 130 2T` →
   `cross_period_dependency_unclean blocking … blockers=missing_observation,
   missing_current_filing_record`.
5. **Date-typed profile bindings unsatisfiable via `--binding` — MEDIUM:**
   `--binding renta-2024-profile-taxpayer-birth-date=…` rejects both `0`
   ("Falta el valor de la vinculacion de fecha") and a date ("is not a decimal").
   Channel is decimal-only; the only path is profile personal data, but
   `profile create` refuses to overwrite, leaving only the interactive wizard.
6. **Casilla 13 minoración basis — MEDIUM (grounding, verify):** gated on
   `irpf.previous_year_economic_activity_net_income`, not current cumulative net
   income; yields a flat €100/quarter. For Marco (first-year, €0 prior income) a
   flat €100 is at least internally consistent with the formula, but if the
   art.110.3.c basis is the current cumulative net income, the minoración should
   phase to 0 at 3T/4T (cumulative >12,000). Worth a grounding cross-check; not
   escalated absent corpus confirmation of the M130 casilla-13 basis.
7. **`project` overstates annual income 2.5× — CRITICAL:**
   `project_modelo_100_from_m130` (`src/aeat/application/modelo/_projection.py:226`)
   sums the **cumulative** M130 casilla 03 across quarters
   (5000+10000+15000+20000 = 50000) and feeds it as M100 income `0171`, where the
   true annual net income is 20000. The extrapolation branch
   (`total*4/quarters_filed`, line 244) confirms the code treats cumulative M130
   figures as incremental. The pagos-fraccionados credit (casilla 19, incremental)
   sums correctly to 3900; only the income basis is wrong. Proof:
   `aeat app modelo project --year 2024 --ccaa madrid` →
   `inputs={'0171': Decimal('50000.00')} … relations={'renta-2024-rel-130-pagos-fraccionados': Decimal('3900.00')}`.
8. **Opaque internal error on missing birth-date — HIGH:** `project` aborts with
   `Invalid value: Error interno: el cálculo del Modelo 100 ha fallado`; the real,
   actionable cause is only in the logged traceback —
   `RegistryValidationError: date_binding 'renta-2024-profile-taxpayer-birth-date'
   has no supplied value; required by age_at_year_end`
   (`_projection.py:316` → `_formula_runtime.py:848`). The
   `except RegistryValidationError` at `_projection.py:325` swallows the detail.
   A taxpayer gets a dead-end generic error.
9. **POSITIVE — M130→M100 pagos-fraccionados fold-in is correct:** via `project`
   the four payments aggregate to exactly €3,900 (Σ casilla 19), reading the
   quarterly revisions directly without any filing record. (This corrects the
   prior delivery's claim that the fold-in "cannot resolve".)

## 7. Verdict
**Partial failure for the cross-period scenario.** Single-period mechanics are
solid: profile, import, classify, cumulative-income aggregation (casilla 01),
calculate, verify and export all work for 1T, producing a valid 946-byte `.boe`.
The **cross-period carry arithmetic is correct when fed manually**, and the
**M130→M100 pagos-fraccionados fold-in is correct** (€3,900 via `project`,
no filing records needed). But the end-to-end cumulative chain the coordinator
cares about is **deadlocked / broken**: the tool will not auto-carry, will not
let the dependent quarters verify/export, and will not file the prior quarter to
unblock them — so 2T/3T/4T never reach a `.boe`. The M100 projection path that
*does* fold the payments in **overstates annual income 2.5×** (sums cumulative
M130 casilla 03 → 50000 vs true 20000, Finding 7) and then **crashes with an
opaque error** on the missing birth date (Finding 8), so no M100 `.boe` is
reachable either. A real autónomo reconstructing 2024 today would get exactly
one quarter out and hit a wall. **Would NOT succeed unaided** for the full
four-quarter + Renta filing.
