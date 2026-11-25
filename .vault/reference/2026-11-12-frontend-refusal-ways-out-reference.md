---
tags:
  - '#reference'
  - '#frontend-refusal-ways-out'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:e502c34f2e61705ab95b9e015e0ff693fb999f15721ae863888e51e60fa38911'
related: []
---

# `frontend-refusal-ways-out` reference: `Where the window and TUI render refusals and recovery actions today`

Survey of the wire shape of refusal verdicts and of where the desktop window and the TUI render refusals and recovery actions on `feature/tui` at `c31f711a18`, read from code. Window locators were read directly; the TUI findings come from the 2026-11-12 frontend drift survey and are marked where not re-read.

## Summary

- Verdict shape: `PreconditionVerdictSnapshot` carries `failed_condition_id`, `evidence`, `action_id`, `argument_bindings`, `missing_argument_names`, `conditionality`, `no_recovery_outcome` and, since t46, `alternative_actions` of `AlternativeActionSnapshot` (`native/desktop/frontend/src/shell/modeloContract/modelo.ts:994`, generated from the registered contracts).
- No action words are served: the catalogue entry is `action_id`, `target_command_key`, argument specifications (`src/cadrumo/application/operator_actions/catalogue.py`, class `ActionCatalogueEntry`); no locale key names a catalogue action. The only served action sentence is the carry attestation's `action_words` (`src/cadrumo/application/modelo/work_form_carry_attestation.py:119`) and the form issue lines' `action` (`src/cadrumo/application/modelo/work_form_issue_lines.py:323`).
- Window refusal words: `servedRefusalWords` reads `refusal_words` from an operation detail (`native/desktop/frontend/src/shell/ledger.ts:592`); about thirty components call it or read verdicts independently, across ledger documents, setup panes, invoices, Modelo dialogs, workspace and profile.
- Window recovery actions: rendered in the Modelo area only (`native/desktop/frontend/src/components/modelo/form/FormView.tsx:472` for the attestation, the workspace and dialogs for verdicts); no component reads `alternative_actions`.
- TUI (drift survey, not re-read): operation results print the primary action as a CLI command line; the operation modal and workbench show words only; a hand table names 12 of about 59 catalogue actions.
