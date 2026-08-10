---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:9a27618649cf4b803c72387fe61e10a5412ed626b3196592596607cca488b64e'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# `cli-action-envelope-hardening` `W04.P06` summary

The persisted workflow continuation slice is complete. S21 replaced the
permissive workflow record with strict locale-neutral v3 models. S22 migrated
all fifteen failed-step producers to typed precondition verdicts. S23 made
work-run summaries ephemeral, projected actions through the canonical catalogue
and live CLI schema, and proved one machine envelope across English, Spanish,
Catalan, and Hungarian.

- Modified: `src/cadrumo/application/workflow/_models.py`
- Modified: `src/cadrumo/application/workflow/_persistence.py`
- Modified: `src/cadrumo/application/workflow/_engine.py`
- Modified: `src/cadrumo/application/workflow/_engine_recording.py`
- Modified: `src/cadrumo/application/workflow/_deadline_stage.py`
- Modified: `src/cadrumo/entrypoints/cli/_common.py`
- Modified: `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- Modified: `src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py`
- Created: workflow persistence, producer, renderer, and locale-catalogue
  regression coverage

## Description

Persisted runs now contain closed summary identities, typed detail facts, typed
obligation and site-health projections, and typed terminal verdicts without
rendered language, raw recovery commands, or provider evidence. The storage
boundary rejects the previous schema before hydration.

Every workflow refusal declares either a canonical action with typed bindings
and unresolved required arguments or an explicit closed no-recovery outcome.
The CLI translates summaries only at presentation time and resolves actions
through the same catalogue and reconciled live schema used by other operator
surfaces.

The phase passed 61 workflow application tests, 23 CLI integration tests, all
focused S23 tests, locale scaffold parity, and the full locale audit. Independent
S23 review and a fresh integrated S21-S23 review both returned PASS with no open
finding. Repository-wide strict typing remains red only in concurrent files
outside this phase's ownership.
