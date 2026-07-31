---
tags:
  - '#exec'
  - '#ledger-evidence-atomicity'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:603e74bcdff48f330cb7b7a143782dda1c648f44161b20fde2c5325401033d66'
step_id: 'S10'
related:
  - "[[2026-07-17-ledger-evidence-atomicity-plan]]"
---

# Prove modelo audit exposes check without replay, backend replay calls, replay result schemas, or synthetic replay events

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_audit_verbs.py`

## Description

- Add `test_audit_replay_command_is_removed` (invoking `modelo audit replay` fails as an unknown command) and `test_audit_replay_result_schema_is_not_registered` (`modelo.audit.replay` absent from `SCHEMA_REGISTRY`).
- Rewrite the end-to-end workflow test to `show -> check -> export` (no replay leg) and drop `replay` from the accepted-vocabulary map and the no-active-profile refusal loop.
- Remove `test_audit_replay_help_disclaims_aeat_contact` (its `replay_help` locale key is gone).

## Outcome

- Proves the audit surface exposes check without a replay command, replay result schema, or replay locale key, while show/check/export stay green. `test_audit_verbs.py`: 11 passed (integration). Commit `87f49c5d2f`.

## Notes

- Real Typer runner against a real EvidenceBundleService and isolated SQLite+filesystem backend; no mocks.
