---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
step_id: 'S04'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-wizard-substrate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S04 and 2026-07-23-tui-wizard-substrate-plan placeholders are machine-filled by
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
     The Port the widget validators and add the typed validator slots (per-answer, section-exit, flow-scope) returning i18n message keys with redacted diagnostics and ## Scope

- `src/cadrumo/application/flows/_validators.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Port the widget validators and add the typed validator slots (per-answer, section-exit, flow-scope) returning i18n message keys with redacted diagnostics

## Scope

- `src/cadrumo/application/flows/_validators.py`

## Description

- Port the widget-shape validators to the substrate with the blank-optional policy carried over, add the three-scope validator registries (per-answer, section-exit, flow-scope) returning typed verdicts with i18n message keys, and the redaction funnel for diagnostics.
- Land in commit 91c5e51afc.

## Outcome

Registries reject duplicate ids; verdict contexts never carry raw answers (reviewer-verified redaction pass).

## Notes

Domain validators (tax-id checksum, postcode) intentionally not ported: they register per-flow via the answer-validator registry.
