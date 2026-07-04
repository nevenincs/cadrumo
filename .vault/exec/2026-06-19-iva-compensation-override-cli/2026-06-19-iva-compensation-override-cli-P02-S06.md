---
tags:
  - '#exec'
  - '#iva-compensation-override-cli'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S06'
related:
  - "[[2026-06-19-iva-compensation-override-cli-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace iva-compensation-override-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-19-iva-compensation-override-cli-plan placeholders are machine-filled by
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
     The Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean and ## Scope

- `src/aeat/locales` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author override help/confirm/error locale leaves for en es ca hu via python -m aeat.locales set, then scaffold --check clean

## Scope

- `src/aeat/locales`

## Description

- Verify the override help, confirm, and error locale leaves the verb renders exist and are genuinely translated across all four target catalogues: `override_amount_help`, `override_confirm_help`, `override_confirm_required`, `override_evidence_locator_help`, `override_evidence_locator_required`, `override_filing_year_help`, `override_help`, `override_period_help`, `override_reason_help`, `override_reason_required` under the iva-wallet override verb group.
- Confirm the four named safety leaves (`override_confirm_help`, `override_confirm_required`, `override_reason_help`, `override_reason_required`) carry real prose in `en`, `es`, `ca`, and `hu` (no placeholder equalling the key).
- Run the locale CLI drift and health gates and the locale parity plus honesty gates to prove the catalogues are structurally sound.

## Outcome

- `python -m aeat.locales scaffold --check` and `python -m aeat.locales audit` both report `ok` for `ca.yml`, `en.yml`, `es.yml`, `hu.yml` (zero codebase-to-locale drift, zero missing keys, inter-locale parity intact).
- The locale parity and honesty gates pass (twenty-two tests), confirming every override leaf has key parity across the four locales and none regresses the untranslated-string honesty ceiling.
- The override verb group renders localized help, mandatory-confirm refusal, and mandatory-reason refusal in all four languages; the operator-facing surface for the verb is complete.

## Notes

- The override leaves were already present and fully translated at `HEAD` across all four catalogues (four named safety leaves confirmed in each of `en`, `es`, `ca`, `hu`), authored through the `aeat.locales` CLI in earlier commits of this feature. No new leaf authoring was required; this Step is a verification close.
- The locale `.yml` files carry unrelated uncommitted peer working-tree modifications that do not touch the override leaves; they were left untouched. This Step's commit carries only the exec record and the plan checkbox, per explicit-pathspec discipline.
