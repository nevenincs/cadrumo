---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S11'
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
     The S11 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Surface the latest LLM rejection on ledger view as a typed info notice reading the row's LLM-decision events and ## Scope

- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`
- `tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Surface the latest LLM rejection on ledger view as a typed info notice reading the row's LLM-decision events

## Scope

- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`
- `tests`

## Description

- Add `_latest_llm_rejection_notice`: read the row's LLM-decision events (CLASSIFIED + LLM_SUGGESTION_REJECTED), and when the most recent is a rejection, return a typed `info` Notice carrying the operator reason.
- Wire it into `ledger view`: surface the notice + a text line via `_emit_envelope(notices=...)`.
- Add `cli.ledger.view.llm_rejected_notice` / `llm_rejected_label` locales (en/es/ca/hu); document on the classify-with-llm how-to.

## Outcome

`ledger view` flags when the most recent LLM suggestion was rejected, with the reason — the deferred view one-liner from the review-loop ADR. 2 CLI tests; conformance/parity/size all green.

## Notes

The notice rides the Notice channel (cli-notices-are-the-only-diagnostic-channel); `ledger view`'s result schema is unchanged. review_status stays a pure projection (the rejection is surfaced, not folded into status).

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
