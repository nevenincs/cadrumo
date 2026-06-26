# Testimonial — `docs/tutorials/index.md`

- **Doc path:** `docs/tutorials/index.md` (title: "Build your first Modelo 130 filing")
- **Persona:** A new user landing on the tutorials index, looking for a starting path, then following the embedded worked walkthrough end-to-end.
- **Date:** 2026-06-18
- **Base dir:** `/tmp/persona-tut-fg`

## Orientation note

My assigned page is the tutorials *index*, but the file is not an index — it is a
single full worked tutorial ("Build your first Modelo 130 filing"). I treated it
as both a navigation entry point (link check) and a runnable walkthrough
(executed Steps 1–8 in order).

## Link check (navigation entry point)

All eight outbound links resolve to real files:

| Link | Resolves |
|------|----------|
| `../how-to/quickstart.md` | OK |
| `../how-to/profile-setup.md` | OK |
| `../how-to/review-calculation-values.md` | OK |
| `../how-to/file-at-aeat.md` | OK |
| `../how-to/index.md` | OK |
| `../how-to/filing-spine.md` | OK |
| `../explanation/from-records-to-figures.md` | OK |
| `../how-to/troubleshooting.md` | OK |

No broken links. As a navigation surface the page is fine.

## Walkthrough

### Step 1 — Create taxpayer profile
- **Command:** `aeat config profile create tutorial --quiet --accept-defaults --tax-id 12345678Z --name "Ana" --surnames "Garcia Lopez"`
- **Expected (doc):** output with `profile tutorial` / `status created` / `active_profile tutorial` / `next aeat app modelo work create`.
- **Actual:**
  ```
  profile	tutorial
  estado	creado
  active_profile	tutorial
  next	aeat app modelo work create
  ```
- **Verdict:** OK (with NIT) — works, but the doc shows `status created` while the CLI emits the Spanish `estado creado`. English reader sees a label/value mismatch.

### Step 2 — Import transactions
- **Command:** `aeat app ledger import transactions.csv --provider csv`
- **Expected (doc):** CSV created in the working dir, then imported; `ledger list` shows two rows.
- **Actual:** Running `aeat` from a `cd`-ed working directory failed (`error: Failed to spawn: aeat ... program not found`) because in this uv-managed checkout the CLI must launch from the repo root; I re-ran with an absolute CSV path from the repo root:
  ```
  Filas	2
  Entradas importadas	2
  Omitidos	0
  ```
- **Verdict:** OK in substance. The `cd into your working directory` instruction is a test-harness friction here, not necessarily a doc bug for an installed `aeat` on PATH — noted as a MINOR.

### Step 2b — `ledger list`
- **Command:** `aeat app ledger list`
- **Expected (doc):**
  ```
  ACCOUNTING LEDGER TRANSACTIONS
  5caeee4b	5caeee4b...	2026-04-10	1234.56	Cobro factura F-2026-020	pending
  4b101fb8	4b101fb8...	2026-04-11	-49.99	Pago software trimestral	pending
  ```
- **Actual:**
  ```
  MOVIMIENTOS DEL LIBRO CONTABLE
  5caeee4b	5caeee4b...	2026-04-10	1234.56	Cobro factura F-2026-020	pending
  cc552072	cc552072...	2026-04-11	49.99	Pago software trimestral	pending
  ```
- **Verdict:** DOC-ISSUE (MINOR). Three divergences from the printed expected output: (a) header is Spanish `MOVIMIENTOS DEL LIBRO CONTABLE`; (b) the second ID is `cc552072`, not the doc's `4b101fb8` (the doc *does* warn IDs vary, so acceptable); (c) the amount is `49.99`, not `-49.99` — the ledger stores absolute magnitudes, so the doc's printed `-49.99` is stale and will never appear.

### Step 3 — Classify transactions
- **Command:** `aeat app ledger classify 5caeee4b --classification BUSINESS` and `... cc552072 ...`
- **Expected (doc):** both flip to `reviewed`.
- **Actual:** both returned `Estado de revisión	reviewed`.
- **Verdict:** OK.

### Step 4 — Create draft
- **Command:** `aeat app modelo work create --modelo 130 --year 2026 --period 1T`
- **Expected (doc):** 5 lines (modelo / filing_year / period / revision_id / state).
- **Actual:** all 5 documented fields present, but the real output is ~25 lines including `work_unit_id`, `short_work_unit_id`, a `recargo_*` block, and `AVISO: plazo voluntario vencido (Art. 27 LGT)`.
- **Verdict:** OK (NIT) — documented subset is correct; real output is far noisier and includes an overdue-deadline warning the tutorial doesn't prepare the reader for.

### Step 5 — Calculate
- **Command (as documented):** `aeat app modelo work calculate --modelo 130 --year 2026 --period 1T`
- **Expected (doc):** "saves the draft for the same filing target." The doc only says: *if* it reports a missing value, go to the review how-to.
- **Actual — it failed:**
  ```
  Invalid value: La vinculación
  irpf.previous_year_economic_activity_net_income no tiene valor asignado.
  Aporta el valor con --binding KEY=VALUE en este comando, o ejecuta `aeat
  app modelo bindings list --modelo 130 --year 2026 --period 1T --missing`
  para ver todos los bindings que el cálculo todavía necesita.
  ```
  `bindings list --missing` shows **6** missing bindings (3 `previous_filing`, 3 `ledger_renta_income_aggregation`). I supplied the one the error named (`--binding irpf.previous_year_economic_activity_net_income=0`) and calculate then completed — but with degenerate figures and two warnings:
  - `AVISO: filing date 2026-04-10 is outside the cumulative income window` → the 1234.56 income is **not aggregated**; casilla 03 (Rendimiento neto) = `0.00`.
  - `AVISO: deducible expense (gasto) candidate dropped: OUTGOING business transaction (category 'unclassified', base 49.99) is not aggregated into Modelo 130 casilla 02 (Gastos) ... declare the quarter's gastos manually` — despite Step 3 telling me to classify it BUSINESS.

  Final draft: casilla 13 = 100.00, casilla 14/17/19 = `-100.00`, everything else 0 — i.e. a near-empty negative draft, not the "tax figures" the step title promises.
- **Verdict:** BOTH (MAJOR). The exact documented command fails on the documented sample data; the recovery (`--binding`) is not shown in this step (only a pointer to a separate how-to), and even after recovery the sample data does not produce a meaningful filing.

### Step 6 — Verify
- **Command:** `aeat app modelo work verify --modelo 130 --year 2026 --period 1T`
- **Expected (doc):**
  ```
  completeness_status     complete
  granted_verificado_completo     true
  finding_count   0
  ```
- **Actual:**
  ```
  completeness_status	incomplete
  granted_verificado_completo	false
  finding_count	3
  missing_casilla	02
  finding	missing_required_casilla	blocking	02 ...
  finding	cross_period_dependency_unclean	blocking ... modelo=100 year=2025 period=0A ...
  finding	cross_period_dependency_unclean	blocking ... no activity-start date for modelo=130 ... record the activity-start date ...
  ```
- **Verdict:** BOTH (BLOCKER). The verify step's promised success state is unreachable with the shipped sample data. Three blocking findings: missing casilla 02 (gastos), a missing prior Modelo 100 2025-0A dependency, and a missing profile activity-start date. None of these is mentioned or pre-supplied anywhere in the tutorial.

### Step 7 — Export
- **Command:** `aeat app modelo export --modelo 130 --year 2026 --period 1T --output borrador.boe`
- **Expected (doc):** export the fichero-BOE and print a path + checksum. The intro promises "You'll export a local fichero-BOE file ... at the end."
- **Actual:**
  ```
  Invalid value: current revision is still draft; verify it before exporting
  or select a verified revision explicitly
  ```
- **Verdict:** APP refusal is correct and graceful, but the tutorial's headline promise is **not delivered** — the export never happens with the documented inputs. (BLOCKER, follows from Step 6.)

### Step 8 — Record local filing marker
- **Command:** `aeat app modelo work file --modelo 130 --year 2026 --period 1T`
- **Expected (doc):** saves a local "filed" marker.
- **Actual:**
  ```
  Invalid value: current revision '...' is in state 'borrador';
  filing requires a verified-complete revision
  ```
- **Verdict:** Graceful refusal, but again unreachable end-state.

## Findings

1. **[BLOCKER][BOTH] The documented happy path cannot complete with the shipped sample data.**
   Repro: run Steps 1–8 verbatim with the doc's `transactions.csv`. Step 5 errors out (missing binding), and even after supplying it, Step 6 returns `granted_verificado_completo false`, `finding_count 3`, so Steps 7 (export) and 8 (file) both refuse. The tutorial's stated goal ("export a local fichero-BOE file at the end") is never achieved. Suggested fix: either (a) ship sample data + pre-steps (activity-start date, prior-period zero bindings, a gastos value) that genuinely reach `verified_complete`, or (b) re-frame the tutorial honestly so the expected outputs in Steps 5/6 show the missing-binding/blocking-finding path and walk the reader through resolving each one, rather than printing a clean `complete`/`true`/`0` that never occurs.

2. **[MAJOR][BOTH] Step 5 calculate fails on the literal documented command.**
   Repro: `aeat app modelo work calculate --modelo 130 --year 2026 --period 1T` → `Invalid value: La vinculación irpf.previous_year_economic_activity_net_income no tiene valor asignado.` The doc presents calculate as succeeding ("The command saves the draft") and only mentions failure as a conditional aside. Suggested fix: show the `--binding` recovery inline in Step 5 (the error even prints the exact `--binding KEY=VALUE` form and a `bindings list --missing` command), and set the expectation that a first-quarter filing needs prior-period and gastos inputs.

3. **[MAJOR][DOC] No passphrase prerequisite is stated.**
   `grep -i passphrase docs/tutorials/index.md` → no match. Every command depends on the master-key passphrase (here pre-set via `AEAT_SECRET_PASSPHRASE`). A naive user in a non-interactive shell is blocked with no warning; even interactively, the page never says a passphrase will be required. Suggested fix: add a one-line prerequisite ("`aeat` will prompt for your master-key passphrase; set `AEAT_SECRET_PASSPHRASE` for non-interactive use").

4. **[MINOR][DOC] Step 3 says classify as BUSINESS, but the expense is then dropped.**
   After classifying the -49.99 software payment BUSINESS, calculate warns: "deducible expense (gasto) candidate dropped ... no expense aggregation binding exists yet; declare the quarter's gastos manually." The tutorial implies classification feeds the filing; for the expense it does not (and casilla 02 is then a blocking missing-required finding). Suggested fix: explain that gastos must be supplied via `--binding`/`--casilla 02=VALUE`, or pick sample data where this doesn't bite.

5. **[MINOR][DOC] Income falls outside the cumulative window → 0 rendimiento.**
   Calculate warns the 2026-04-10 income is "outside the cumulative income window," so casilla 03 = 0.00. The sample data dates are inconsistent with the 1T cumulative aggregation the tutorial relies on. Suggested fix: use sample dates that land inside the 1T cumulative window so the income actually aggregates.

6. **[MINOR][DOC] Printed expected outputs are stale / English-labelled.**
   `ledger list` header is `MOVIMIENTOS DEL LIBRO CONTABLE` (doc: `ACCOUNTING LEDGER TRANSACTIONS`); the expense shows `49.99` (doc: `-49.99`, ledger stores absolute magnitudes); Step 1 emits `estado creado` (doc: `status created`); Steps 4–6 emit far more fields (work_unit_id, recargo block, AVISO lines) than the trimmed examples. The doc's expected blocks don't match the Spanish, absolute-amount CLI. Suggested fix: regenerate expected outputs from the live CLI, or note that labels render in Spanish and the doc shows a subset.

7. **[NIT][DOC] The "tutorials index" is actually a single tutorial.**
   The file assigned as the tutorials *index* is a full Modelo-130 walkthrough with no list of other tutorials. As a directory landing page it offers no menu of starting paths. Suggested fix: if this is meant to be the index, add a short list/links to the available tutorials; otherwise rename the page so the title and role match.

## Testimonial

As a first-timer I got off to a confident start — the profile, import, and
classify steps all worked and the links to the how-to guides all resolved, so the
page felt trustworthy as an entry point. Then the wheels came off exactly where it
mattered: the calculate step errored on the documented command, and once I limped
past it the verify step came back `incomplete` / `false` / `3 findings` instead of
the clean pass the page promised, so the export and the "record your filing"
finish — the whole point of the tutorial — simply refused. The refusals were
polite and told me what was wrong, which I appreciated, but the page set me up to
expect a finished fichero-BOE and the shipped sample data can't get there. It also
never warned me a master-key passphrase would be needed. The app is clearly
capable and its guardrails are sound; the tutorial just over-promises and its
sample data doesn't survive contact with the real engine.

## Scorecard

- **Doc clarity:** 2 / 5 (well-structured and well-linked, but the worked example does not run to its promised end and several expected outputs are stale)
- **App capability:** 4 / 5 (every refusal was graceful and instructive; the engine correctly blocked an unverified export/file; lost a point only for the first-quarter UX requiring several non-obvious manual bindings)
- **Findings by severity:** BLOCKER 1 · MAJOR 2 · MINOR 3 · NIT 1 (7 total)
