---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S04'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




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

