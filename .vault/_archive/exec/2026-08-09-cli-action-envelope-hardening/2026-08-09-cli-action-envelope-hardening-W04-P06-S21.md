---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0d8f8e75b32c96819f149b73b2ede1a28fd72da980388beafbf88b2c386d99b7'
step_id: 'S21'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Delete the permissive persisted workflow-details compatibility shape and replace next-action details with closed typed action and precondition records

## Scope

- `src/cadrumo/application/workflow/_models.py`

## Description

- Replace permissive mapping-compatible workflow details with a strict discriminated union of locale-neutral fact records.
- Replace persisted workflow summaries with validated abstract locale keys and typed interpolation facts.
- Carry the canonical application-owned `PreconditionVerdict` on failed workflow steps and require every aborted terminal step to declare an action or explicit no-recovery outcome.
- Reject legacy continuation fields, arbitrary extras, rendered prose, exception-shaped evidence, and presentation-shaped evidence keys at model validation.
- Advance the secure workflow-run envelope to schema version 2 and refuse older inner envelopes on both direct and enumerated reads without an upgrader.
- Prove strict model rejection, encrypted persistence round-trips, tamper rejection, version refusal, classification refusal, and output-language-invariant serialization with real production imports.

## Outcome

The S21 persistence contract is implemented and its focused model, persistence, lint, and type gates pass. Persisted workflow runs now contain only abstract locale keys, closed typed facts, and canonical action/precondition outcomes; no mapping compatibility or free-form `next_action` field remains in the model.

The plan row remains open. S22 must migrate workflow producers in `_engine.py`, `_engine_helpers.py`, `_deadline_stage.py`, and `_engine_recording.py` from English summaries and untyped detail dictionaries to this contract. S23 must migrate `_modelo_work_runs_cli.py` and `_modelo_aux_payloads.py` from mapping access and English string equality to typed rendering, and prove all four locale-catalogue keys. Closing S21 before those dependencies would leave production construction and rendering incompatible with the canonical persistence boundary.

## Notes

- A shared-worktree edit changed the model union and tests during implementation. The current authoritative bytes were reconciled without reset, restore, stash, or index mutation; all prior proof was discarded and rerun afterward.
- The ordinary `uv run --no-sync pytest` shim produced no output before the harness timeout and left only the exact child processes started by that invocation. Those PIDs were inventoried and terminated narrowly. Verification therefore used the project interpreter directly with repository addopts disabled and xdist disabled: 35 focused tests passed.
- Scoped Ruff formatting and lint pass. Targeted BasedPyright reports zero errors, zero warnings, and zero notes. `git diff --check` remains a required final handoff check.
- No commit was created and no staging or index operation was performed.
