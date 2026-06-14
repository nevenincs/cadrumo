---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S04'
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
     The S04 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Emit typed split-recommendation Notice from classify and ## Scope

- `add --auto-split routing into the evidence split / in-place classify`
- `src/aeat/entrypoints/cli/_ledger.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Emit typed split-recommendation Notice from classify

## Scope

- `add --auto-split routing into the evidence split / in-place classify`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Emit a typed `info` split-recommendation Notice from `classify --read-evidence` (and --saturate) when the model flags multiple components; the suggestion is the runnable --auto-split command.
- Add `--auto-split` to `classify`: one split-proposer call routes a multi-child verdict to the evidence split and a single-child verdict to in-place classification (preview or --apply).
- Refuse --auto-split without --read-evidence.

## Outcome

`classify` now recommends and actions evidence-driven splits. The recommendation rides the Notice channel (cli-notices-are-the-only-diagnostic-channel).

## Notes

The auto-split path costs one model call; the proposer response is both the verdict and the per-line selection set.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
