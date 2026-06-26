# Testimonial — Review and supply calculation inputs

- **Doc:** `docs/how-to/review-calculation-values.md`
- **Persona:** First-time filer whose calculation reported missing values/bindings, trying to enter missing box values and handle IVA credits carried forward.
- **Date:** 2026-06-18
- **BASE:** `/tmp/persona-review-calc`

---

## Walkthrough

### 1. `aeat app modelo describe 130 --period 1T`
- **Expect:** A description of the modelo and its revisions.
- **Actual:** OK. Printed título, periodicidad, revision ids, 20 casillas, 6 vinculaciones, 11 fórmulas.
- **Verdict:** OK.

### 2. `aeat app modelo casillas 130 --period 1T`
- **Expect:** Table of casilla id, form number, input kind, required flag, label.
- **Actual:** OK. Full 20-row table; columns exactly as the page promises.
- **Verdict:** OK.

### 3. `aeat app modelo casillas 130 --period 1T --input-kind manual --required`
- **Expect:** Only required manual casillas.
- **Actual:** OK. One row: `02 / 02 / manual / true / Gastos`.
- **Verdict:** OK.

### 4. `aeat app modelo formulas 130 --period 1T --explain`
- **Expect:** Formulas with legal/source references.
- **Actual:** OK. 11 formulas with target, inputs, legal_refs, source_refs.
- **Verdict:** OK.

### 5. `aeat app modelo work revisions --modelo 130 --year 2026 --period 1T`  *(first attempt, fresh env)*
- **Expect:** "List calculation revisions for one filing."
- **Actual:** Refused: `Refused. No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.`
- **Verdict:** DOC-ISSUE, MAJOR — page never tells you to create a profile.

> Prerequisite built off-page to continue: `aeat config profile create tester --quiet --tax-id 12345678Z` (the plain `create ... --tax-id` form first refused, demanding `--quiet` or an interactive terminal).

### 6. `aeat app modelo work revisions --modelo 130 --year 2026 --period 1T`  *(after profile)*
- **Actual:** `Invalid value: Ninguna unidad de trabajo activa coincide con este modelo, ano y periodo. Ejecute primero aeat app modelo work create.`
- **Verdict:** DOC-ISSUE, MAJOR — page assumes a draft exists; never mentions `work create`.

> Prerequisite built off-page: `aeat app modelo work create --modelo 130 --year 2026 --period 1T` → `state borrador`.

### 7. `aeat app modelo work revisions ...` *(after work create)*
- **Actual:** OK — `revision_count 0` (empty, since nothing calculated yet).
- **Verdict:** OK.

### 8. `aeat app modelo work revision --modelo 130 --year 2026 --period 1T`
- **Expect:** "Show the selected or current revision's persisted casilla values."
- **Actual:** `Invalid value: 'work unit has no selectable current_calculation_revision_id'`.
- **Verdict:** DOC-ISSUE, MAJOR — page lists this BEFORE the calculate command, but it can't work until a calculation exists.

### 9. `aeat app modelo work verify --modelo 130 --year 2026 --period 1T`
- **Actual (pre-calculation):** Same `no selectable current_calculation_revision_id` refusal.
- **Actual (after calculation #11):** OK and very informative — `completeness_status incomplete`, `missing_required_casilla_count 1` (casilla 02), 3 blocking findings each with legal_refs and a concrete next-command suggestion.
- **Verdict:** OK once a calculation exists; DOC-ISSUE on ordering.

### 10. `aeat app modelo work calculate --modelo 130 --year 2026 --period 1T --casilla 02=4000.00`
- **Expect:** Per "Supply manual casilla values", this is the first calculate example.
- **Actual:** Refused: `Invalid value: La vinculación irpf.previous_year_economic_activity_net_income no tiene valor asignado. Aporta el valor con --binding KEY=VALUE en este comando, o ejecuta 'aeat app modelo bindings list ... --missing' ...`
- **Verdict:** DOC-ISSUE, MAJOR — the page's first worked calculate command fails on its own; the binding requirement is introduced only in the *next* section. Error is instructive, which softens it.

### 11. `aeat app modelo bindings list --modelo 130 --year 2026 --period 1T`
- **Expect:** Fields with `source` and plain-language `readiness`.
- **Actual:** OK. 6 bindings; `source` and `readiness` columns present. But all sources are `previous_filing` or `ledger_renta_income_aggregation` — **zero `manual` sources**. `readiness` shows "prior filed revision"/"ledger source" (a restatement of source), not a resolved/unresolved status.
- **Verdict:** MINOR (see findings 5, 6).

### 12. `aeat app modelo bindings list ... --missing`
- **Actual:** OK, but returned the same 6 rows with identical readiness text — no visible "still missing" distinction.
- **Verdict:** MINOR.

### 13. `aeat app modelo bindings preview ... --binding irpf.previous_year_economic_activity_net_income=0`
- **Expect:** Preview without saving.
- **Actual:** OK. `override` column shows `0` against the targeted binding; others `-`.
- **Verdict:** OK.

### 14. `aeat app modelo work calculate ... --binding irpf.previous_year_economic_activity_net_income=0`
- **Actual:** OK. Saved a borrador calculation revision; printed full casilla table, recargo band, overdue notice, and a resume hint.
- **Verdict:** OK.

### 15. `aeat app modelo iva-wallet balance --as-of-year 2026`
- **Actual:** OK. `total_balance 0`, `lot_count 0`.
- **Verdict:** OK.

### 16. `aeat app modelo iva-wallet seed --filing-year 2024 --period 4T --amount 0 --confirm`
- **Actual:** OK. `status seeded`.
- **Verdict:** OK.

### 17. `aeat app modelo iva-wallet correct --filing-year 2024 --period 4T --amount 1200.50 --reason "typo in opening balance" --confirm`
- **Actual:** OK. `previous_amount 0`, `amount 1200.50`, reason recorded.
- **Verdict:** OK.

### 18. `aeat app modelo work create --modelo 184 ...` + `work calculate <id> --row 'miembro ...' --row 'miembro ...'`
- **Expect:** Saved rows appear as `detail_row` lines.
- **Actual:** OK. Two `detail_row` lines (NIFs hashed), porcentaje 60/40 summing to 100 accepted.
- **Verdict:** OK.

### 19. `aeat app modelo work compare-taxation --modelo 100 --year 2026 --period 0A`
- **Actual:** `Invalid value: Ninguna unidad de trabajo activa ... Ejecute primero aeat app modelo work create.`
- **Verdict:** DOC-ISSUE, MINOR — requires a Modelo 100 work unit; page doesn't state the prerequisite.

### 20. `aeat app modelo work preview-maritime-exemption`
- **Actual:** OK. Empty observation set (no maritime data), no draft required.
- **Verdict:** OK.

### 21. `aeat app modelo work amend --from-filing-record nonexistent-id --kind complementaria --reason "corrected value" --set 02=4000.00`
- **Actual:** Graceful refusal: `Invalid value: No existe ninguna declaración registrada con id=nonexistent-id.`
- **Verdict:** OK — clear refusal (could not test the happy path without an imported justificante, as the page warns).

---

## Findings

1. **[MAJOR] [DOC]** Page assumes an **active profile** but never instructs creating one. The first command in "Review a saved calculation" refused with `No hay un perfil activo. Ejecuta 'aeat config profile create NAME --tax-id <NIF/CIF/DNI/NIE>' primero.` *Fix:* add a one-line prerequisite/link to profile creation at the top.

2. **[MAJOR] [DOC]** Page assumes a **work unit/draft already exists**. `work revisions`, `work revision`, `work verify` all refuse with `Ejecute primero aeat app modelo work create`. The page is built entirely around reviewing a draft yet never names `aeat app modelo work create`. *Fix:* add a prerequisite step or link to the workflow that creates the draft.

3. **[MAJOR] [DOC]** **Ordering inversion.** "Review a saved calculation" (`work revision`, `work verify`) is documented *before* the calculate command, but on a freshly-created work unit both fail with `work unit has no selectable current_calculation_revision_id`. You must calculate first. *Fix:* move the review subsection after the calculate subsection, or note "run a calculation first."

4. **[MAJOR] [DOC]** The first worked calculate example, `--casilla 02=4000.00`, **fails by itself** because binding `irpf.previous_year_economic_activity_net_income` is unset — yet bindings are introduced only in the next section. A top-to-bottom reader hits a wall on the page's headline command. *Fix:* present the casilla example together with the required binding, or forward-reference the bindings section.

5. **[MINOR] [DOC]** Source-taxonomy claim is misleading: "Only the manual source needs a value you enter by hand." For Modelo 130 there are **zero `manual`-source bindings**, and the page's own worked example types a value into a `previous_filing`-source binding (`--binding irpf.previous_year_economic_activity_net_income=0`). The "record it as zero" prose reconciles it, but the flat claim contradicts the example. *Fix:* soften to "manual *and* unresolved prior-period bindings may need a hand-entered value."

6. **[MINOR] [BOTH]** `readiness` column doesn't match the doc. Page says readiness "says whether it is resolved yet," but the column prints "prior filed revision"/"ledger source" — a restatement of `source`, not a resolved/unresolved status. Even `--missing` returns all rows with identical readiness text and no visible "missing" flag. *Fix:* either document readiness as a source-description, or have the app emit a true resolved/unresolved value (and have `--missing` actually filter).

7. **[MINOR] [DOC]** No **master-key passphrase** warning. The harness pre-set `AEAT_SECRET_PASSPHRASE`; a naive user in a non-interactive shell would be blocked with no hint from this page. *Fix:* add a note that a passphrase is required for profile-scoped commands.

8. **[MINOR] [DOC]** `compare-taxation` (and the `--relation` example on Modelo 100) require a **Modelo 100 work unit** that the page never tells you to create — same draft-assumption gap as finding 2. *Fix:* note the prerequisite.

9. **[NIT] [DOC]** Inconsistent addressing within one page: most commands use `--modelo/--year/--period`, but the multi-record section switches to a positional `<work-unit-id>` placeholder without saying where to obtain that id (it is in `work create` output). *Fix:* show how to get the id, or use consistent flags.

---

## Testimonial

I came to this page because my calculation said values were missing, and the reference material itself is genuinely good — `casillas`, `formulas`, `bindings list/preview`, `verify`, and the IVA-wallet trio all did exactly what they promised and the error messages were unusually helpful (each one named the next command to run). But the page quietly assumes I already have a profile *and* a draft, and it never tells me how to get either, so the very first command I tried bounced me with "no active profile," and the next bounced me with "run work create first." Worse, it lists "review your saved calculation" before the calculate step that produces something to review, and its headline `--casilla 02=4000.00` example fails on its own until I scroll down to learn about bindings. Once I created the profile and draft off-page and supplied the binding, everything worked and felt solid — the app delivered, but the page sent me through the doors in the wrong order.

## Scorecard

- **Doc clarity:** 2/5 (strong reference content undermined by missing prerequisites and reversed ordering)
- **App capability:** 5/5 (every command worked once prerequisites existed; refusals were graceful and instructive)
- **Findings:** BLOCKER 0 · MAJOR 4 · MINOR 4 · NIT 1
