# Period filter single boundary authority

Every period-scoped selection must resolve its date span through
`Period.contains()`, built from the canonical year plus the AEAT-token grammar.
No call site may implement a parallel boundary, an inclusion override, or a
legacy period alias.

`Period.contains()` is the single authority shared by CLI ledger filters, modelo
calculation snapshots, sorting, and participation-index selection. Re-derived
start/end math at call sites creates off-by-one gaps, overlaps, and inconsistent
handling of adjacent quarters or months; a continuity invariant keeps the
boundary gap-free and overlap-free.

## How

- **Good:** parse `--year 2026 --period 1T` to a `Period`, then filter rows with
  `period.contains(row.date)`; modelo snapshot selection and ledger export use
  the same object and the same inclusion semantics.
- **Bad:** accepting an alternate boundary grammar (`2026Q1`, `2026-1T`, `ANUAL`,
  `Q1`) once the canonical grammar is in force, or open-coding
  `start <= row.date <= end` with locally derived dates in a CLI handler.

Source: ADR `2026-06-10-ledger-filter-period-adr`.
