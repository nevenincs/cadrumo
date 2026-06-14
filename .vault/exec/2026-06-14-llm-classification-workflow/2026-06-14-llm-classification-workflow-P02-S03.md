---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S03'
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
     The S03 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Carry multiple_components into LLMClassificationSuggestion + LLMSaturatedSuggestion and ## Scope

- `add recommends_split`
- `add apply_evidence_classification`
- `guard apply_evidence_split`
- `src/aeat/application/ledger/_llm_classification.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Carry multiple_components into LLMClassificationSuggestion + LLMSaturatedSuggestion

## Scope

- `add recommends_split`
- `add apply_evidence_classification`
- `guard apply_evidence_split`
- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Carry `multiple_components` into `LLMClassificationSuggestion` and `LLMSaturatedSuggestion`, each exposing `recommends_split`.
- Add `apply_evidence_classification` to write a no-split (single-child) suggestion in place on the parent via the single-writer manual write.
- Guard `apply_evidence_split` to refuse a single-child no-split verdict.

## Outcome

The application layer routes a no-split verdict to in-place classification and refuses to apply a degenerate one-way split. Re-exported from the package top-level.

## Notes

`apply_evidence_classification` reuses `update_manual_transaction_fields`, the same single-writer the per-child split apply uses (composition-service-no-parallel-write-path).

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
