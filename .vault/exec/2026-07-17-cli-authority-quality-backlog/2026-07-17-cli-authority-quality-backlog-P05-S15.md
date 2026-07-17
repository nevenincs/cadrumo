---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S15'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-quality-backlog with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-17-cli-authority-quality-backlog-plan placeholders are machine-filled by
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
     The Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives and ## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Implement one application review workflow for suggest, saturate, review, apply, reject, evidence no-split, and evidence split while composing existing canonical persistence primitives

## Scope

- `src/cadrumo/application/ledger/_llm_review_workflow.py`

## Description

- Add `execute_reviewed_decision` to `application/ledger/_llm_review_workflow.py`: the single persisting decision terminal of the review workflow.
- Route by suggestion type + `LlmReviewDecision`: REJECT delegates to `reject_llm_suggestion`; APPLY delegates to `apply_saturated_llm_classification` (saturated) or `apply_llm_classification` (classification); SPLIT delegates to `apply_evidence_split` (which itself owns the canonical single-writer `split_transaction_with_classified_children`).
- Pass `source_command` DERIVED from the mandatory `LlmReviewInvocationOrigin`, replacing each primitive's CLI-spelling default.
- Refuse the non-persisting terminals (SUGGEST preview, NO_SPLIT verdict) and decision/suggestion shape mismatches with `TransactionValidationError`.
- Prove composition + derived provenance against real SQLite persistence (no mocks): APPLY classifies the row and stamps the derived label on the `LEDGER_TRANSACTION_CLASSIFIED` event; REJECT records the declined event with the derived label and emits no classification event; the refusal terminals raise.

## Outcome

- The workflow introduces NO new write path — it is thin orchestration over the existing canonical persistence authorities (RAG-confirmed: `apply_evidence_split` already composes the single-writer split primitive, so the workflow composes the authority, never re-implements classify/split). This is the opposite of the wizard-prompter duplication failure the RAG-first mandate guards against.
- 5 real-behaviour tests pass; ruff, ty, ledger collection (397 tests), and import-linter (5/5 kept) all green. Committed as `e783f48447`.

## Notes

- Scope reading: the step's "composing existing canonical PERSISTENCE primitives" governs the deliverable — the persisting decision dispatch. The preview generators `suggest_llm_classification` / `saturate_llm_classification` / `suggest_evidence_split` are NON-persisting and remain the canonical preview authorities; the workflow's `LlmReviewDecision` vocabulary types all seven terminals (suggest/saturate-feeding/review/apply/reject/no-split/split) and the persisting ones execute while the non-persisting ones are typed and refused at the durable boundary.
- S16 wires the CLI: `classify --auto-split` + `split --llm` call the existing preview authorities for the suggestion, then route the operator's terminal through `execute_reviewed_decision` with the route's distinct invocation origin — removing the CLI-owned branching and the app-layer `source_command` defaults. S17 adds the full real-persistence + real-subprocess matrix (saturation, multi-child split, origin-attribution, CLI-route parity).
