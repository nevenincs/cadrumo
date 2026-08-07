---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:b3da114b8fc1da69b85f833e0e258f35b08f98a090f5042e4fb1dde0b0035b48'
step_id: 'S25'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Normalize tabular dialects covering delimiter, decimal convention, encoding, preamble rows, summary rows and embedded newlines into one typed table, gated by all nine bundled operator CSV exports normalizing against the current 1-of-7 baseline

## Scope

- `src/cadrumo/adapters/inbound/financial`

## Description

- Re-measure the baseline by driving the real provider detection and ingest over
  the nine operator tabular exports.
- Bundle those nine exports as fixtures with provenance sidecars, verifying each
  licence and sha256 against the source corpus manifest.
- Add `_tabular_dialect.py`: decoding, delimiter detection, header location,
  preamble and summary separation, decimal-convention inference, typed notices.
- Export the normalization surface through the providers facade and the parent
  financial facade.

## Outcome

All nine bundled exports normalize into a typed table. The baseline was
re-measured rather than taken on report: driving the real detection and ingest
over the same nine files imported **one**. One export parsed, one died on an
appended `TOTAL` row read as a date, and seven were refused at detection.

Every axis and what each file contributes:

| export | delimiter | decimal | preamble | summary | note |
| --- | --- | --- | --- | --- | --- |
| `bank_bbva_2026Q1.csv` | `;` | comma | 3 | 0 | the one file that imported before |
| `bank_caixa_excel_export_2026Q1.csv` | `;` | comma | 2 | 1 | the `TOTAL` row that broke ingest |
| `bank_neobank_2026Q1.csv` | `,` | dot | 0 | 0 | ISO dates, English headers |
| `bank_statement_2026Q1_Q2.csv` | `;` | comma | 7 | 0 | deepest preamble |
| `expenses_app_export_2026.csv` | `,` | dot | 0 | 0 | newline inside a quoted field |
| `ledger_erp_export_2026Q1.tsv` | tab | comma | 0 | 0 | debit/credit split columns |
| `libro_facturas_expedidas_2025_2026.csv` | `,` | dot | 0 | 0 | UTF-8 byte-order mark |
| `libro_facturas_recibidas_2025_2026.csv` | tab | comma | 0 | 0 | Spanish invoice book |
| `pos_zreport_20260514.txt` | `\|` | comma | 2 | 1 | pipe-delimited, `TOTALES` row |

Cell text is stored verbatim, so a Spanish printed amount keeps its printed form
and the detected convention travels beside it as recorded metadata rather than
replacing the value.

Delimiter detection scores a whole-file rectangle instead of sampling a window,
because a metadata preamble defeats a sample-window sniffer. Header location
scores a candidate row together with the row below it, because a populated
metadata line is otherwise indistinguishable from a real header on its own.

### Two duplication risks adjudicated before writing anything

The existing CSV provider is an **exact fixed-layout** parser: five named bank
layouts matched by scoring header aliases. It is not a general dialect
normalizer, and extending it would have made it both exact and general at once,
which is the shape that later has to be pulled apart. The normalizer was built
as a sibling and that provider was left untouched.

**No decimal parser was written.** The convention-detection helper only decides
*which convention a file uses*, and delegates the genuinely ambiguous case to the
existing shared ambiguity predicate. No value is converted anywhere in this lane;
conversion stays in the existing shared amount parser, which the mapping lane
calls with the detected separator.

## Verification

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/ -p no:randomly -n0
    142 passed in 5.71s

Collection counts read from the log on disk, confirming the default marker lane
deselected nothing:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/ --collect-only -n0
    142 tests collected in 1.79s

Two mutations proved this Step's gate bites, both applied from a throwaway
plugin outside the repository so no tracked file changed. Suppressing
summary-row recognition reddened **four** tests, including the dialect-axis
assertion for each of the two bundled exports that carry an aggregate row.
Capping the header search at the first line, so a preamble reads as data,
reddened **eleven**. Both were restored and the suite re-run green.

## Notes

### Three assignment premises corrected by measurement

There is **no `parse_date` in `core.parsing`** — that module exports the ISO
currency normaliser. The shared day-first date parser is `parse_date_value` in
the providers' own `_base.py`, and that is what this lane reuses.

**No bundled export is cp1252 or latin-1.** All nine decode as UTF-8, one
carrying a byte-order mark, so the encoding axis is present in this corpus only
as that mark.

**Nothing is undecodable**, because the tail of the shared fallback chain maps
all 256 byte values. The refusal branch in the decoder is therefore unreachable
defence-in-depth rather than a live path, and the test asserts the **reported
fallback** instead — the only real signal that the preferred codec did not fit.
A paired positive control asserts a UTF-8 source raises no such report, so the
assertion cannot pass by the reporter firing unconditionally.

### Fixtures

Nineteen files bundled: the nine exports plus a provenance sidecar each, and the
package marker. Every one is CC0-1.0, synthetic and generated per the source
corpus manifest, and each copy was sha256-verified byte-identical against that
manifest at bundle time. **Nothing was declined** — no licence was unresolved or
copyleft.

### Incidents

An initial numeric-cell predicate condensed a cell by dropping its letters,
which made a header such as `col_0` read as a number and cost the header
detector its first synthetic table. Corrected to set aside only a currency
symbol or an isolated ISO code, so letters interleaved with digits disqualify a
cell as an amount.

The source and fixtures of this Step were committed by a concurrent tree-wide
peer sweep rather than by this Step's own commit. HEAD content was verified to
match the working tree for every path before proceeding.
