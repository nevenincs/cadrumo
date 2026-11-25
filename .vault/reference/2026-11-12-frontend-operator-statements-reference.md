---
tags:
  - '#reference'
  - '#frontend-operator-statements'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:5586c828f58a4c31f7be13ee4ff7c9a9cfcc087d0e6bfa96fa9888d3aaf9b88c'
related: []
---

# `frontend-operator-statements` reference: `What the backend serves for operator statements and where the frontends read it`

What the backend serves for operator statements in the Modelo edit session and form, and where the window and TUI read it, on `feature/tui` after train t48.

## Summary

- Intent kinds: `set_override_value`, `remove_override`, `attest_no_amount`, `attest_prior_value` (`native/desktop/frontend/src/shell/modeloContract/modeloEditWork.ts:91-104`, generated).
- Admission per binding: the edit surface entry lists `allowed_intents`; `attest_no_amount` only where the binding declares an absence attestation, `attest_prior_value` only for a carry the application holds no source for (`src/cadrumo/application/modelo/edit_admission.py:246-262`).
- Family statement on the form: `ModeloFormCarryAttestation` with `family`, `binding_ids`, `action_words`, `statement_words`, `effect_words` (`src/cadrumo/application/modelo/work_form_models.py:740`); the form lists them as `carry_attestations` (`work_form_models.py:849`); a field carries `stated_absent` (`work_form_models.py:326`). `AbsenceAttestationFamily` has two members on the wire (`native/desktop/frontend/src/shell/modeloContract/modeloWorkForm.ts:57`).
- Field origin has no member for a stated prior value (`ModeloFormOrigin`, `modeloWorkForm.ts:587`); no words are served for a per-binding statement.
- Window: stages `attest_no_amount` for the family banner (`native/desktop/frontend/src/components/modelo/form/session.ts:821-837`), renders it (`native/desktop/frontend/src/components/modelo/form/FormView.tsx:472`), words per staged intent in `stagedWords.ts:30` and `ReviewDialog.tsx:59`; never reads `allowed_intents`.
- TUI: no reference to `carry_attestations`, `allowed_intents` or `attest_no_amount` in `src/cadrumo/entrypoints/tui` or `src/cadrumo_runtime/host/frontend/tui`.
