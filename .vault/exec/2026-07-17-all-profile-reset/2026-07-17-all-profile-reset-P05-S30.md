---
tags:
  - '#exec'
  - '#all-profile-reset'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S30'
related:
  - "[[2026-07-17-all-profile-reset-plan]]"
---




# Prove the removed reset and sandbox spellings are absent from every source and generated surface

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py`

## Description

- Extend `test_root_grammar_invariants.py`: prove `config reset` mounts exactly start/status/resume (no flat/DATA/AUTH/profile action), rejects the retired `--scope` flag on the group and leaves, that `config profile sandbox use` and `config profile use` are unmounted, and that `config profile sandbox use` / `config reset --scope` / `reset --scope` are absent from source, locales, docs, and sequence contracts (probe files exempted).
- Clear the two production-source citations the absence scan would otherwise catch: reword the `_custody.py` switch-resolver docstring to drop the literal `sandbox use`, and drop the stale `config reset --scope` example from the `_input_schema.py` MCP comment.

## Outcome

17 grammar invariants pass (5 new). The absence scan is green, confirming no `.py`/`.yml`/`.md`/`.seq` operator or harness surface carries a removed reset/sandbox spelling. Every removed spelling refuses on the live surface (exit code 2).

## Notes

The generated terminology evaluation dataset (`_data/terminology/evaluation/coverage-report.json`) still names the old command but is a `.json` artifact outside the operator/harness scan surface; recorded in the S29 record for the lead's terminology regeneration.
