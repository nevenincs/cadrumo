---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:64ce180dfa1ec02b18374c673f8ed7cc20f5c501749b3adc4a51b58f6e8e3f2d'
step_id: 'S20'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Prove clean-root refusal recovery and retry through real CLI dispatch

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_profile_guard_action_recovery.py`

## Description

- Add a real clean-root refusal, recovery, exact retry, and durable re-open
  journey for the profile-bound `ledger.ratios.set` leaf.
- Assert the exact requested leaf, failed condition, evidence, canonical action,
  target command, missing binding, and conditionality in text and JSON.
- Resolve the projected target through the live Click input schema, supply the
  missing operator input, and execute `config profile create` through real CLI
  dispatch.
- Close the active session before retry and again before the final list so the
  positive state and written ratio must survive durable re-open.
- Exercise the installed `uv run --no-sync aeat` console path in separate
  processes against a disposable encrypted file-backed root.
- Complete an independent Terra xhigh review and retain its clean audit record.

## Outcome

The empty root refused `ledger.ratios.set` with `profile.active` and the
catalogued `operator.profile.create` action targeting `config.profile.create`.
The projected `profile_name` binding was explicitly missing and required
operator input. The test joined that projection to the canonical catalogue and
live input schema, created profile `recovered` through the CLI, retried the
unchanged original arguments successfully, and observed the persisted ratio
through a separate list dispatch after closing the active session.

The focused integration lane passed 17 tests, including the new end-to-end
journey and the root/refusal projection suites. The action and storage-policy
unit lane passed 55 tests. Ruff check and formatting passed, BasedPyright
reported zero diagnostics, the forbidden-technique scan was clean, and the
installed four-process console journey passed. Independent review reported no
findings and declared the Step safe to close.

## Notes

The first focused pytest invocation used the repository's default unit marker
and collected zero tests; it was discarded as evidence and rerun explicitly
with `-m integration`. A broader adjacent run exposed fifteen existing setup
errors in `test_ratios_verbs.py`: its fixture uses a UUID-shaped value as a
profile display label, which the current `BucketManifest` rejects. S20 has no
diff in that file or the label validator; the failures were isolated and left
untouched under the shared-worktree ownership boundary. No production fix was
required for S20, no Git index state was changed, and no data was lost.
