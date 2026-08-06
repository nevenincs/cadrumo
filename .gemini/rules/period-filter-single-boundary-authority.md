---
name: period-filter-single-boundary-authority
trigger: always_on
---

# Period filter single boundary authority

## Rule

Every period-scoped selection must resolve its date span through `Period.contains()` built from the canonical year plus AEAT-token grammar; no call site may implement a parallel boundary, inclusion override, or legacy period alias.

## Why

The `2026-06-10-ledger-filter-period-adr` made `Period.contains()` the single authority shared by CLI ledger filters, modelo calculation snapshots, sorting, and participation-index selection. Re-derived start/end math at call sites creates off-by-one gaps, overlaps, and inconsistent handling of adjacent quarters or months. A continuity invariant keeps the boundary gap-free and overlap-free.

## How

- Good: parse `--year 2026 --period 1T` to a `Period`, then filter rows by calling `period.contains(row.date)`.
- Good: modelo snapshot selection and ledger export use the same `Period` object and the same inclusion semantics.
- Bad: accepting `2026Q1`, `2026-1T`, `ANUAL`, or `Q1` as alternate boundary grammars after the canonical grammar is in force.
- Bad: open-coding `start <= row.date <= end` with locally derived dates in a CLI handler.
