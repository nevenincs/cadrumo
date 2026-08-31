---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:ad2a731ed91e9d137499728ce5721966ebf9d01f0d021f6a23fbbb8a272e1523'
step_id: 'S67'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove public cursor replay, resynchronization, detach and reattach, REVIEW revision and response authority, cancellation acknowledgement, typed Workspace refresh, terminal settlement, log visibility, subscriber loss, and exact C0 receipt ancestry with no private operation imports

## Scope

- `src/cadrumo/entrypoints/tui/operations/tests`

## Changes

- `A` `src/cadrumo/entrypoints/tui/operations/tests/__init__.py`
- `A` `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py`
- `M` `src/cadrumo/locales/en/common.yml`
- `M` `src/cadrumo/locales/es/common.yml`
- `M` `src/cadrumo/locales/ca/common.yml`
- `M` `src/cadrumo/locales/hu/common.yml`
- `verify:` `pytest src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py -m integration` -> `pass` (7 passed)
- `verify:` `pytest dev/locales/tests/test_parity.py dev/locales/tests/test_locale_translation_honesty.py` -> `pass` (42 passed)

## Notes

Coverage delivered: cursor replay and resynchronization (`fold_event_page`
pure-transform proof), REVIEW resolution and its single-use response
authority, cancellation acknowledgement against a genuinely running
operation, detach against a detach-allowed operation, terminal settlement
and its derived view model, log-row accumulation, and an installed Textual
`App.run_test()` proof driving the real modal end to end. "Reattach" and
"subscriber loss" are not exercised: this Step's public services carry no
reattach or multi-subscriber primitive to drive (Workspace-level reattach is
out of this phase's scope per the plan's C2 receipt boundary), so those two
listed behaviors are deferred to the phase that introduces them rather than
fabricated here.
