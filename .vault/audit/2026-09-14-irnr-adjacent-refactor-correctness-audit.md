---
tags:
  - '#audit'
  - '#irnr-adjacent-refactor-correctness'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:cfe46bc695226d72e7d1f4fe1e67299fb950981af8654cedd0f7b66c9a0b3abb'
related:
  - "[[2026-09-14-irnr-adjacent-refactor-correctness-reference]]"
---
# `irnr-adjacent-refactor-correctness` audit: `IRNR adjacent-refactor correctness final review`

## Scope

Reviewed the coordinated LANE-2 changes for detail-row ownership, Modelo 349 period selection and wire mirrors, Modelo 210 grouping and payer applicability, formula identity, profile hydration, convenio token use, M347 EUR authority, and Modelo 210 deadlines. The review checked that membership and semantics remain registry-owned and that affected consumers use explicit filing coordinates.

## Findings

### irnr-adjacent-refactor-correctness | medium | Detail catalogue projections allowed implicit wall-clock selection

The initial implementation allowed `resolve_detail_bearing_modelos` and `resolve_detail_row_owning_modelos` to reach a `date.today()` fallback. This could select a different registry variant than the work unit. The finding is resolved: both projections now require `effective_date`, calculation and amendment callers derive it from the filing year, and Modelo 349 validation supplies the rectified filing coordinate.

### irnr-adjacent-refactor-correctness | medium | Row construction validated payer applicability without a filing coordinate

The initial `Modelo210AgrupacionRentaRow` validator called the payer-mode resolver without an effective date. The finding is resolved: the opaque row retains typed identity only, while code-specific payer applicability is enforced by the grouped-renta validator against its required explicit effective date.

### irnr-adjacent-refactor-correctness | high | Concurrent exception migration prevents acceptance execution

The combined acceptance run cannot start because importing `cadrumo.core.config_state_root` currently refuses: `FormerProductStateError` has no declared error-code registry entry. This file and the shared error-code registry belong to concurrent LANE-1 and were not edited by LANE-2. Authority publication also refused safely when concurrent compiler changes altered the candidate during validation. No test result is claimed while this external pre-collection failure remains.

## Recommendations

Complete the LANE-1 registration for `FormerProductStateError`, then publish the validated authority generation through the canonical pipeline and execute the recorded LANE-2 collection and focused acceptance sequence. Retain the explicit-date signatures and keep code-specific payer applicability out of opaque row construction.
