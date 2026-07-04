---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S34'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace calculation-source-connectivity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S34 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extend category profile lookup to accept filing year and CCAA key and ## Scope

- `src/aeat/core/resources/_repos/category_profiles.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend category profile lookup to accept filing year and CCAA key

## Scope

- `src/aeat/core/resources/_repos/category_profiles.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Add `resolve_region_category_profiles(year)` (the per-comunidad override resolver) and `select_deductibility_profile()` (state profile / region override / fail-closed) to the renta domain. Realise the "filing year plus CCAA" lookup intent as an additive resolver-plus-selector layered over the existing year-keyed category profiles, so the state pure-year lookup stays byte-identical.

## Outcome

Region-aware category-profile selection is available and consumed by the aggregation path. Pure-year state lookups are unchanged. Landed in commit `1ca532e93a`. A domain test pins all four selection branches. Gates green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Implements ADR `2026-07-04-renta-region-deductibility` decision D2-A. The plan's `int -> (int, CCAA)` `CategoryProfileRepository` key-widening intent is satisfied by the additive resolver + selector rather than mutating the generic `ResourceCacheRepository[..., int]` key type — the same backward-compatible outcome (pure-year lookups untouched) with far smaller blast radius.
