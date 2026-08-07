---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:6312dd8940c10268c260ce296a65e5175987475c91a01e0f0cb9e9d643660dbd'
step_id: 'S25'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---




# Normalize tabular dialects covering delimiter, decimal convention, encoding, preamble rows, summary rows and embedded newlines into one typed table, gated by all nine bundled operator CSV exports normalizing against the current 1-of-7 baseline

## Scope

- `src/cadrumo/adapters/inbound/financial`

## Description


- Measure the current baseline by driving the real provider detection and ingest
  over the nine operator tabular exports.
- Bundle those nine exports as fixtures with provenance sidecars, verifying each
  licence and sha256 against the source corpus manifest.
- Add `_tabular_dialect.py`: decode, delimiter detection, header location,
  preamble and summary separation, decimal-convention inference, typed notices.
- Export the normalization surface through the providers facade and the parent
  financial facade.

## Outcome

All nine bundled exports normalize into a typed table. The measured starting
point was one of nine importing: one export parsed, one died on an appended
`TOTAL` row read as a date, and seven were refused at detection.

Delimiter, decimal convention, encoding, preamble depth, summary rows and a
newline embedded in a quoted field are each detected rather than assumed. Cell
text is stored verbatim, so a Spanish printed amount keeps its printed form and
the detected convention travels beside it as recorded metadata rather than
replacing the value.

Delimiter detection scores a whole-file rectangle instead of sampling a window,
because a metadata preamble defeats a sample-window sniffer. Header location
scores a candidate row together with the row below it, because a populated
metadata line is otherwise indistinguishable from a real header.

Two premises in the assignment did not survive measurement and are recorded in
Notes.

## Verification


The gate, and the whole owning package:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/ -p no:randomly -n0
    142 passed in 5.71s

Collection counts read from the log on disk, confirming nothing was deselected
by the default marker lane:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/ --collect-only -n0
    142 tests collected in 1.79s

Two mutations proved the gate bites, both applied from a throwaway plugin
outside the repository so no tracked file changed. Suppressing summary-row
recognition reddened four tests, including the two bundled exports that carry an
aggregate row. Capping the header search at the first line, so a preamble reads
as data, reddened eleven. Both were restored and the suite re-run green.

## Notes


Two assignment premises were wrong on measurement. No bundled export is cp1252
or latin-1; all nine decode as UTF-8, one carrying a byte-order mark, so the
encoding axis is present only as that mark. And no byte sequence is undecodable,
because the tail of the shared fallback chain maps all 256 byte values — the
refusal path in the decoder is unreachable defence-in-depth, and the test asserts
the reported fallback instead, which is the only signal the preferred codec did
not fit.

An initial numeric-cell predicate condensed a cell by dropping its letters, which
made a header such as `col_0` read as a number and cost the header detector its
first synthetic table. Corrected to set aside only a currency symbol or an
isolated ISO code, so letters interleaved with digits disqualify a cell.

The source and fixtures of this Step were committed by a concurrent tree-wide
peer sweep rather than by this Step's own commit. HEAD content was verified to
match the working tree for every path before proceeding.
