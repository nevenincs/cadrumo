---
doc: docs/how-to/import-bank-statements.md
persona: user with a bank CSV export who wants transactions in the ledger
author: coordinator (covered directly after the background persona for this page failed to start twice)
date: 2026-06-18
---

# Work with Transactions (import) — naive-user walkthrough

Isolated state under `/tmp/coord-import`; passphrase via env. CLI: `uv run --no-sync aeat ...`.

## Walkthrough (every documented command exercised)

- **`config profile status`** (Before you start) — OK; correctly reports active profile.
- **`ledger import ./statement.csv --provider auto --dry-run`** — same trap as quickstart: the page
  ships no `statement.csv` and never shows the CSV column format, so a literal copy/paste hits
  `FileNotFoundError` (raw traceback) + `auto-detection failed`. Once I used a realistic bank CSV
  (BBVA: `Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda`, semicolon-delimited, comma
  decimals), **`--provider auto` detected and previewed 2 rows correctly**. Verdict: DOC-ISSUE
  (missing sample/format) / APP OK.
- **`ledger import ... ` (real save)** — OK, 2 rows imported. Negative `-800,00` expense stored as
  magnitude `800` with OUTGOING direction (matches the absolute-amount/direction-authority design).
- **`ledger add` (manual, INCOMING/OUTGOING/tax fields/MIXED)** — OK; required fields enforced;
  `--business-pct` correctly rejected unless `--classification MIXED`.
- **`ledger list` (+ filters)** — OK; short + full ids, date, amount, description, review state.
- **`ledger view <id>`** — OK; full typed detail incl. lifecycle + review state.
- **`ledger classify <id> --classification BUSINESS --category-id arrendamiento_local`** — OK
  (`categories` lists valid ids grouped by family).
- **`ledger update <id> --notes ...`** — OK.
- **`ledger history <id>`** — OK; event trail (imported/classified/updated) with event ids.
- **`ledger export --output ... --year 2026 --period 2T`** — OK; wrote CSV + reported row count and
  SHA-256.
- **`ledger rule add` / `rule apply --dry-run`** — OK; a rule matching an unclassified row previews
  `1 transacción(es) se clasificarían`; a rule whose only match is already-classified previews `0`
  (correct — rules act on unclassified rows only).
- **`ledger preflight --year 2026 --period 2T`** — OK and instructive: named 4 concrete issues
  (`missing_business_classification`, `missing_taxable_base`, `missing_iva_amount`,
  `missing_iva_rate`) per transaction id.
- **Cross-links** — `../cli/index.rst` resolves (exists). Not broken.
- Not exercised live (no external services): `doclink` (Google Drive), `invoice add/list`. Page sets
  expectations for these reasonably.

## Findings

1. **[MAJOR][DOC]** No sample `statement.csv` and no CSV column format anywhere on the page (the one
   thing a brand-new importer most needs). Fix: inline the minimal accepted CSV header/format, or
   ship a downloadable sample, and name which providers map to which bank exports.
2. **[MINOR][APP]** A missing import file produces a Python `FileNotFoundError` traceback and a
   spurious `pdf_n26_provider: failed to parse PDF` ERROR log line before the friendly
   `auto-detection failed` message. Fix: clean refusal on missing file; suppress the provider-probe
   stack noise under `auto`.
3. **[NIT][DOC]** `--provider auto` recognised a BBVA CSV without any hint about which bank formats
   auto-detect supports; the recognised provider tokens (`csv, ofx, qfx, xlsx, excel, n26, pdf,
   pdf-n26`) live only in `--help`. A one-line "supported formats" note would help.

## Testimonial

This page is in much better shape than the quickstart: it is thorough, the command vocabulary is
consistent, and every single documented ledger verb I tried actually worked. My only real stumble was
the very first import — I had no `statement.csv` and the page never told me what a valid file looks
like, so my first attempt was an ugly traceback. The moment I fed it a realistic bank CSV, auto-detect
nailed the format, the rows imported cleanly, and the edit/classify/export/rule/preflight surface all
behaved exactly as documented. Preflight in particular is excellent — it told me precisely which tax
facts each row was still missing. The app clearly delivers what this page promises.

## Scorecard
- Doc clarity: 4/5 (loses a point only for the missing sample CSV / format)
- App capability: 5/5 (full ledger surface works; minor traceback-on-missing-file blemish)
- Findings: BLOCKER 0, MAJOR 1, MINOR 1, NIT 1
