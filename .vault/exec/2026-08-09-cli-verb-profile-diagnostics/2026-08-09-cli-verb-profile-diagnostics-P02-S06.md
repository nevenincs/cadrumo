---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6af77492759104a8748c708a38e67f24eb8e141a19411d0d931e6e7a84dc8e07'
step_id: 'S06'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Route the overview agenda refusal through the shared enrichment helper and the typed notice channel

## Scope

- `src/cadrumo/entrypoints/cli/_overview.py`

## Description

- Replaced the agenda verb's inline `", ".join(warning.code ...)` summary and its Click parameter error with a single call to the shared refusal builder added in this Phase.
- Left the refusal CONDITION exactly as it was: the verb still refuses when warnings are present and `--allow-incomplete` was not passed.

## Outcome

The agenda refusal now names each blocking profile fact by its operator label with the legal grounding the registry carries, and reads as a workflow-state refusal rather than as invalid operator input.

Nothing about WHICH profiles refuse changed. The warning stream feeding the condition, and the condition itself, are untouched, so a profile that rendered before still renders and a profile that refused before still refuses. Only the text and the channel changed.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_overview_profile_refusal_grounding.py -m integration -n 0 -q
    7 passed in 18.07s

Condition-preservation is asserted directly by `test_calendar_allow_incomplete_still_renders_rather_than_refusing`, which proves the override path still produces a rendered projection.

## Notes

See the sibling test Step for the honest limit on end-to-end coverage of the enrichment branch at this verb.
