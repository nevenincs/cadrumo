# Adversarial QA — LEDGER edge cases

Persona: adversarial QA probing `aeat app ledger` via the real CLI.
Harness: `/tmp/edge-ledger` (+`/tmp/edge-ledger-small` for the reset threshold).
Date: 2026-06-19. Profile: `p` (12345678Z, Ana Garcia Lopez, consultoria).

Verdict legend: OK = correct behaviour (accept or instructive refuse); BUG = defect.
Exit codes captured via `${PIPESTATUS[0]}` (tail masks the real code otherwise).

---

## Amount edges

### EDGE 1 — zero amount
- Cmd: `ledger add --date 2026-03-01 --amount 0 --direction INCOMING --description "zero amt"`
- Expected: refuse (amount must be non-zero).
- Actual: `Invalid value: ... manual ledger transaction amount must be non-zero; attach zero-value evidence to an existing row`. Exit 2.
- Verdict: OK (correct refusal, instructive).

### EDGE 2 — negative amount
- Cmd: `ledger add --amount -50 --direction OUTGOING ...`
- Expected: refuse (magnitude must be non-negative; sign carried by --direction).
- Actual: `Invalid value: El --amount -50 debe ser una magnitud no negativa. Indica el importe sin signo y define el flujo con --direction (...)`. Exit 2.
- Verdict: OK (correct refusal; aligns with ledger-amount-is-absolute rule).

### EDGE 3 — many decimals (1200.123456789)
- Expected: refuse (money is 2 decimals).
- Actual: `Invalid value: Valor decimal no válido para amount: 1200.123456789. Use el punto como separador decimal y sin separador de miles, p. ej. 1234.56.`. Exit 2.
- Verdict: OK.

---

## Date edges

### EDGE 4 — future-dated (2099-12-31)
- Actual: ACCEPTED, stored, exit 0 (`Fecha 2099-12-31`).
- Verdict: OK-ish (no future-date guard). LOW observational — a year-2099 accounting row arguably warrants an advisory; not a crash/wrong-result.

### EDGE 5 — prior-year-dated (1999-01-01)
- Actual: ACCEPTED, stored, exit 0.
- Verdict: OK-ish. LOW observational — no sanity bound on accounting date; tolerable since AEAT periods are resolved at filing time.

---

## Currency edges

### EDGE 6 — USD (real non-EUR)
- Actual: ACCEPTED, exit 0.
- Verdict: OK (multi-currency supported).

### EDGE 7 — XYZ (3 letters, NOT a real ISO 4217 code)
- Expected: arguably refuse (help says "ISO 4217 three-letter").
- Actual: ACCEPTED, stored, exit 0.
- Verdict: BUG (LOW). Validator only checks shape ~`[A-Za-z]{3}`, not actual ISO 4217 membership. A bogus currency persists silently. Help text overstates the guarantee ("ISO 4217").

### EDGE 8 — lowercase `usd`
- Actual: ACCEPTED, stored verbatim, exit 0.
- Verdict: BUG (LOW). ISO 4217 codes are uppercase; lowercase is accepted and not normalised. Risk of split currency buckets (USD vs usd).

### EDGE 9 — 2-letter `US` / EDGE 10 — 4-char `EURO` / EDGE 11 — digits `123`
- Actual: all refused — `currency: currency must be a three-letter ISO 4217 code`. Exit 2.
- Verdict: OK (length + alpha checked; digits rejected). Confirms validator is `[A-Za-z]{3}`, not real-code membership.

---

## Direction / classification edges

### INTERNAL_TRANSFER
- Cmd: `ledger add --amount 500 --direction INTERNAL_TRANSFER ...`
- Actual: ACCEPTED, exit 0.
- Verdict: OK.

### EDGE 12 — emoji/unicode description (`café 日本語 🎉💰 ñÑ`)
- Actual: ACCEPTED, rendered intact, exit 0.
- Verdict: OK.

### EDGE 13 — empty description / EDGE 14 — whitespace-only
- Actual: refused — `String should have at least 1 character` / `field must not be blank`. Exit 2.
- Verdict: OK.

### EDGE 15 — 5000-char description
- Actual: ACCEPTED, stored in full, exit 0.
- Verdict: BUG (LOW). No max_length on description; an unbounded blob persists into the encrypted record. Cosmetic/storage concern, not a crash.

### EDGE 16 — MIXED --business-pct 0 / EDGE 17 — MIXED --business-pct 1
- Actual: both ACCEPTED, review status `reviewed`, exit 0.
- Verdict: OK (boundaries 0 and 1 inclusive). Note: MIXED + pct 0 (=100% personal) is semantically odd but permitted; not flagged as a bug.

### EDGE 18 — MIXED --business-pct 1.5 / EDGE 19 — MIXED --business-pct -0.3
- Actual: refused — `La proporción de uso profesional 1.5 (= 150%) está fuera de rango. Introduce una proporción entre 0 y 1 ...`. Exit 2.
- Verdict: OK (instructive, shows percent).

### EDGE 20 — BUSINESS + --business-pct 0.5 (contradictory)
- Actual: refused — `business_pct must be None unless classification is MIXED`. Exit 2.
- Verdict: OK (cross-field validation).

### EDGE 21 — MIXED with NO --business-pct
- Actual: refused — `business_pct is required when classification is MIXED`. Exit 2.
- Verdict: OK.

---

## Split / merge edges

### EDGE 22 — split into 3 balanced children (100+100+100=300) --yes
- Actual: succeeded, 3 child ids returned, split_group id emitted, exit 0.
- Pre-check: without --yes -> `Pasa --yes para confirmar esta operación destructiva del libro.` Exit 2 (OK).
- Verdict: OK.

### EDGE 23 — split children NOT summing (100+100+50=250 != 300) --yes
- Actual: `Error. ledger split child amounts must sum to the parent amount exactly` with child_amounts / child_sum / parent_amount. Exit 1.
- Verdict: OK (clear diagnostic).

### EDGE 24 — merge PARTIAL cohort (2 of 3 children of one split_group) --yes
- Actual: `Error. ledger merge cohort is incomplete; every child of the split_group must be supplied` enumerating expected vs supplied. Exit 1.
- Verdict: OK. (Also confirmed: merging children from different split_groups -> `children must all share one split_group_id`. OK.)

---

## Lifecycle edges

### Lifecycle cycle: archive -> restore -> stash -> restore -> remove
- Actual: each step succeeded, exit 0; final remove reports `Eliminado True`, `DRY RUN False`.
- Verdict: OK (full cycle clean).

### EDGE 25 — restore an ACTIVE (never archived) row
- Actual: `Error. ledger transaction is already active; restore applies only to a stashed or archived row` (state ACTIVE). Exit 1.
- Verdict: OK.

### EDGE 26 — archive an ALREADY-archived row
- Actual: `Error. ledger transaction is already archived` (state ARCHIVED). Exit 1.
- Verdict: OK.

### EDGE 27 — remove an already-removed row
- Actual: `Invalid value: Ninguna transacción coincide con el prefijo de id %'f31622...'`. Exit 2.
- Verdict: OK behaviourally (gone after first remove) BUT see EDGE 49 for the `%'...'` text bug.

### EDGE 28 — operate on bogus/nonexistent id (archive/remove/view deadbeefdeadbeef)
- Actual (after peer-WIP settled): all refuse cleanly — `Invalid value: Ninguna transacción coincide con el prefijo de id %'deadbeefdeadbeef'.` Exit 2.
- Verdict: OK behaviourally; carries the `%'...'` text bug (EDGE 49).
- NOTE — TRANSIENT NON-LEDGER CRASH: the FIRST run of EDGE 28 produced a RAW TRACEBACK,
  `NameError: name 'catalogue_app' is not defined` at
  `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py:64` (exit 6, "Internal").
  Root cause: that file had uncommitted peer WIP (+173 lines over commit 636acce08) — a
  concurrent agent mid-edit introduced a module-import-time NameError. It self-resolved
  on the next run and `ledger list/add/invoice --help` all worked. Classified as
  IN-FLIGHT PEER CHURN, not an owner-surface ledger bug (per full-tree-gate-must-
  distinguish-owner). Flagged for the peer owner of `_ledger_business_invoice_cli.py`.

---

## Reset edges

### EDGE 29 — reset --dry-run
- Actual: `Filas 26 / Reiniciado False / DRY RUN True`. Exit 0.
- Verdict: OK.

### EDGE 30 — reset WITHOUT --yes
- Actual: `Pasa --yes para confirmar esta operación destructiva del libro.` Exit 2.
- Verdict: OK.

### EDGE 31 — reset --yes (real) on a 26-row ledger  *** WORST ISSUE ***
- Actual: pydantic `ValidationError in ledger_reset`: field
  `payload.removed_transaction_ids` `String should have at most 500 characters`
  (max_length=500). The catalogue was NOT cleared (subsequent `ledger list` still shows
  all rows). Exit 2.
- Threshold confirmed on `/tmp/edge-ledger-small`: reset SUCCEEDS at 7 rows
  (7*64 + 6 commas = 454 chars < 500) and FAILS at 8 rows (8*64 + 7 = 519 chars > 500).
- Verdict: **BUG (HIGH)**. `ledger reset --yes` is unusable once a ledger holds 8+
  transactions — a realistic, common state. The result-envelope schema caps the joined
  removed-id CSV at 500 chars; a moderately-sized ledger overflows it and the reset is
  refused (and silently does nothing beyond the error). `--dry-run` does NOT hit this
  (it reports a count, not the joined id string), so the failure is hidden until the
  real run. Fix: the `removed_transaction_ids` result field should be a list/sequence
  (or have no 500-char cap), not a single capped string.

---

## Classify edges

### EDGE 32 — classify with bogus --category-id
- Actual: `--category-id 'NOT_A_REAL_CATEGORY' no reconocido. Pasa un id de categoría sin prefijo como 'cuotas_colegiales' ... Ejecuta 'aeat app ledger categories' ...`. Exit 2.
- Verdict: OK (instructive, points to `categories`).

### EDGE 33 — classify --from-csv with bad classification value (WIBBLE)
- Actual: per-row report `1 filas, 0 aplicadas, 0 omitidas, 1 fallidas` then `failed ... 1 validation error for BulkClassifyRow / classification / Input should be 'BUSINESS'...`. **Exit 0.**
- Verdict: BUG (LOW-MED). Behaviour graceful but exit code 0 on an all-rows-failed CSV
  is a silent failure for automation. Raw pydantic class name (`BulkClassifyRow`) leaks
  into the operator message.

### EDGE 34 — classify --from-csv with wrong headers
- Actual: `Error. bulk classify CSV contains unknown columns: header, wrong`. Exit 1.
- Verdict: OK.

### EDGE 35 — classify --from-csv with nonexistent tx id
- Actual: `failed ffffffffffffffff transaction not found: ffffffffffffffff`. **Exit 0.**
- Verdict: BUG (LOW-MED). Same exit-0-on-all-failed concern as EDGE 33.

### EDGE 36 — classify --from-csv MIXED row without business_pct
- Actual: `failed ... business_pct is required when classification is MIXED` (leaks `ManualLedgerTransactionCommand`). **Exit 0.**
- Verdict: BUG (LOW-MED). Same exit-0 concern; raw command class name leaks.

### EDGE 37 — classify --from-csv nonexistent file
- Actual: `Invalid value: Archivo CSV no encontrado: ...does-not-exist.csv`. Exit 2.
- Verdict: OK.

---

## Import edges

### EDGE 38 — import garbage CSV (provider auto)
- Actual: `Error. auto-detection of ledger format failed for ...`. Exit 1.
- Verdict: OK.

### EDGE 39 — import CSV with malformed rows (provider csv)
- Actual: `Error. No se puede importar el extracto bancario: CSV row 2 could not be parsed: unsupported date format: 'NOTADATE'`. Exit 1.
- Verdict: OK (names the offending row + reason).

### EDGE 40 — import nonexistent path
- Actual: `Error. El archivo de origen no existe: ...nope.csv`. Exit 1.
- Verdict: OK.

### EDGE 41 — import bogus provider (banana)
- Actual: `Invalid value: Proveedor de importación --provider 'banana' desconocido. Proveedores reconocidos: auto, csv, ofx, qfx, xlsx, excel, n26, pdf, pdf-n26.`. Exit 2.
- Verdict: OK (lists accepted set).

---

## List filter edges

`ledger list` takes filters via `--filter "key=value"` (NOT `--period`/`--year` flags;
those produce `No such option`).

### EDGE 42 — filter period=5T (bad token)
- Actual: `Periodo '5T' no reconocido. Use un token AEAT: 1T-4T ..., e indique el año con --year ...`. Exit 2.
- Verdict: OK content, but the message references a `--period 1T --year 2024` flag form
  that `list` does NOT expose (LOW inconsistency — copy-pasted from the add/import help).

### EDGE 43 — filter period=Q1 (bad grammar)
- Actual: same `Periodo 'Q1' no reconocido ...`. Exit 2.
- Verdict: OK.

### EDGE 44 — filter period=1T WITHOUT year
- Actual: `Fallo al analizar el filtro del libro cerca de period=<redacted>: ledger-period-year-pairing.`. Exit 2.
- Verdict: OK behaviourally (period needs year) BUT message leaks an internal slug
  (`ledger-period-year-pairing`) instead of plain guidance (LOW).

### EDGE 46 — filter year=-5 / EDGE 47 — filter year=abcd
- Actual: `... year=<redacted>: invalid-value-ledger-year.`. Exit 2.
- Verdict: OK behaviourally; internal slug leaks (LOW). Value redaction is good.

### EDGE 48 — filter unknown key foo=bar
- Actual: `... foo=<redacted>: unknown-key-ledger.`. Exit 2.
- Verdict: OK behaviourally; internal slug leaks (LOW).

---

## Cross-cutting text bug

### EDGE 49 — `%'...'` artifact in id-prefix-not-found errors (ALL locales)
- Symptom: every "no transaction matches id prefix" error renders
  `... prefijo de id %'deadbeefdeadbeef'.` — a stray leading `%`.
- Root cause: locale keys use `%{prefix!r}` (e.g. `en.yml:2561 id_prefix_not_found`,
  also `id_prefix_not_hex`, `id_prefix_too_long`, `id_prefix_collision`,
  `id_prefix_unknown`, in en/es/ca/hu). The project's interpolation syntax is plain
  `{var}` (e.g. `{action}`, `{profile}`) — the `%` is a leftover and `!r` is not a
  supported converter in this `{}`-style format, so `%` leaks literally and `!r`
  happens to wrap quotes. Intended output was likely `'deadbeefdeadbeef'`.
- Verdict: BUG (LOW). Cosmetic but ships in user-facing errors across all four
  languages for the entire `id_prefix_*` family. Touches the locale catalogue only
  (must be fixed via `python -m aeat.locales set ...`, not by hand).

---

## Summary

| Severity | Count | Items |
|----------|-------|-------|
| HIGH     | 1     | EDGE 31 reset --yes fails at 8+ rows (500-char result-field cap; reset does nothing) |
| MEDIUM   | 0     | — |
| LOW-MED  | 3     | EDGE 33/35/36 classify --from-csv returns exit 0 when every row fails (+ raw pydantic class names leak) |
| LOW      | several | EDGE 7/8 bogus/lowercase currency accepted; EDGE 15 unbounded description; EDGE 49 `%'...'` text artifact (all locales); EDGE 44/46/47/48 internal error-slug leaks; EDGE 42 message cites nonexistent `--period`/`--year` flags |
| TRANSIENT (not owner bug) | 1 | EDGE 28 first-run NameError `catalogue_app` from peer WIP in `_ledger_business_invoice_cli.py`; self-resolved |

Real raw tracebacks attributable to ledger logic: 0 (the one NameError was peer-WIP).
Validation, lifecycle, split/merge, and import surfaces are robust and instructive.
The single load-bearing defect is the reset 500-char cap — it bricks a core destructive
verb on any realistically-sized ledger and is masked by --dry-run.
