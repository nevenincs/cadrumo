---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:859266567049197132af25d5ed895761661f9a3a4a55bcf90226243be611ef8a'
step_id: 'S35'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Create the missing end-to-end negative JSON and text locale and recovery-retry proof for overview and provisioning action or no-recovery journeys, deriving each action against the live schema and rejecting raw command prose

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_overview_provisioning_action_recovery.py`

## Description

- Add the S35 production-boundary proof using a fresh interpreter that makes the registered optional-extra import unavailable before application imports.
- Drive the real optional-extra and stored-selected-model-with-extra-absent producers through the S89 configuration-check DTO and `validate_registered_result`.
- Reconstruct only the text renderer's emitted action cells and prove they equal the JSON DTO projection in every supported output locale.
- Prove both failed outcomes contain their application facts and condition evidence, declare `operator_decision`, carry no action, and expose no install hint, suggestion, or next-command field.
- Run the same real producer paths with the extra available and selected model present, proving successful rows carry neither verdict nor recovery projection.

## Outcome

- The negative proof covers `provisioning.optional_extra.importable` and `provisioning.local_model.model_requires_extra` across Catalan, English, Spanish, and Hungarian without matching localized wording.
- The result is validated against the registered `config.check` schema, and text action cells are equal to the JSON action object for both closed outcomes.
- S35 is ready for independent review and deliberately remains open.
## Notes

- The live console observation `aeat --format json config check` was refused by the active profile's real session-login boundary before configuration checking. The deterministic handler/DTO proof therefore covers provisioning rows without bypassing or simulating the CLI guard.
- The focused proof passed two tests. The cross-slice action, application provisioning, and app-contract run passed 21 tests. The broader locale/schema/error run passed 365 tests and has one out-of-scope existing failure in `test_profile_bound_command_populates_active_profile_label`: its quiet profile-create invocation now lacks `--tax-residence-jurisdiction-scope`.
- Static checks passed for the owned test. Vault frontmatter and placeholder checks pass; global historical Vault warnings predate this record and remain outside S35.
