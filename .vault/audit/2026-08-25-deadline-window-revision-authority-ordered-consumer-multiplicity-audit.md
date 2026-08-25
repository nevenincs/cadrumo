---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1ecf0bb72db6b6e9fb36045568a279d3a8aade192e52e6e45d848877dcf70fea'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# `deadline-window-revision-authority` audit: `ordered consumer multiplicity`

## Scope

Audit the overview calendar and workflow deadline-stage regressions for transformations that erase obligation multiplicity or ordering, and confirm that the changes reuse the canonical deadline engine schedule without introducing another resolver, selector, or coordinate model.

## Findings

### multiplicity-erasing-workflow-parity | high | Set equality concealed duplicate schedule rows

The workflow parity test converted both the deadline schedule and pending-obligation projection to sets. That proved membership only: a repeated canonical obligation would disappear before comparison. The test now compares ordered tuples of the existing semantic coordinates `(modelo, period, opens_on, closes_on, status)`.

### overview-sortedness-only | medium | Generic sortedness did not pin the expected Modelo 303 cardinality

The overview suite proved that returned entries were sorted but did not prove the operator-visible quarterly schedule had exactly four rows. A real-registry regression now asserts the ordered `(modelo, filing_year, registry_token)` tuple for Modelo 303 in filing year 2025, including the Q4 filing window that closes in 2026.

### canonical-owner-reuse | low | No resolver or schedule producer was redeclared

Vaultspec RAG and exact symbol search located `DeadlineEngine.compute`, `compute_obligation_schedule`, `build_pending_obligations`, `build_overview_calendar`, and `_target_obligation_from_schedule` as the existing owners and consumers. The change is test-only and invokes those owners directly; it adds no parser, selector, cadence map, deadline resolver, or deduplication layer.

## Recommendations

- Keep consumer parity assertions ordered and multiplicity-preserving; do not normalize legal obligation rows through sets or dictionaries.
- Keep the explicit duplicate-target refusal alongside end-to-end coordinate parity so upstream cardinality defects fail at both projection and selection boundaries.
- Treat the four-row Modelo 303 witness as an operator-visible regression while the all-model fleet parity step broadens the same invariant.
