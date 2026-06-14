---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S01'
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
     The S01 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Relax LLMSplitResponse to >=1 child + recommends_split and ## Scope

- `relax derive_child_amounts`
- `update build_split_prompt for the single-line verdict`
- `src/aeat/domain/transactions/_llm.py`
- `src/aeat/application/ledger/_evidence_split.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Relax LLMSplitResponse to >=1 child + recommends_split

## Scope

- `relax derive_child_amounts`
- `update build_split_prompt for the single-line verdict`
- `src/aeat/domain/transactions/_llm.py`
- `src/aeat/application/ledger/_evidence_split.py`

## Description

- Relax `LLMSplitResponse` to accept one-or-more children (was two-or-more); a single child at proportion 1.0 is the no-split verdict.
- Add `recommends_split` (more than one child) to `LLMSplitResponse`.
- Relax `derive_child_amounts` to accept one proportion, returning the whole gross on one child; reject only the empty case.
- Update `build_split_prompt` to ask for exactly one child for a single-line invoice, one per line otherwise.

## Outcome

Single-line invoices now have a first-class no-split verdict. `test_llm_split_schema.py` and `test_evidence_split.py` updated and green.

## Notes

The manual `split_transaction` still requires two-or-more children; only the LLM evidence-split derivation relaxed.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
