---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S100'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P05.S100 - verify modelo work help import regression

Scope: `src/aeat/entrypoints/cli/_modelo*.py`, `src/aeat/entrypoints/cli/tests/test_output_language_parity.py`.

## Description

- Re-run the `app modelo work calculate --help` path in a fresh Python process with exception capture disabled.
- Re-run the full output-language parity module after the dirty modelo fragments settled.
- Confirm whether the earlier `NameError: lru_cache is not defined` failure still reproduces.

## Outcome

The direct help probe exited 0, and `test_output_language_parity.py` reported 40 passing tests. No code change was required for this edge.

## Notes

The earlier parity failure was recorded in S99 because it occurred during verification of the config bucket-history extraction. The fresh-process rerun cleared the concern.
