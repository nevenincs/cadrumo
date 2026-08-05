---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:1032618e5741186c4f190df43a529ba4efdcbaa29036bb877df40bc56f4845cc'
step_id: 'S26'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace minimo-descendientes-eligibility with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-08-04-minimo-descendientes-eligibility-plan placeholders are machine-filled by
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
     The Apply the pre-2023 cotizaciones ceiling to the computed casilla 0611 for filing years 2020 to 2022 only, or refuse to compute it for those years, because the law in force through 2022 additionally limited the deduction to the mother total Seguridad Social cotizaciones while the computation applies only the 1200 euro cap, and although the un-ceilinged arithmetic predates this campaign the wiring changed the exposed population from operators who explicitly typed the calculate flag to every operator with declared descendant months, so the defect is now reachable by default rather than newly created, and the registry declares the cotizaciones binding only in 2024 so it cannot express the ceiling for the affected years at all and ## Scope

- `src/cadrumo/domain/contribuyente/_deduccion_maternidad.py`
- `src/cadrumo/application/modelo/_profile_binding.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Apply the pre-2023 cotizaciones ceiling to the computed casilla 0611 for filing years 2020 to 2022 only, or refuse to compute it for those years, because the law in force through 2022 additionally limited the deduction to the mother total Seguridad Social cotizaciones while the computation applies only the 1200 euro cap, and although the un-ceilinged arithmetic predates this campaign the wiring changed the exposed population from operators who explicitly typed the calculate flag to every operator with declared descendant months, so the defect is now reachable by default rather than newly created, and the registry declares the cotizaciones binding only in 2024 so it cannot express the ceiling for the affected years at all

## Scope

- `src/cadrumo/domain/contribuyente/_deduccion_maternidad.py`
- `src/cadrumo/application/modelo/_profile_binding.py`

## Description

Gate the maternidad month resolver on the filing year, withholding the deduccion for
years in which the cotizaciones ceiling applied and the engine cannot express it.

Name the cutover as a constant, separate from the alta-posterior gate that shares its
value.

Disclose the withholding through the calculate path's advisory channel, with the hand
computation the operator can perform from a certificate they already hold.

## Outcome

The over-grant is closed for exactly 2020, 2021 and 2022. A descendant eligible on every
other axis, declaring a full twelve months, now yields nothing for those years and yields
the full pairing from 2023. The boundary was verified by resolving the same record across
2020 to 2024 and observing the transition fall precisely between 2022 and 2023.

Withholding rather than authoring the ceiling was forced rather than preferred. The
cotizaciones binding exists only in the 2024 registry revision and the profile fact is
2024-pinned with no equivalent for any earlier year, so applying the cap would require
authoring three years of profile facts, their entry surface and their bindings, and then
demanding a figure this application has never collected for those years.

## Notes

The guard asserts THE CEILING rather than this campaign's innocence, and that phrasing is
the substance of the Step rather than a stylistic choice. The un-ceilinged arithmetic
predates the campaign: the retired calculate-time flag computed the same product with no
cotizaciones term, and what the campaign changed was the population reaching it, from
operators who typed a flag to every operator with declared months. A guard asserting "this
campaign introduces no un-ceilinged path" would have been satisfied by the flag path that
already had one. That is the third acceptance criterion on this campaign that would have
certified the defect it guards.

2023 is deliberately excluded. The manual fixes the cutover at 1 January 2023, and a fix
spanning four years would trade this over-grant for an under-grant in the first year the
deduccion was correctly un-capped -- the same year-scoping error this Phase has now met
from both directions.

The cutover constant shares a value with the alta-posterior gate and is deliberately not
merged with it. They are two independent rules that happen to change in the same reform,
and a shared constant would silently move one if the other were corrected.

The blocker is the campaign's own founding defect in a second guise, and that is worth
more than the tax fix. `cotizaciones_ss_madre_2024` is a YEAR-SUFFIXED fact name, the same
shape as the year-suffixed derived fields that made the operator's list grow without
bound and started this campaign. Suffixing the year into the fact name makes the concept
inexpressible for every other year, so the ceiling could not be applied to 2020-2022 even
though the statute plainly required it. The next person wanting a cross-year figure will
hit the identical wall, and the fix is the same one this campaign has been applying
elsewhere: parameterise the year rather than encoding it in the name.

Four failures in the surrounding suite are foreign and were attributed rather than
assumed: two bare modelo-code literals in a peer's mid-refactor validator, and three
registry-parity failures from the localization cascade rewriting the Modelo 036 revision.
Both files are peer-dirty in the working tree.
