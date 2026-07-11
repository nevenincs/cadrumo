---
tags:
  - '#exec'
  - '#censo-operator-manual-enrolment'
date: '2026-07-11'
modified: '2026-07-11'
step_id: 'S04'
related:
  - "[[2026-07-11-censo-operator-manual-enrolment-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censo-operator-manual-enrolment with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-11-censo-operator-manual-enrolment-plan placeholders are machine-filled by
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
     The Remove the dead censo pull/compare/apply locale key subtree through the locales CLI (keeping the operator-manual advisory strings) and confirm scaffold --check is clean and ## Scope

- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove the dead censo pull/compare/apply locale key subtree through the locales CLI (keeping the operator-manual advisory strings) and confirm scaffold --check is clean

## Scope

- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Description

- Removed the 12 orphaned censo locale keys across `en`, `es`, `ca`, `hu` through the locales CLI (`python -m aeat.locales remove`): the retired verb help/subgroup keys, `cli.operator_surface.help.config.profile_censo`, the portal `entries.portal_mis_datos_censales.label` / `.purpose`, the four `errors.censo.*` snapshot/apply/no-censo keys, `errors.fail.fail_sede_censo_parse`, and the three `errors.refused.censo_*` keys.
- Kept the operator-facing advisory strings that survive the retirement (`cli.overview.warning.censo_enrolment_unverified` and `errors.censo.bucket_id_blank`).

## Outcome

`python -m aeat.locales scaffold --check` reports `extra=0` for all four catalogues; the diff is pure removals with no reflow (targeted `remove`, not `scaffold`, was used after an initial `scaffold` reflowed the whole file cosmetically and was reverted from HEAD).

## Notes

`scaffold --check` reports a PRE-EXISTING `missing=30` drift per locale (keys under `application.modelo.findings.cross_period_*`, `cli.app.modelo.verification_report.*`, `formula_operation_*`) owned by other in-flight campaigns (m210 / cross-period / verification). Zero of the 30 are censo-related; per full-tree-gate-must-distinguish-owner this is peer drift, not this campaign's surface, and is left untouched.
