---
tags:
  - '#exec'
  - '#schema-driven-wizard'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# `schema-driven-wizard` `phase1` `step9`

Wired the wizard descriptor into `aeat config`.

## What landed

- `src/aeat/entrypoints/cli/_config.py`:
  - `config_set` now looks up the matching `WizardQuestion` by
    profile key and runs `validate_widget_answer` before
    persistence, so `aeat config set iva.regime XYZ` is rejected at
    the CLI boundary with the descriptor's translated error and
    the choice catalogue.
  - New `aeat config setup` command invokes
    `build_wizard_command(SETUP_FLOW)` and supports `--quiet`,
    `--accept-defaults`, `--profile-name`, plus the most common
    flag values (`--tax-id`, `--activity`).
  - New `aeat config status` projects the active profile through
    `project_answers(SETUP_FLOW, values)` and renders the readiness
    summary the legacy `aeat setup status` produced.
  - New `aeat config reset` relocates the scoped-reset semantics
    from `aeat setup reset` (consumes `SetupResetScope`,
    `reset_setup`).
  - New `aeat config auth` relocates the auth-provider setter from
    `aeat setup auth configure` (consumes `get_auth_provider` and
    `update_auth`).
- `src/aeat/entrypoints/cli/test_config_setter.py`:
  - Asserts descriptor-validated rejection of unknown IVA regime.
  - Asserts the wizard-validated set round-trips the canonical
    value into `ProfileRecord.values` for IVA and CCAA.
  - Asserts the new `setup` / `status` / `reset` / `auth` surfaces
    show up under `aeat config --help`.
  - Adds an `xfail(strict=True)` for the case-insensitive
    `TAX.ID` / `tax.id` parity gate (closed in W12).

## Gates cleared

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_setter.py`
  passes (4 passed, 1 xfailed as planned).
- `aeat config --help` lists the new surfaces (`setup`, `status`,
  `reset`, `auth`).
- `uv run --no-sync prek run --files <touched paths>` is green.

## Not in this Step

- `_setup.py` left in place (W11 deletes it).
- Locale catalogues not migrated (W10).
- Case-insensitive key lookup not yet implemented (W12).
