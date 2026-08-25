---
tags:
  - '#audit'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:47bad6f266f2136e94d6d38d73a22a95d4a8b84170a9ce63bbc7d69a5b97f61f'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# `deadline-window-revision-authority` audit: `historical engine CLI scenarios`

## Scope

Audit every repaired modelo in the adjudicated deadline census at the registry boundary, then verify the canonical engine and real CLI projections across the registry-owned supported filing-year horizon.

## Findings

### repaired-model-census | high | Every repaired modelo passes its exact historical registry scenarios

The exact registry modules for modelos 111, 115, 123, 130, 131, 190, 193, 202, 210, 216, 303, 322, 349, 353, and 369 passed 235 tests. These modules assert the authored historical periods, legal dates, sources, revision selection, and canonical ownership expected by each modelo's adjudicated census.

### canonical-coordinate-reuse | medium | A stale M322 test now calls the existing singular resolver

The M322 census test referenced a nonexistent `window.semantic_coordinate` attribute. It now calls `deadline_semantic_coordinate("322", window.period, None, None)`, the existing base-window identity resolver. The plural expansion resolver was evaluated and rejected for this assertion because it correctly expands each unqualified M322 window into eleven coordinates: one unqualified base identity plus ten qualified result identities. That is a different semantic question.

### engine-fleet-scenarios | high | Both IVA profile variants preserve every applicable authored pre-calculation coordinate

The engine fleet invariant passed for quarterly and monthly IVA profiles across every year read from `catalogues.supported_filing_years`. Expected rows reuse the registry's semantic-coordinate, filing-schedule, and profile-condition authorities and compare exact multiplicity with `DeadlineEngine.compute`.

### real-cli-historical-parity | high | The actual CLI matches the application projection across all supported years

The real JSON calendar command passed its full supported-year loop. The expected projection and CLI execution share one execution-local `today_madrid()` sample, preventing a midnight split while avoiding any durable definition of today. Ordered modelo, period, adjusted-close, payment-cutoff, and status rows match without set conversion.

### no-redeclaration | high | Historical closure added no competing authority

Vaultspec RAG discovery followed by exact-symbol inspection located and reused `deadline_semantic_coordinate`, `bundled_authority().deadline_windows`, `catalogues.supported_filing_years`, `DeadlineEngine.compute`, and `build_overview_calendar`. The only source change is a test call to the canonical resolver; no production code or data authority was added.

## Recommendations

- Keep exact per-modelo registry scenarios paired with the fleet engine and real CLI projections.
- Keep temporal comparisons execution-relative by sampling the clock once; never encode "today" as a persistent registry or test fact.
- Preserve singular base-window identity and plural qualified-identity expansion as separate canonical operations.
