---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9339eaa35b9ec613d308200d82368a91f54247f81175416c0497d9edaf5210d8'
step_id: 'S08'
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
     The {S##} and {yyyy-mm-dd-*-plan} placeholders are machine-filled by
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
     The Fleet periodic deadline completeness hard gate and  placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Fleet periodic deadline completeness hard gate



## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

## Context

## Scope

- `src/cadrumo/domain/calculations/registry/_validate.py`
- `src/cadrumo/domain/calculations/registry/_validate_revision_rules.py`
- `src/cadrumo/domain/calculations/registry/tests/test_deadline_window_ownership.py`

## Outcome

Registry construction now hard-fails when a periodic filing-schedule coordinate selected by `select_revision` has no deadline window for a year in the canonical `supported_filing_years` catalogue. Candidate periods come from the selected revision's existing filing schedules and are checked through `registry_period_kind`; no modelo roster, supported-year horizon, period parser, cadence map, deadline catalogue, or downstream deduplication was introduced.

The planted-cell regression removes February from a two-month schedule and proves both the invariant helper and `RegistryValidator` refuse `(2024, "02")`. The repaired M303, M322, M349, and M353 fleet plus the deadline engine pass 164 focused tests; Ruff is clean. The canonical deadline campaign population is now complete at 555/555. A later Modelo 136 enrollment adds four independently derived periodic cells to the current whole-registry total without changing the historical campaign denominator.

## Evidence

- Commit `206f813c668` grounds and authors the five year-end coordinates and closes construct/test/engine parity.
- Commit `a5e5e677fb` activates the completeness refusal and cache-key horizon dependency.
- Official year-end rules are grounded by the existing bundled M303/M322/M353 procedures and BOE Orden EHA/769/2010 article 10 for M349; January 30, 2027 falls on Saturday, so the legal next-working-day rule yields February 1, 2027.
- Vaultspec RAG located `select_revision`, `_SCHEDULE_PERIOD_KINDS`, `filing_schedule_period_kind_mismatches`, and `supported_filing_years` before implementation; exact search confirmed no duplicate authority was added.
