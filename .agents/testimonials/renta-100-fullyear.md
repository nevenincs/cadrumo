# Testimonial — Elena Navarro, Modelo 100 (Renta) 2024 annual

**Persona slug:** `renta-100-fullyear`
**Run date:** 2026-06-18
**Backend:** real `aeat` CLI on `chore/eliminate-shims`, isolated storage root `tmp/personas/renta-100-fullyear`.

---

## 1. Who I am

I am Elena Navarro, NIF **67890123B**, a salaried employee in Madrid with one small
urban rental flat. I file the annual **Renta (Modelo 100) for 2024**, individual
(taxation-type 1), single, born 1985. My whole year is two things:

- **Salary** (rendimiento del trabajo): €30,000 gross, €4,500 IRPF withheld (retención).
- **Rent** (capital inmobiliario): €500/month × 12 = €6,000 from an urban flat.

Total income €36,000. No business, no autónomo activity, no quarterly filings. I am
the most ordinary taxpayer Spain has. I wanted one thing: a verified `.boe` for my
annual return.

**I did not get it.** I reached a fully *computed* draft (resultado €2,953.10 to pay),
but the tool **refuses to verify or export** it because it demands AEAT evidence for a
year's worth of withholding and instalment forms (modelos 111/115/123/130/131/193) that
**I have no legal obligation to file** — my employer files 111, not me; I never touch
130 or 131. A salaried employee with a rental cannot, with this tool and only local
data, produce a compliant Modelo 100.

---

## 2. What worked

- **Profile creation** worked once I used a valid NIF and ISO dates. The CLI even
  computed my correct control letter for me (see Friction).
- **Ledger import**: my 24-row semicolon CSV (12 nómina + 12 alquiler rows) imported
  cleanly first try (`Filas 24 / Entradas importadas 24 / Omitidos 0`).
- **Work unit create** (`modelo work create --modelo 100 --year 2024 --period 0A`)
  succeeded and correctly warned the 2024 plazo is vencido (filed 2026-06-18, 353 days
  overdue → recargo 12% Art. 27 LGT). Correct and informative.
- **The IRPF calculation chain itself is correct and impressive** once I hand-fed the
  income. Entering salary into casilla 0003 and rent into 0102 produced a complete,
  plausible cascade: rendimientos netos, base imponible, base liquidable, the **mínimo
  personal €5,550** (computed automatically from my profile birth-date), cuota íntegra
  estatal + autonómica, and the final resultado. The engine clearly *can* do the maths.

---

## 3. Friction / breakage (in the order I hit it)

1. **NIF rejected.** My brief NIF `67890123E` was refused: *"La letra de control del
   NIF es incorrecta: para 67890123 la letra de control debe ser B, no E."* The message
   is excellent — it computed and named the right letter. I used `67890123B`. (Brief
   data error, not a tool bug, but worth recording.)

2. **17 bindings, surfaced one at a time.** A bare `work calculate` failed with a
   *single* missing-binding error, not a list. I had to run
   `bindings list --modelo 100 --year 2024 --period 0A --missing` (17 entries) and
   supply each. For the simplest possible taxpayer that is 15 numeric bindings I set to
   0 by hand, plus 2 that resolve from the profile.

3. **The birth-date binding is unsatisfiable via `--binding`.**
   `renta-2024-profile-taxpayer-birth-date` is typed **`decimal`** in `bindings list`,
   but the engine rejects `=0` with *"Falta el valor de la vinculacion de fecha"* and
   rejects `=1985-05-15` with *"is not a decimal: '1985-05-15'"*. There is no value that
   satisfies it through `--binding`. It must be set on the **profile**
   (`--taxpayer-birth-date`). The error also never names *which* binding is the offending
   date — it just says "the date binding", so with several profile-date facts you cannot
   tell which one to fix.

4. **Profile date format inconsistency.** `--taxpayer-birth-date 15/05/1985` (Spanish
   dd/mm/yyyy — the exact format the import CSV requires) was rejected
   (`invalid_date_value`). Only ISO `1985-05-15` is accepted. Two different date dialects
   on two surfaces of the same tool.

5. **Income does not come from the ledger at all.** This is the big one. M100 has
   **2,059 casillas, 1,882 of them manual**. My 24 imported, real income rows contributed
   **nothing** to the form. Salary and rent had to be typed by hand into casillas 0003
   and 0102. Worse, `ledger preflight --year 2024 --period 0A` emitted **24
   `missing_business_classification` issues** ("business classification 'NOT_YET_PROCESSED'
   is not ready") — the ledger/preflight pipeline is built for IVA/business income and is
   simply irrelevant to a personal IRPF return, yet it actively reports my salary and rent
   as errors.

6. **Silent loss of the bottom-line resultado.** With income entered but before I
   discovered the pagos-fraccionados *relations*, the engine computed cuota líquida
   (0595 = €7,453.10) **but silently dropped casillas 0604, 0609, 0610 and 0670 — the
   resultado de la declaración itself**. They were simply *absent* from the revision
   (their neighbours all emitted 0). The only signal was a non-blocking `AVISO`. The fix
   was to pass `--relation renta-2024-rel-130-pagos-fraccionados=0` and the 131 sibling —
   **but those relation ids are NOT listed by `bindings list --missing`**, so there is no
   discoverable way to learn they are required. A taxpayer would see a cuota but no
   "to pay" figure and have no idea why.

7. **Verify is hard-blocked; export refused.** `work verify` returns
   `completeness_status = blocked`, `granted_verificado_completo = false`,
   `finding_count = 35` with **~33 blocking `cross_period_dependency_unclean` findings**
   demanding AEAT justificante evidence for modelos 111 (12 monthly + 4 quarterly), 115
   (4), 123 (4), 130 (4), 131 (4), 193 (annual). `modelo export` then refuses:
   *"current revision is still draft; verify it before exporting."* The only suggested
   remediations are a **live AEAT pull** (`live filed pull-sources`) or a **justificante
   PDF** (`reconcile file --file PATH`) — neither available to an employee who never filed
   those forms. There is no "I have no such obligation" path. `activity-start-date
   2024-01-01` only scoped out the **2023** prior-year dependency (1 advisory); it does
   **not** scope out the same-year 2024 intra-period relations.

---

## 4. Input → Output reconciliation

All figures below are engine output read from `modelo work revision` after I manually
entered salary (0003=30000) and rent (0102=6000) and supplied retención via
`--binding renta-2024-modelo-111-retenciones-periodicas=4500` and the two pagos-
fraccionados relations =0.

| Input (mine) | Casilla | Engine value | Expected | Match? |
|---|---|---|---|---|
| Salary gross €30,000 | 0003 Retribuciones dinerarias | 30000.00 | 30000 | ✅ (manual entry) |
| → rendimiento neto trabajo | 0022 | 30000.00 | 30000 (no gastos/SS entered) | ✅ but see note |
| → rend. neto reducido | 0025 | 30000.00 | 30000 | ✅ |
| Rent gross €6,000 | 0102 Ingresos íntegros computables | 6000.00 | 6000 | ✅ (manual entry) |
| → rend. neto inmobiliario | 0149 / 0154 / 0156 | 6000.00 | 6000 (no expenses entered) | ✅ |
| Base imponible general | 0435 / 0500 / 0505 | 36000.00 | 30000+6000 = 36000 | ✅ |
| Base liquidable ahorro | 0510 | 0.00 | 0 | ✅ |
| Mínimo personal y familiar | 0521 | 5550.00 | €5,550 (2024, <65, single) | ✅ computed from profile |
| Cuota íntegra estatal | 0545 | 3983.50 | engine/AEAT oracle | ⚠ unverified vs AEAT |
| Cuota íntegra autonómica | 0546 | 3469.60 | engine/AEAT oracle | ⚠ unverified vs AEAT |
| Cuota líquida total | 0595 | 7453.10 | 3983.50+3469.60 | ✅ internally consistent |
| Retención trabajo (my €4,500) | 0596 | 4500.00 | 4500 | ✅ (fed by 111 binding) |
| Pagos fraccionados | 0604 | 0.00 | 0 | ✅ (only after --relation) |
| Total pagos a cuenta | 0609 | 4500.00 | 4500 | ✅ (only after --relation) |
| Cuota diferencial | 0610 | 2953.10 | 7453.10 − 4500 | ✅ |
| **Resultado de la declaración** | **0670** | **2953.10** | 2953.10 a ingresar | ✅ internally consistent |

**Note on 0022:** the engine did not auto-apply the €2,000 automatic "otros gastos"
(art. 19.2.f) nor any Seguridad Social — because both are manual casillas I left empty.
Faithful to my literal input, but a real employee who forgets casilla 0019/SS will
over-declare. The €4,500 retención is internally reflected; the cuota figures are the
engine's own and were **not** cross-checked against an AEAT oracle (would need the live
PADRE/Renta Web comparison).

**Bottom line the tool computed:** €2,953.10 to pay (plus a 12% recargo for late filing).
But this number lives only in a **draft** revision that cannot be verified or exported.

---

## 5. Final artefact

**No `.boe` was produced.** `modelo export --output tmp/personas/renta-100-fullyear/m100-2024.boe`
was **refused**: *"current revision is still draft; verify it before exporting or select a
verified revision explicitly."* Verify cannot be granted (Section 3, item 7), so there is
no verified revision to export.

- byte_size: n/a
- file_sha256: n/a

---

## 6. Findings

### F1 — CRITICAL: A salaried + rental taxpayer cannot reach a verified/exportable M100
Verify imposes ~33 blocking `cross_period_dependency_unclean` findings demanding AEAT
justificante evidence for modelos **111, 115, 123, 130, 131, 193** — withholding and
instalment forms a pure employee/landlord has **no obligation to file**. There is no
local path to satisfy them (only `live filed pull-sources` against AEAT, or a justificante
PDF). `activity-start-date` scopes out only the prior *year*, not same-year relations.
Result: `granted_verificado_completo = false`, export refused. **A real Elena fails here,
unaided.**
Proof: `work verify --modelo 100 --year 2024 --period 0A` → `completeness_status blocked`,
`finding_count 35`, 33× `cross_period_dependency_unclean ... blockers=missing_observation,
missing_current_filing_record`; `modelo export` → *"current revision is still draft"*.

### F2 — CRITICAL: Silent drop of the resultado chain when a relation is unsupplied
With income entered but the pagos-fraccionados *relations* not passed, casillas **0604,
0609, 0610 and 0670 (resultado de la declaración) were absent from the revision** while
their neighbours emitted 0 — the cuota líquida (0595) computed but the final "to pay"
figure silently vanished, signalled only by a non-blocking `AVISO`. The required relation
ids (`renta-2024-rel-130/131-pagos-fraccionados`) are **not listed by `bindings list
--missing`**, so the requirement is undiscoverable. Violates `no-silent-under-declaration`
and `aeat-calculation-grounding` (every casilla must be emitted).
Proof: revision after calculate-without-relations → `0670 => ABSENT`; after
`--relation renta-2024-rel-130/131-pagos-fraccionados=0` → `0670 = 2953.10`.

### F3 — HIGH: Income does not auto-map from the ledger; M100 is 1,882/2,059 manual
24 imported real income rows contributed nothing to the form; salary (0003) and rent
(0102) were typed by hand. `ledger preflight` additionally reports all 24 personal-income
rows as `missing_business_classification` errors — the ledger pipeline is IVA/business-only
and irrelevant to IRPF. A taxpayer expecting "import statement → form fills in" gets an
empty form and 24 error issues.
Proof: `modelo casillas 100 ... --input-kind manual` → 1882; bare calculate left every
income casilla 0; `ledger preflight --year 2024 --period 0A` → 24× `missing_business_classification`.

### F4 — MEDIUM: Date-typed bindings are unsatisfiable via `--binding` and mis-typed
`renta-2024-profile-taxpayer-birth-date` is advertised as `decimal` but rejects `0`
("Falta el valor de la vinculacion de fecha") *and* ISO dates ("is not a decimal"). It is
only satisfiable by setting the profile field. The error never names which binding is the
missing date.
Proof: `--binding renta-2024-profile-taxpayer-birth-date=1985-05-15` → "is not a decimal";
`=0` (with others present) → "Falta el valor de la vinculacion de fecha".

### F5 — MEDIUM: Inconsistent date format between profile and import surfaces
Profile `--taxpayer-birth-date` accepts only ISO `YYYY-MM-DD`; the Spanish `15/05/1985`
(the exact dialect the import CSV mandates, `dd/mm/YYYY`) is rejected `invalid_date_value`.
Proof: create with `15/05/1985` → `issue_codes: invalid_date_value`,
`issue_paths: renta_taxpayer.birth_date`; with `1985-05-15` → success.

### F6 — LOW: Bindings reported one-at-a-time on calculate; relations not reported at all
`work calculate` surfaces missing bindings one error per run; you must pre-fetch with
`--missing`. The two required pagos-fraccionados relations are not in that list at all
(see F2). 17 bindings + 2 relations are needed for the simplest conceivable filer.

### F7 — LOW (works as designed): late-filing recargo applied automatically
2024 work created on 2026-06-18 → `recargo_band within_12_months`, `recargo_pct 12.00`,
Art. 27.2 LGT. Correct and clearly surfaced.

### F8 — INFO (works well): NIF control-letter validation and mínimo personal
The NIF check computed and named the correct control letter (B). The €5,550 mínimo
personal was derived automatically from the profile birth-date. Both are good.

---

## 7. Verdict

**Did I reach a compliant `.boe`? NO.** I reached a fully computed draft showing
**€2,953.10 to pay**, but verify is hard-blocked by ~33 cross-period evidence demands for
withholding/instalment modelos I never file, and export refuses any draft.

**Would a real Elena succeed unaided? No.** Three walls would stop an ordinary salaried
taxpayer cold: (1) her bank import fills in nothing and is flagged as 24 errors;
(2) 17 bindings + 2 hidden relations + ~1,880 manual casillas with no guidance;
(3) a verify gate that treats her employer's modelo-111 obligations as her own and offers
no "not applicable" path. The underlying IRPF engine is genuinely capable — base, mínimo,
cuota and resultado all compute coherently — but the **on-ramp (ledger→form) and the
off-ramp (cross-period verify gate) are not built for the single most common Spanish
taxpayer.** The most valuable fixes are F1 (scope cross-period evidence to the filer's
actual obligations) and F2 (never drop the resultado casillas silently).
