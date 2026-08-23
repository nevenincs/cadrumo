---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:4719df2671b8d5072fcf742f425e32239be2411f0290e96bda07864d78ed4efd'
step_id: 'S36'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The add the inventory source kind to the canonical taxonomy and ## Scope

- `src/cadrumo/core/aggregation.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the inventory source kind to the canonical taxonomy

## Scope

- `src/cadrumo/core/aggregation.py`

## Description

- Add the dedicated `BindingSourceKind.INVENTORY` token to the closed canonical taxonomy.
- Keep inventory outside the derived transaction-ledger, invoice, and counterpart source families.
- Classify inventory as deferred until the ordered selector, binding, and resolver steps enroll it.
- Extend the total readiness noun and operator-action projections for the new taxonomy member.
- Pin taxonomy uniqueness, family exclusion, and deferred-disposition parity in focused tests.

## Outcome

Inventory now has one canonical source identity without borrowing transaction-ledger or capital-goods semantics. The closed taxonomy and its disposition/readiness projections remain total, while live routing remains intentionally absent for later plan steps.

## Notes

Focused Ruff and ty checks passed. The expanded taxonomy, enrollment-status, disposition, selector/validator, and readiness-locale parity suites passed with 86 tests. Formal review findings were resolved and the final verdict was clear to close. No selector, validator, resolver, registry binding, or casilla mapping was added in this step.
