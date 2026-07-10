---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S35'
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
     The S35 and 2026-05-20-calculation-source-connectivity-plan placeholders are machine-filled by
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
     The Represent region scoped category profiles in registry resources and ## Scope

- `src/aeat/_data/registry/aeat/categories/profiles` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Represent region scoped category profiles in registry resources

## Scope

- `src/aeat/_data/registry/aeat/categories/profiles`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Provision the per-comunidad category-profile override-layer shape via `resolve_region_category_profiles(year)` and leave it deliberately EMPTY. No registry TOML override entries are authored.

## Outcome

Closed DONE-EMPTY per ADR `2026-07-04-renta-region-deductibility` decision D2-C. The override mechanism exists; a future territorial-regime enrolment populates it grounded to its regime law with no further architectural change. Landed in commit `1ca532e93a`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

Honest empty layer, not an omission. No `SpendingCategory` warrants a per-comunidad expense-deductibility override today, because the two genuinely region-varying expense-side regimes are OUT of this table by construction: the Reserva para Inversiones en Canarias (Ley 19/1994 art. 27) reaches the base through its OWN dedicated binding, and the Ceuta/Melilla benefit is an art. 68.4 CUOTA deduction (not base-imponible; Ceuta and Melilla are excluded from the `CCAA` enum as ciudades autonomas). Both regime legal bases are already bundled in corpus (`ley-19-1994-art-27.html`, `ley-35-2006-art-68-4.html`), so nothing needed fetching and no regulated value was fabricated.
