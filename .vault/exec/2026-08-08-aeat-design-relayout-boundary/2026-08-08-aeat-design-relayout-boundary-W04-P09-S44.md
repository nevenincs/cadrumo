---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:8ff2b75637d77ef38b7b6a0b9479bae44312942d7a745bf1d91869c191d13ad4'
step_id: 'S44'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# Do not retire the Modelo 200 revision directory

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/200/revisions/`

## Description

Evaluated the cost and consequence of retiring the Modelo 200 `2024-y-siguientes` revision directory after narrowing its applicability to filing year 2025 onward.

## Outcome

**RULING: The revision directory REMAINS.** The narrowing accomplished by S43 — setting `valid_from = 2025-01-01` and `period_selector.year_from = 2025` — is sufficient. Filing year 2024 now refuses to resolve and 2025+ continues to resolve to the correctly-scoped tree. Re-keying is not necessary to prevent the revision from claiming a year it should not cover.

**Re-keying cost is prohibitive.** Measured at HEAD: **1,045 files carry 3,444 occurrences** of the `2024-y-siguientes` revision id within the Modelo 200 registry tree. Beyond the registry, **20+ external test modules** reference Modelo 200's revision id directly, several in concurrent executor lanes (confirmed by sampling imports and test fixtures). Re-keying both scopes creates unacceptable blast radius across parallel work.

**Measured revision state:** The revision's `revision.toml` correctly narrows applicability with `valid_from = 2025-01-01` and `period_selector = { year_from = 2025, periods = ["0A"] }`.

**CRITICAL PREMISE CHANGE:** The neighbouring S43 record states "retains its export fragment tree unchanged." That premise is now false. **The export fragment tree for this revision was deleted** in commit `b57cebf353` ("Registry work: 200", 2026-08-11) as part of the sibling campaign. The tree holds zero files at HEAD. The non-retirement ruling stands on its own grounds (the re-keying cost) independent of the export tree's existence.

**Naming debt restated and deferred separately:** The revision is named `2024-y-siguientes` while covering 2025 onward. This is correctness (the year 2024 is outside the scope) paired with a misleading label. Tracked as its own Step rather than compounded into re-keying work.

## Notes

The export tree deletion was confirmed via `git ls-files "src/cadrumo/_data/registry/aeat/modelos/200/revisions/*/export/*" | wc -l`, which returned zero at HEAD across all Modelo 200 revisions. The deletion commit b57cebf353 included 148 delete lines from the export directory, concentrated in casillas and export TOML fragments.
