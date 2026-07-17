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
- S16/S17 RESUMER BRIEF (deferred to a fresh post-push window; captured here so the resumer starts fast):

  - S16 target file: `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`. Cutover sites (confirm line numbers at HEAD, the file churns): the reject route (~L84 `reject_llm_suggestion`), the classify-llm route `ledger_classify_llm` (~L433-560, which passes `source_command="aeat app ledger classify --llm --apply"` at ~L548-553), the saturating route `ledger_saturate_llm` (~L581+), and the auto-split routing (~L189+). Replace each direct primitive call's `source_command="aeat app ..."` argument + the CLI-owned suggest/apply/reject/split branching with one call to `execute_reviewed_decision(suggestion, origin=<route origin>, decision=<terminal>, ...)`. Route-to-origin map: classify --llm --apply -> `CLASSIFY_LLM_APPLY`; classify --llm --reject -> `CLASSIFY_LLM_REJECT`; classify --llm --saturate --apply -> `CLASSIFY_LLM_SATURATE_APPLY`; classify --iva-category --saturate -> `CLASSIFY_IVA_CATEGORY_SATURATE`; classify --read-evidence --auto-split --apply -> `CLASSIFY_AUTO_SPLIT`; split --llm -> `SPLIT_LLM`. Previews stay on the existing `suggest_llm_classification` / `saturate_llm_classification` / `suggest_evidence_split` authorities (not persisting, no origin needed).

  - S16 conformance gates to keep GREEN through the cutover (behaviour-preserving routing change — the operator-facing envelope/notices/exit codes must not drift): (1) documented-command conformance `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py` (the Typer-tree walk; run `-m integration`); (2) JSON-schema/envelope conformance `src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py` (shared spine + no bespoke notice field, per `cli-notices-are-the-only-diagnostic-channel`); (3) the CLI-tree / operator-surface manifest gate; (4) the ledger LLM CLI's own behaviour tests. Watch that the durable `source_command` audit label change (now the origin-derived spelling) does not break any test asserting the old exact string — those assertions move to the derived label.

  - S17 target file: `src/cadrumo/application/ledger/tests/test_llm_reject.py` (extend) — prove suggestion, saturation, rejection, no-split, multi-child split, invocation-origin attribution, and CLI-route parity against REAL persistence + REAL model subprocess boundaries (no mocks/stubs/skip/xfail). The origin-attribution + CLI-route-parity proofs lock the provenance contract and must be non-tautological (assert the derived label equals `origin.source_command`, not a hardcoded copy). The S15 real-SQLite composition tests in `test_llm_review_workflow.py` are the pattern to extend for the split/saturation matrix.
