---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:52782f58707a8507fb63ee367d147e0a5039a43db0fc679034106c3ff2b09507'
step_id: 'S35'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Create the missing end-to-end negative JSON and text locale and recovery-retry proof for overview and provisioning action or no-recovery journeys, deriving each action against the live schema and rejecting raw command prose

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_provisioning_action_recovery.py`

## Description

- Replace import interception with two committed-cohort, core-only / `llm`-extra installed product environments; the child process imports production code from the installed wheel with `PYTHONPATH` removed.
- Drive the real optional-extra and stored-selected-model-with-extra-absent producers through the S89 configuration-check DTO and `validate_registered_result`.
- Reconstruct only the text renderer's emitted action cells and prove they equal the JSON DTO projection in every supported output locale.
- Prove both failed outcomes contain their application facts and condition evidence, declare `operator_decision`, carry no action, and expose no install hint, suggestion, or next-command field.
- Invoke the installed `aeat` overview console in JSON and text for Catalan, English, Spanish, and Hungarian without matching localized wording; classify a profile/session gate separately if it precedes overview.
- Run the same real producer paths with the extra available and selected model present, proving successful rows carry neither verdict nor recovery projection.

## Outcome

- The negative proof covers `provisioning.optional_extra.importable` and `provisioning.local_model.model_requires_extra` across Catalan, English, Spanish, and Hungarian without matching localized wording.
- The result is validated against the registered `config.check` schema, and text action cells are equal to the JSON action object for both closed outcomes.
- The installed-core overview console passes its actual `overview.status` result through both render modes; the active-worktree console observation independently showed the profile-session gate occurs before configuration checking.
- S35 is ready for independent review and deliberately remains open.

## Notes

- `uv run pytest -m integration -n0 src/cadrumo/entrypoints/cli/tests/test_overview_provisioning_action_recovery.py` passed: 1 test in 336.73 seconds.
- The core-only and extra-installed cohorts contain only built committed artifacts and declared companion data wheels; no import finder, `find_spec`, `sys.modules` alteration, mock, stub, patch, monkeypatch, skip, xfail, or localized-message assertion is used.
- The focused S35 behavior is intentionally split: direct configuration DTOs prove provisioning rows while the real console proof records the distinct earlier operator-session boundary. It does not claim the overview view renders provisioning rows.
- Cross-slice action/application/app-contract testing passed 459 tests except the existing `test_profile_bound_command_populates_active_profile_label`, whose quiet profile-create invocation lacks the now-required `--tax-residence-jurisdiction-scope`.
