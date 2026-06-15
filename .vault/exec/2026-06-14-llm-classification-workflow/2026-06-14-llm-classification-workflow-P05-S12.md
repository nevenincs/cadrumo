---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S12'
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
     The S12 and 2026-06-14-llm-classification-workflow-plan placeholders are machine-filled by
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
     The Add ledger list --hide-llm-rejected: an event-based filter excluding rows whose latest LLM decision is a rejection, keeping review_status a pure projection and ## Scope

- `src/aeat/entrypoints/cli/_ledger_list.py`
- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add ledger list --hide-llm-rejected: an event-based filter excluding rows whose latest LLM decision is a rejection, keeping review_status a pure projection

## Scope

- `src/aeat/entrypoints/cli/_ledger_list.py`
- `src/aeat/entrypoints/cli/_ledger_read_cli.py`
- `src/aeat/locales`
- `tests`

## Description

- Add `latest_llm_decision_is_rejection` + an `exclude_llm_rejected` path to `project_ledger_list`: load the event catalogue once and drop rows whose latest LLM-decision event (classified vs rejected) is a rejection.
- Add the `ledger list --hide-llm-rejected` flag threading the exclusion; add the locale key (en/es/ca/hu).
- Verify the 7b deferral: pulled `qwen2.5vl:7b` (network recovered) and ran a live end-to-end vision classification; updated the prior audit BLOCKED->RESOLVED.

## Outcome

The batch reviewer can hide reviewed-and-declined rows from `ledger list`; review_status stays a pure projection (event-based orthogonal filter). 1 CLI test; conformance/size green. qwen2.5vl:7b live-verified.

## Notes

The exclusion reads events per listed row from one loaded catalogue; it never consults review_status. Closes the last two deferrals (declined filter + 7b weights).

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
