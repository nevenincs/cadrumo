---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:1925b0fa818c3aa36c2806d83a9da9bb0510a5caad2c8f4003b129f477215b04'
step_id: 'S26'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S26 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Keep DeadlineEngine.compute thin and prove exact-one complete monthly and quarterly emission without local selection or deduplication and ## Scope

- `src/cadrumo/domain/deadlines/_engine.py`
- `src/cadrumo/domain/deadlines/tests/test_engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Keep DeadlineEngine.compute thin and prove exact-one complete monthly and quarterly emission without local selection or deduplication

## Scope

- `src/cadrumo/domain/deadlines/_engine.py`
- `src/cadrumo/domain/deadlines/tests/test_engine.py`

## Description

- Trace deadline projection semantically with Vaultspec RAG and confirm exact symbols.
- Keep `DeadlineEngine.compute` as a one-for-one consumer of canonical authority rows.
- Exclude resultado/tipo-renta-qualified windows from the pre-calculation schedule and retain their existing post-calculation resolver ownership.
- Prove exact M303 2025 quarterly and REDEME monthly emission.
- Prove every applicable authored periodic authority coordinate is emitted exactly once across filing years 2022-2026.
- Align the M349 2026 regression with the explicitly grounded three-quarter and eleven-month corpus boundary.
- Run focused Ruff and deadline-engine tests and complete an independent focused review.

## Outcome

`DeadlineEngine.compute` remains thin over `ValidatedRegistryAuthority.deadline_windows`:
it contains no revision selection, runtime deduplication, period parsing, or cadence
generation. The audit exposed and repaired four indistinguishable qualified M210 `0A`
obligations in 2025 and 2026. Those windows require calculation resultado and declared
tipo-renta context, so the pre-calculation profile schedule now declines them while the
already implemented canonical post-calculation plazo resolver and typed Notice channel
remain their sole projection path.

An ordinary M303 profile emits exactly `1T`, `2T`, `3T`, and `4T` for 2025. A REDEME
profile emits exactly months `01` through `12`. The fleet regression compares engine
output against every applicable currently authored monthly/quarterly authority row for
both profiles across 2022-2026 through the shared semantic-coordinate constructor and
proves multiplicity one.

Focused verification passed: Ruff reported no findings and the complete engine test
module passed 49 tests. Independent re-review found one HIGH test-oracle weakness and
one MEDIUM locally redeclared supported-year horizon, so this Step remains open pending
their correction even though the production boundary itself was approved.

## Notes

The registry corpus still has exactly five deliberately unauthored filing-year-2026
cells whose physical deadlines require the unpublished 2027 taxpayer calendar: M303
month `12`, M322 month `12`, M353 month `12`, and M349 month `12` plus quarter `4T`.
S26 must prove one-for-one emission of the canonical rows the validated authority can
currently project without adding inferred future dates. The fleet completeness gate
remains responsible for closing those corpus cells when authoritative evidence is
enrolled.

The current fleet regression derives expected applicability through the same private
`_obligation_for_window` helper used by `compute`, so an erroneous helper exclusion can
disappear from both sides. It also hard-codes 2022-2026 instead of consuming the shared
supported-year authority. These review findings must be resolved before S26 closes.
