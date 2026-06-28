---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




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

