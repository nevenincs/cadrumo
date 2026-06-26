# Testimonial — docs/how-to/classify-transactions.md

- **Doc path:** `docs/how-to/classify-transactions.md`
- **Persona:** First-time user with imported transactions who needs to classify
  them (business/personal/mixed), set tax fields, do bulk CSV classification, and
  allocate mixed-use shares.
- **Date:** 2026-06-18
- **Env:** `BASE=/tmp/persona-classify`, CLI via `uv run --no-sync aeat ...`

Note on prerequisites: the page opens "Use this guide after transactions are in
the active profile's ledger" and never documents creating a profile or adding a
row. I had a pre-existing `persona` profile in the harness storage; I synthesized
the transactions with `aeat app ledger add` (an undocumented-on-this-page command)
to exercise the documented verbs. See Finding 3.

## Walkthrough

### 1. `aeat app ledger list --filter classification=NOT_YET_PROCESSED`
- **Expected:** A list of unclassified rows with ids to copy.
- **Actual:** On an empty ledger: header only, `MOVIMIENTOS DEL LIBRO CONTABLE`,
  exit 0. After adding rows, tab-separated rows with a short id, full id, date,
  amount, description, status — **but no column headers**.
- **Verdict:** OK (app) / DOC-ISSUE for missing-data path. MINOR. (See Finding 4
  for the no-header point.)

### 2. `aeat app ledger view 5a6dc702`
- **Expected:** Full detail of one transaction.
- **Actual:** Clean field/value table (ID, Fecha, Importe, Sentido, Clasificación,
  etc.), accepts the short id. Bad id → Spanish error
  `El prefijo de id %'faketx-123' contiene caracteres no hexadecimales` (exit 2).
- **Verdict:** OK.

### 3. `aeat app ledger categories`
- **Expected:** Accepted category ids.
- **Actual:** Two-column table `category-id (pasa este valor exacto) / familia`
  listing `software_suscripcion`, `material_oficina`, `telefonia_movil`, etc.
  Works without a profile, exit 0.
- **Verdict:** OK.

### 4. `aeat app ledger classify 5a6dc702 --classification BUSINESS --category-id software_suscripcion`
- **Expected:** Row classified BUSINESS with a category.
- **Actual:** Returned the row summary, `Estado de revisión reviewed`, exit 0.
  Verified via `view`.
- **Verdict:** OK.

### 5. `aeat app ledger classify ... --taxable-base 100.00 --iva-rate 0.21 --iva-amount 21.00`
- **Expected:** Tax fields stored.
- **Actual:** `view` shows `Base imponible 100`, `Tipo de IVA 0.21`,
  `Importe de IVA 21`. Exit 0.
- **Verdict:** OK.

### 6. `aeat app ledger classify f2d702f0 --classification MIXED --business-pct 0.5 --category-id telefonia_movil`
- **Expected:** Mixed row with a 50% business share, calculation-ready per the
  page's "Most users need only `--business-pct`."
- **Actual:** Stored (`Porcentaje de negocio 0.5`), exit 0. **But preflight later
  rejected it** for missing `usage_ratio_id` — see Finding 1.
- **Verdict:** APP-ISSUE/DOC-ISSUE (BOTH), MAJOR (Finding 1).

### 7. `aeat app ledger allocate f2d702f0 --business-pct 0.6 --category-id telefonia_movil`
- **Expected:** Update the share on an already-classified row.
- **Actual:** `Porcentaje de negocio 0.6`, exit 0.
- **Verdict:** OK.

### 8. `aeat app ledger ratios eligible` / `ratios list`
- **Expected:** Which categories support a ratio; current ratios.
- **Actual:** `eligible` → 15 categories with their ratio kind
  (`usage_ratio_home_area`, `usage_ratio_personal`) and defaults. `list` → `count 0`.
- **Verdict:** OK.

### 9. `aeat app ledger ratios set telefonia_movil 0.5` / `ratios validate` / `ratios unset telefonia_movil`
- **Expected:** Save, validate, remove a category ratio.
- **Actual:** `set` → `telefonia_movil 0.5`; `validate` → `overrides 1`;
  `unset` → `telefonia_movil <unset>`. All exit 0.
- **Verdict:** OK.

### 10. Bulk CSV — `ledger list` (filtered) → `ledger export` → narrow CSV → `classify --from-csv`
- **Command(s):**
  `aeat app ledger export --output .../ledger-2026-q1.csv --year 2026 --period 1T`
  then `aeat app ledger classify --from-csv .../classifications.csv`
- **Expected:** Export a review snapshot, prepare a `transaction_id,classification,category_id`
  CSV, apply it.
- **Actual:** Export wrote 5 rows + SHA-256, exit 0. The CSV header columns match
  the export exactly (good). Apply: `clasificación masiva: 2 filas, 2 aplicadas,
  0 omitidas, 0 fallidas`, exit 0. Both rows became `reviewed`.
- **Verdict:** OK. This was the smoothest part of the page.

### 11. `aeat app ledger preflight --year 2026 --period 1T`
- **Expected:** "Names rows that still need category, taxable base, IVA amount, IVA
  rate, currency, or proportionality reference."
- **Actual:** `issues 8, ready false`, including
  `f2d702...  missing_proportionality_reference  mixed ledger transaction has no
  usage_ratio_id proportionality reference` — for the row I classified MIXED with
  `--business-pct` per the page. Exit 0.
- **Verdict:** Surfaces issues well, but exposes Finding 1.

### 12. Rules — `rule add` / `rule list` / `rule apply --dry-run` / `rule apply`
- **Expected:** Pattern-based auto-classification; dry-run first.
- **Actual:** `rule add` → rule_id + priority 100. `list` shows it. `apply --dry-run`
  → `simulacro: 0 transacción(es) se clasificarían` (the only "software" row was
  already BUSINESS). `apply` → `reglas: 1, escaneadas: 1, coincidencias: 0,
  omitidas: 4, sin_coincidencia: 1`. All exit 0.
- **Verdict:** OK.

### 13. `aeat app ledger status --year 2026 --period 1T`
- **Expected:** Readiness summary.
- **Actual:** Totals + per-issue `readiness_issue` rows (same 8 as preflight),
  `Preparado False`. Exit 0.
- **Verdict:** OK.

### 14. `aeat app ledger classify 1a5eb381 --classification PERSONAL` (correction)
- **Expected:** Replace prior classification.
- **Actual:** Row summary, `reviewed`, exit 0.
- **Verdict:** OK.

## Findings

### 1. [MAJOR] [BOTH] Mixed-use guidance leads to an unresolvable preflight block via `classify`
The "Classify mixed-use transactions" section lists three ways to record a share
(`--business-pct`, `--usage-ratio-id`, `--prorrata-reference`), says "Set the share
while you classify the row," and concludes "Most users need only `--business-pct`."
In practice:
- A MIXED row classified with only `--business-pct 0.5` **fails preflight**:
  `missing_proportionality_reference  mixed ledger transaction has no usage_ratio_id
  proportionality reference`. So `--business-pct` alone is NOT enough for the common
  case the page implies.
- `aeat app ledger classify` has **no** `--usage-ratio-id` and **no**
  `--prorrata-reference` option. Trying it:
  `aeat app ledger classify f2d702f0 --usage-ratio-id x` →
  `Error  No such option: --usage-ratio-id` (exit 2). Those two flags exist only on
  `allocate` and `add`, not `classify` — yet the page presents all three under a
  section headed by a `classify` example.
- The only way I cleared the block was
  `aeat app ledger allocate f2d702f0 --business-pct 0.5 --usage-ratio-id telefonia_movil
  --category-id telefonia_movil` (the `usage_ratio_id` value must be a **spending
  category id**, discovered only via an error message:
  `usage_ratio_id 'usage_ratio_personal' must be a concrete eligible spending category`).
  The page never says the `--usage-ratio-id` value is a category id, never says
  `allocate` (not `classify`) is required, and never says `allocate --business-pct`
  is mandatory alongside it.
- **Repro:** classify any OUTGOING row `--classification MIXED --business-pct 0.5
  --category-id telefonia_movil`, then `preflight`. Observe the proportionality issue
  that the page's own readiness wording promises but gives no documented fix for.
- **Suggested fix:** Split the three share-recording methods by the verb that
  actually supports them: `classify`/`add` accept `--business-pct`; `--usage-ratio-id`
  and `--prorrata-reference` are `allocate`/`add` only. State that a MIXED row needs a
  proportionality reference to pass preflight, that `--usage-ratio-id` takes a
  *category id*, and show the `allocate --business-pct N --usage-ratio-id <category-id>`
  command that satisfies it. Soften "Most users need only `--business-pct`" — it's
  true for the value but not for preflight readiness.

### 2. [MAJOR] [DOC] No mention of the required master-key passphrase
The page issues many commands that touch encrypted secure storage (`view`, `classify`,
`allocate`, `ratios`, `export`, `preflight`, `status`, `rule`) but never warns that a
master-key passphrase is required. In a non-interactive shell with no passphrase:
`Failed. AEAT_SECRET_PASSPHRASE is not set and stdin is not interactive; re-run the
command from an interactive terminal (the CLI prompts for the passphrase) or provide
AEAT_SECRET_PASSPHRASE through the Settings environment.` A first-timer scripting these
commands is blocked with no warning from the page.
- **Suggested fix:** Add a one-line prerequisite near the top: these commands unlock
  the profile's encrypted store and will prompt for (or require) the master-key
  passphrase.

### 3. [MINOR] [DOC] Page assumes a profile and ledger rows exist with no on-ramp
"Use this guide after transactions are in the active profile's ledger" presumes both an
active profile and imported rows. There's no pointer to profile creation, and the only
inbound link (`import-bank-statements.md`, in Next steps) is at the very bottom. A true
first-time reader landing here has neither a profile nor a transaction and no documented
command on this page to make one.
- **Suggested fix:** Add an explicit "Before you start" line linking profile setup and
  the import guide up front, not only in Next steps.

### 4. [MINOR] [APP] `ledger list` prints no column headers
`MOVIMIENTOS DEL LIBRO CONTABLE` is followed by tab-separated rows with no header line,
so a naive reader can't tell that column 1 is the short id to copy (vs the full id in
column 2). `view`, `categories`, and `export` all label their columns; `list` doesn't.
- **Suggested fix:** Emit a header row (short id, full id, date, amount, description,
  review status), or have the page note that the first column is the id to use.

### 5. [NIT] [DOC] Spanish help/errors against an English page
The page tells readers to run `aeat app ledger classify --help` "to see the accepted
values," but the help renders fully in Spanish (`Porcentaje de uso profesional...`), as
do errors (`No such option`, mixed-language). An English-only reader gets friction
exactly where the page sends them for the authoritative option list.
- **Suggested fix:** Note that CLI help/errors are localized to Spanish, or inline the
  key accepted values (IVA category, IRPF category) in the page so the reader needn't
  cross the language boundary.

## Testimonial

The straightforward path felt solid: single-row `classify`, tax fields, the bulk
`classify --from-csv` workflow, rules, and preflight/status all did exactly what the
page promised, with clear output and honest readiness reporting. Where I tripped hard
was mixed-use: I did what the page told me ("most users need only `--business-pct`"),
then preflight blocked the row for a missing `usage_ratio_id`, and the verb the page
implied — `classify` — flat-out rejected `--usage-ratio-id` ("No such option"). I only
escaped by guessing my way through `allocate` and decoding an error message to learn the
ratio id is actually a category id. I'd also have been dead in the water on a real
machine because the page never warns about the passphrase. The app is capable; the page
oversells `--business-pct` and hides which verb owns which share flag.

## Scorecard

- **Doc clarity:** 3/5
- **App capability:** 4/5
- **Findings:** BLOCKER 0 · MAJOR 2 · MINOR 2 · NIT 1
