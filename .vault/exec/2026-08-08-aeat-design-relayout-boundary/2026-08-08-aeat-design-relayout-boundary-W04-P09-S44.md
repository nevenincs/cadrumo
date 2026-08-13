---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:09add858abd0eb1b59a7511d75234549d978071ae9e28bde9f0f00035374aa2a'
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

## Correction (2026-08-13)

**This record's "Measured revision state" line reported a selector value that does not match `revision.toml` at HEAD, and its "naming debt" framing rests on a narrowing that does not exist. Recorded here rather than edited into the prose above, because the record is history.**

The line above reads `period_selector = { year_from = 2025, periods = ["0A"] }`. Read directly from `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/revision.toml` at HEAD, the true value is `period_selector = { year_from = 2024, periods = ["0A"] }`. The `year_from = 2025` narrowing this record described as landed was reverted by commit `867b1fe7e7`, one day before this record was written - see the sibling `2026-08-08-aeat-design-relayout-boundary-W04-P09-S43.md` record's own correction section for the full commit history.

`valid_from = 2025-01-01` is correctly reported above and does survive at HEAD, but on its own it narrows nothing. Registry coverage is decided solely by `period_selector.includes_year(filing_year)` at `src/cadrumo/domain/calculations/registry/_temporal.py:95`; the `valid_from` comparison at `_temporal.py:117` is guarded by `if on is not None`, and no production caller passes `on`, so that branch never runs on the resolution path this record's ruling depends on.

The axis this record calls "filing year" throughout is the EJERCICIO (the fiscal year reported), not the calendar year of filing. Restated on that axis: the revision covers ejercicio 2024 onward at HEAD, correctly, grounded in Orden HAC/657/2025 (BOE-A-2025-12818) Article 1 - the orden this revision's own `orden_aplicabilidad` already cites, and which approves modelo 200 for the periodos impositivos of 2024. There is therefore no narrowing at HEAD and no naming debt: the revision is named `2024-y-siguientes` and covers ejercicio 2024 onward, so the name is accurate.

**The non-retirement RULING is unaffected.** It never rested on the narrowing described above - it rests on re-keying cost, measured in this record at 1,045 files / 3,444 occurrences within the Modelo 200 registry tree (reconfirmed unchanged; 1,205 files / 3,956 occurrences span `src/` and `dev/` combined). That cost does not depend on which axis the revision covers, so the RULING that the revision directory remains stands on its own grounds regardless of this correction. `W04.P09.S76` in the governing plan carries the conditional re-key, activating only if a future narrowing ever lands in the same commit as an ejercicio-2024 successor revision.
