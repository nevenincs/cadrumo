---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-17'
step_id: 'S370'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# FU-S340-A localise next_action hardcoded English in WorkflowStep.details and CLI tab-delimited command-hint lines when the tab-delimited surface gets a broader localisation pass. DEFERRED-WITH-REASON: conditioned on that broader localisation pass, which is not yet scheduled

## Scope

- `consistent with pre-existing pattern across other detail keys`
- `non-blocking W09`
- `src/aeat/application/workflow/_engine.py`

## Description

- Grounded workflow and report-rendering recovery surfaces with RAG and direct source review.
- Reverted engine translation so persisted `WorkflowStep.details.next_action` values remain locale-neutral canonical values.
- Added `work runs` CLI projection of localized final-step summary and next action in text/tab and JSON, while retaining run identifiers, stages, reasons, commands, and stored results.
- Localized the refused verification-report tab value at the CLI renderer while retaining its `next_action` key, report identifier, and exact command path.
- Added all four locale leaves through the locale scaffold, not hand-edited catalogs.
- Added a real encrypted cross-locale regression: save one builder-refusal run, reload canonical evidence, render it through public `work runs` in Catalan and Hungarian text/JSON, then reload unchanged after each projection.

## Outcome

- Selected-language operator prose is localized only at the CLI rendering boundary; persisted workflow details, error fields, machine keys, and commands remain canonical.
- Encrypted `work runs` cross-locale coverage passed 13 tests in 20.02 seconds; workflow/rendering coverage passed 23 tests in 34.40 seconds; placeholder parity passed 3 tests in 6.36 seconds; explicit command-conformance coverage passed 8 tests in 8.20 seconds.
- Owned Ruff, locale scaffold/audit for ca/en/es/hu, and scoped whitespace checks passed.

## Notes

- The initial engine-localization attempt was rejected because it would have persisted locale-specific prose. The final projection-only design preserves cross-locale history integrity.
