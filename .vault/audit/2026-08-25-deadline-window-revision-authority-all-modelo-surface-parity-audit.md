---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f14ea159d94edd43f8171bf1208409f10f6ded7026c45bdbb1e394eba5840bda'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# `deadline-window-revision-authority` audit: `all modelo surface parity`

## Scope

Audit the complete registry-to-CLI deadline projection for every filing year declared by the canonical temporal-coverage catalogue. Verify all authored pre-calculation deadline rows and every downstream consumer without introducing a second supported-year horizon, cadence authority, modelo roster, applicability evaluator, resolver, or deduplication layer.

## Findings

### registry-engine-fleet | high | Engine parity now covers every unqualified authored deadline row

The prior fleet engine witness covered monthly and quarterly rows only. It now evaluates every unqualified authored window, including annual and event periods, through the existing filing-schedule and profile-condition authorities. Qualified resultado/tipo-renta M210 windows remain excluded from pre-calculation by design and resolve through the already-tested post-calculation path.

### workflow-order-parity | high | Workflow preserves the ordered schedule for every supported year

The workflow pending-obligation projection is compared as an ordered tuple with `compute_obligation_schedule` for every year read from `catalogues.supported_filing_years`. A duplicate, omission, or reorder is visible and cannot be erased by set conversion.

### overview-legal-row-parity | high | Overview preserves every applicable engine row and legal date

For each supported filing year, overview entries are compared with applicable engine obligations on modelo, filing year, registry token, opens date, closes date, payment cutoff, and status. The query range includes following-calendar-year closes without changing filing-year identity.

### cli-visible-coordinate-parity | high | Real CLI preserves every application row across the supported horizon

Five real isolated CLI invocations are compared with the application calendar projection for the same active profile, ranges, and frozen Madrid date. The asserted ordered coordinates cover modelo, period, adjusted close, payment cutoff, and status. The CLI's native `OverviewCalendarEntrySummaryPayload` intentionally does not include raw opening and closing dates; those remain covered by application parity.

### canonical-reuse-sweep | low | Fleet parity adds no competing authority

Vaultspec RAG followed by exact-symbol inspection found and reused `supported_filing_years`, `deadline_semantic_coordinate`, `applicable_filing_schedules`, `evaluate_profile_conditions`, `DeadlineEngine.compute`, `compute_obligation_schedule`, `build_pending_obligations`, `build_overview_calendar`, `_profile_to_taxpayer`, and the existing CLI runner. No new resolver, parser, cadence map, supported-year range, modelo list, applicability rule, deadline catalogue, or deduplicator was declared.

## Recommendations

- Keep the supported filing years read from the registry catalogue at execution time.
- Keep qualified deadline variants out of pre-calculation parity and test them through canonical post-calculation resolution.
- Preserve raw legal-date parity at the application boundary and native operator-summary parity at the CLI boundary.
- Run this chain with the bundled-registry invariant and historical corpus scenarios during final closure.
