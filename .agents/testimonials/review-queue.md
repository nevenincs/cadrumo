# Testimonial — `docs/how-to/review-queue.md`

- **Doc path:** `docs/how-to/review-queue.md`
- **Persona:** A first-time user working through the pending review queue for
  transactions that still need attention before a filing.
- **Date:** 2026-06-18
- **Environment:** `uv run --no-sync aeat ...`, non-interactive shell,
  `AEAT_SECRET_PASSPHRASE` pre-set by `.agents/persona_env.sh`, BASE
  `/tmp/persona-rq-fg`.

## Setup performed before the page (not on the page)

To get a non-empty queue I had to do work the page never mentions: create a
profile and import transactions. The page assumes a profile already exists and
that the ledger already has unclassified rows. A truly naive reader landing
here first would see an empty queue and be confused.

- `aeat config profile create persona-rq --quiet --accept-defaults`
  → refused gracefully: `Refused. A esta ejecución con --quiet le faltan datos
  obligatorios. Añade estos flags ...: --tax-id.` Good refusal.
- `aeat config profile create persona-rq --quiet --accept-defaults --tax-id 00000001R`
  → `estado  creado`, profile active. OK.
- Wrote a 3-row CSV (`date,description,amount`) and ran
  `aeat app ledger import "$BASE/stmt.csv" --provider csv`
  → `Entradas importadas  3`. OK. Queue now has 3 `ledger_transaction` items.

## Walkthrough

### 1. `aeat app review queue`
- **Expected (per doc):** A table whose columns are "the item id, its kind, the
  affected record, the period, a severity, and a final column with the command
  to run next."
- **Actual:** Table rendered with EIGHT columns:
  `ID  Tipo  Tipo origen  Objeto  Bucket  Periodo  Severidad  Siguiente`.
  Three rows, e.g.
  `fb1b5401...  ledger_transaction  ledger_transaction  fb1b5401...  <profile-id>  2026-01  normal  aeat app ledger review fb1b5401...`
  The `Bucket` column prints the literal placeholder string `<profile-id>`
  rather than a real bucket id.
- **Verdict:** DOC-ISSUE + APP-ISSUE, MINOR. Doc lists 6 columns; the app shows
  8 (extra `Tipo origen` and `Bucket`). The `Bucket` cell showing the literal
  `<profile-id>` looks like an unfilled template token, not real data.

### 2a. `aeat app review queue --kind ledger_transaction`
- **Expected:** Only ledger-transaction items.
- **Actual:** Same 3 rows. OK.
- **Verdict:** OK.

### 2b. `aeat app review queue --kind modelo_finding --modelo 303`
- **Expected:** Only modelo-303 findings (none here).
- **Actual:** `No hay elementos pendientes de revisión.` OK, clean empty case.
- **Verdict:** OK.

### 2c. `aeat app review queue --state all`
- **Expected:** A wider list than the default `pending`.
- **Actual:** Same 3 rows. OK (nothing non-pending exists to widen to).
- **Verdict:** OK.

### Unknown-kind claim: `aeat app review queue --kind nonsense`
- **Expected (per doc):** "An unknown kind is refused **with the accepted set
  named**."
- **Actual:**
  ```
  ┌─ Error ──────────────────────────────────────────────┐
  │ Invalid value: Tipo de elemento de revisión desconocido. │
  └──────────────────────────────────────────────────────┘
  ```
  The accepted set is NOT named. The error is a bare "value invalid" with no
  list of valid tokens.
- **Verdict:** BOTH, MAJOR. The doc promises the accepted set is named; the app
  does not name it. This also violates the project's own CLI-boundary rule that
  a closed-enum refusal must list the accepted values, never a bare "value
  invalid."

### 3. `aeat app review view <item-id>`
- **Expected:** "Show one item in full, including the suggested next command."
- **Actual:**
  ```
  ID         fb1b5401...
  Tipo       ledger_transaction
  Tipo origen ledger_transaction
  Objeto     fb1b5401...
  Bucket     <profile-id>
  Severidad  normal
  Siguiente  aeat app ledger review fb1b5401...
  ```
  It shows the next command (`Siguiente`). But "in full" is generous: there is
  no Periodo row (present in the queue), and no transaction detail (date /
  amount / description) — just ids and the same fields the queue already shows.
- **Verdict:** DOC-ISSUE, MINOR. "in full" oversells it; `view` shows roughly
  the same data as the queue row, minus the period.

### 4a. `aeat app review queue --kind modelo_finding --explain`
- **Expected:** Legal references appended to the text table.
- **Actual:** Header gains a `Referencias legales` column, then
  `No hay elementos pendientes de revisión.` (no findings to show refs for). The
  `--explain` flag is accepted and adds the column. OK as far as testable here.
- **Verdict:** OK (could not exercise with a real finding in this environment).

### 4b. `aeat app review view <id> --explain`
- **Expected:** Legal references added for this item.
- **Actual:** Identical output to plain `view` — no legal-refs row. Correct per
  the page's own note ("Transaction and invoice items carry no legal
  references"), so `--explain` is a harmless no-op on a transaction item.
- **Verdict:** OK.

### JSON claim — NO documented way to get JSON
- The page asserts twice: "The JSON output always carries the `legal_refs`" and
  "The JSON output always carries the `legal_refs`; `--explain` adds them to the
  text table." But the page never tells the reader how to request JSON, and the
  obvious attempts all fail on these commands:
  - `aeat app review view <id> --json` → `No such option: --json`
  - `aeat app review queue --format json` / `--format=json` → `No such option: --format`
  - `aeat --json app review view <id>` → `No such option: --json ('(Possible options: --version)',)`
  - `aeat --output json ...` → `No such option: --output`
  - `AEAT_OUTPUT_FORMAT=json ...` → ignored, text rendered.
  The `--help` for both `review queue` and `review view` lists only `--explain`
  (and for queue, the filters) — no JSON/format option at all.
- **Verdict:** BOTH, MAJOR. The page makes a JSON-contract promise the reader
  cannot act on. Either the commands should expose a `--json`/`--format json`
  option (other parts of the CLI use `--json`), or the page must stop claiming a
  JSON output that this surface does not provide.

### Follow the suggested next command: `aeat app ledger review <id>`
- **Expected:** The row's "Siguiente" command resolves the item.
- **Actual:** Works and shows the transaction detail:
  ```
  ID         fb1b5401...
  Fecha      2026-01-15
  Importe    1210
  Descripción Cliente factura 001
  ```
  Good — the to-do-list promise (each row names the command that resolves it)
  holds at the entry point. (Note: this is the very transaction detail that
  `review view` itself withholds.)
- **Verdict:** OK.

### Link integrity
- All cross-links resolve: `classify-transactions.md`, `ledger-evidence.md`,
  `verification-reports.md`, `import-bank-statements.md`,
  `correct-ledger-entries.md`, and `../cli/index.rst` all exist.
- **Verdict:** OK.

## Findings

1. **[MAJOR] [BOTH] JSON output is promised but unreachable from this page.**
   Repro: `aeat app review view <id> --json` → `No such option: --json`;
   `--format json` → `No such option: --format`; `aeat --json app review ...` →
   `No such option`. The page states "The JSON output always carries the
   `legal_refs`" twice but documents no flag to enable JSON, and every obvious
   attempt is refused on this command surface.
   Fix: either add a `--json`/`--format json` option to `review queue`/`review
   view` and document it on this page, or rewrite the two JSON sentences to name
   the actual mechanism (or drop the JSON claim if the surface is text-only).

2. **[MAJOR] [BOTH] Unknown `--kind` does not name the accepted set.**
   Repro: `aeat app review queue --kind nonsense` →
   `Invalid value: Tipo de elemento de revisión desconocido.` (no list).
   The page promises "an unknown kind is refused with the accepted set named,"
   and the project's CLI rule requires closed-enum refusals to list accepted
   values. Fix: make the error enumerate
   `ledger_transaction, purchase_invoice_evidence, payable_invoice,
   collectible_invoice, modelo_finding`, or render `--kind` as a Click
   `Choice([...])` so the set surfaces automatically.

3. **[MINOR] [BOTH] Queue column set in the doc does not match the app.**
   Doc lists 6 columns (id, kind, record, period, severity, next); the app
   renders 8 (`ID  Tipo  Tipo origen  Objeto  Bucket  Periodo  Severidad
   Siguiente`). Fix: align the doc's column description with the real table, and
   investigate the `Bucket` column printing the literal `<profile-id>`
   placeholder (looks like an unfilled template token, not real data).

4. **[MINOR] [DOC] "Inspect one item ... in full" oversells `review view`.**
   `review view` shows id/kind/source-kind/object/bucket/severity/next — roughly
   the queue row minus the period, with no transaction date/amount/description.
   The actual per-transaction detail comes from the suggested next command
   (`aeat app ledger review <id>`). Fix: soften "in full," or have `view`
   include the underlying record detail it implies.

5. **[MINOR] [DOC] Page assumes a populated queue and an existing profile.**
   With a fresh profile and no transactions the queue is empty; the page never
   says you must first create a profile and import/enter rows. A naive reader
   arriving here first sees nothing and cannot tell whether the tool is broken.
   Fix: add a one-line precondition ("you need an active profile with imported
   transactions or a modelo draft; see Import bank statements / Create a
   profile") near the top.

6. **[NIT] [DOC] Passphrase requirement is unmentioned.**
   None of the documented commands warn that a master-key passphrase is
   required. In this harness it is pre-set, but a naive user in a non-interactive
   shell with no `AEAT_SECRET_PASSPHRASE` would be blocked. Fix: link to the
   passphrase/profile setup note, consistent with other how-to pages.

7. **[NIT] [DOC] `Periodo` shows a month (`2026-01`), not an AEAT period token.**
   The page calls the column "the period." The value rendered is a calendar
   month (`2026-01`), not the AEAT token grammar (`1T`, `0A`) used elsewhere in
   the CLI. Minor inconsistency a careful reader will notice.

## Testimonial

Working the queue felt mostly smooth: it really is a tidy to-do list, every row
hands you the exact next command, and following that command did reveal and let
me act on the transaction — so the core promise held. But two things made me
distrust the page. It tells me twice that "the JSON output always carries the
`legal_refs`," yet I could not find any way to actually get JSON — `--json`,
`--format json`, `--output json` were all rejected outright. And when I fat-
fingered a `--kind`, the page promised the accepted set would be named, but the
app just said "value invalid" with no list, leaving me to guess. The table also
had two more columns than the page described, one of them printing a raw
`<profile-id>` placeholder, which made me wonder if I'd broken something. The
queue works; the page over-promises around JSON and error messages.

## Scorecard

- **Doc clarity:** 3 / 5
- **App capability:** 3 / 5
- **Findings by severity:** BLOCKER 0 · MAJOR 2 · MINOR 3 · NIT 2
