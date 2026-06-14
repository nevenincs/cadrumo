---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S06'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace llm-classification-workflow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Add locale keys via aeat.locales and ## Scope

- `update classify-with-llm how-to with the auto-split flow`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add locale keys via aeat.locales

## Scope

- `update classify-with-llm how-to with the auto-split flow`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`

## Description

- Add five locale leaves (auto_split_help, auto_split_needs_evidence, split_recommended_message, split_recommended_label, auto_split_single_line) plus the missing split.vision_model_help across en/es/ca/hu via the aeat.locales CLI.
- Document the auto-split flow in the classify-with-llm how-to.

## Outcome

Locale parity, honesty, and scaffold --check clean; documented-command conformance green.

## Notes

All locale edits routed through `python -m aeat.locales set` (aeat-locales-cli); no hand-edited YAML.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
