---
tags:
  - '#adr'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-app-ledger-ratios-shape-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-iva-prorrata-art-101-103-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-apoderamientos-surface-research]]"
---


# `cli-workflow-redesign` adr: `App ledger ratios eligible and validate verbs` | (**status:** `accepted`)

## Problem Statement

`aeat app ledger ratios set KEY VALUE` configures proportional-deduction
ratios for mixed-use expense categories. The app-ledger-ratios-shape ADR
lists `list`, `set`, `unset` as canonical verbs and marks `eligible` and
`show` as optional/future. An operator cannot discover which spending
categories accept a ratio without trying `set` and reading the error,
and cannot confirm their ratio set is complete before running modelo
calculations. Both gaps block routine quarterly preparation for mixed-
activity autónomos.

## Considerations

- Proportional-deduction ratios are governed by spending categories
  declared in the domain layer; not every category accepts a ratio (e.g.,
  fully-business or fully-personal categories reject ratio assignment).
- The set of categories that accept a ratio is registry-driven and may
  evolve over years.
- A pre-calculate validation surfaces missing ratio keys before the
  modelo calculate fails mid-pipeline.
- This is distinct from IVA prorrata (locked in the iva-prorrata-art-
  101-103 ADR). Ratios under `app ledger ratios` are proportional
  deduction for ledger transaction allocation; prorrata is the legal
  IVA mechanism on a different calculation path.

## Constraints

- `aeat app ledger ratios eligible [--format json|text]` enumerates the
  spending categories that accept a ratio in the current registry, with
  the canonical category id, display name, accepted ratio range
  (typically `0.0` to `1.0`), and any registry-declared constraints.
- `aeat app ledger ratios validate [--modelo MODELO] [--year YYYY]
  [--period PERIOD] [--format json|text]` runs a readiness check
  against the active bucket. Output reports:
  - categories with at least one transaction that requires a ratio but
    has no ratio set
  - categories with a ratio set but no transactions in the active
    period (informational)
  - any ratio values outside the registry-declared range (blocker)
- `validate --modelo MODELO --year YYYY --period PERIOD` scopes the
  check to a specific modelo work unit; without those flags, the check
  spans the whole bucket.
- Both verbs are read-only and emit no bucket events.
- `eligible` does not show current values; it shows the static
  catalogue. Use `list` for current values.

## Implementation

Command shapes:

```text
aeat app ledger ratios eligible [--format json|text]
aeat app ledger ratios validate [--modelo MODELO] [--year YYYY] [--period PERIOD]
                                [--format json|text]
```

Pipelines:

- `eligible`: load the spending category registry; filter to categories
  whose `ratio_eligible` flag is true; emit each with metadata.
- `validate`: load the active bucket's ledger transactions (optionally
  scoped by modelo / year / period); cross-reference with the current
  ratio set; produce a structured readiness report.

Output:

- `eligible` text: a table with `category_id`, `display_name`,
  `range_min`, `range_max`, `notes`.
- `validate` text: a per-finding report grouped by readiness type
  (`missing`, `informational_unused`, `out_of_range`); each finding
  carries a fix pointer to `aeat app ledger ratios set KEY VALUE`.
- Both verbs JSON: structured envelope per output category.

Discoverability hooks:

- `aeat app ledger ratios set KEY VALUE` rejection error for an
  unknown / ineligible category includes "Run `aeat app ledger ratios
  eligible` to see ratio-eligible categories."
- `aeat app modelo bindings list --missing` includes a readiness
  category "ratios incomplete" with a fix pointer to `aeat app ledger
  ratios validate --modelo MODELO`.

## Rationale

Mixed-activity proportional deduction is the most common autónomo tax-
preparation complication after categorisation. Without `eligible`, an
operator must blindly try `set` to discover the catalogue. Without
`validate`, modelo calculate fails mid-pipeline with a missing-binding
error rather than a focused readiness report. Both verbs are read-only
and cost nothing structurally; they close the loop between
proportional-deduction setup and modelo calculation.

## Consequences

- The app-ledger-ratios-shape ADR's optional `eligible` verb becomes
  required; `show` remains optional.
- The spending-category registry must annotate each category with
  `ratio_eligible: bool` and (where applicable) ratio range
  constraints.
- The `app modelo bindings list --missing` readiness output gains a
  category for incomplete ratios with a `app ledger ratios validate`
  fix pointer.
- Tests must cover: `eligible` enumerates only `ratio_eligible = true`
  categories; `validate` reports missing/informational/out-of-range
  findings correctly; `validate --modelo` scopes to a specific work
  unit; both verbs are read-only (no bucket events emitted); rejection
  hint in `set` references `eligible`.
