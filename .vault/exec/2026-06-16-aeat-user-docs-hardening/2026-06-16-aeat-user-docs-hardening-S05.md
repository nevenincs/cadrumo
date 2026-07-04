---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-04'
step_id: 'S05'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace aeat-user-docs-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-06-16-aeat-user-docs-hardening-plan placeholders are machine-filled by
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
     The Harden classify-transactions.md and ## Scope

- `docs/how-to/classify-transactions.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Harden classify-transactions.md

## Scope

- `docs/how-to/classify-transactions.md`

## Description

- Verify-close: read `classify-transactions.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm finding M6 (mixed-use classification unreachable from the documented verb): the page now documents the real working flow - `ledger ratios eligible` -> `ratios set <category-id> N` -> `ledger allocate <tx> --business-pct N --usage-ratio-id <category-id>` - and drops the false "most users need only `--business-pct`" claim.
- Confirm finding m15 (deductible-expense rows need `--category-id`): the page documents the category-id requirement and the `ledger categories` lookup.
- Confirm every documented command resolves against the live CLI.

## Outcome

- Page verified compliant at HEAD; audit findings M6 and m15 resolved (2026-06-19 batch). Delta: none required this pass.
- Imperative instruction steps, precondition block, safety note ("nothing is sent to AEAT"), Spanish-runtime note, resolving cross-links.

## Notes

- Residual m6 (ledger list prints no column headers) is an APP-side ergonomics finding, out of documentation-hardening scope. CLI conformance gate green.
