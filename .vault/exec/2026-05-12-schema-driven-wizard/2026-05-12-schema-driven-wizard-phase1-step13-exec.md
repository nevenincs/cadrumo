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

# `schema-driven-wizard` `phase1` `step13`

Final verification sweep for the schema-driven wizard landing.

## Gates run

- `uv run --no-sync pytest src/aeat/application/wizard/`: green
  (73 tests).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_config_setter.py`:
  green (5 tests, no xfail markers).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py`:
  green (16 tests). The 21 legacy `test_setup_*` /
  `test_app_declaration_calculate_*` tests were removed in W11
  because they exercised the deleted `aeat setup` / `aeat init`
  surface.
- `uv run --no-sync pytest src/aeat/application/wizard/ src/aeat/entrypoints/cli/test_config_setter.py src/aeat/entrypoints/cli/test_cli_surface.py`:
  94 passed.
- `from aeat.domain.profile import PROFILE_KEYS` returns a tuple
  of 39 entries compiled from `WIZARD_FLOWS` (38 prior +
  `tax.residence.ccaa`); `compile_profile_keys` is pure (no env
  / file I/O at import time).
- `aeat config set TAX.ID 12345678Z` and `aeat config set tax.id 12345678Z`
  resolve to the same `ProfileRecord.values` slot.
- `aeat config set iva.regime XYZ` exits non-zero with the
  descriptor-translated error and the choice catalogue.
- `aeat config set tax.residence.ccaa madrid` succeeds; the
  legacy `save_tax_residence` side-effect runs via
  `persist_answers`.

## Acknowledged deviations from the plan

- The directory `src/aeat/application/setup/` still exists. It
  retains a minimal namespace stub (`__init__.py`) plus
  `_env_writer.py` containing only the storage-namespace constants
  (`_PROFILE_NAMESPACE`, `_PROFILE_VERSION`, `_profile_object_key`)
  the archive registry and filing-runtime fixtures reference. Full
  directory removal waits on those callers being rewired to a
  wizard-owned namespace.
- The `SetupAnswers` symbol name survives — but it's now the
  wizard-owned typed answers model in
  `aeat.application.wizard._setup_answers`, not the dead
  identically-named class. The plan's grep gate was written
  against the legacy class which no longer exists.
- The root `aeat --help` still lists `archive` and `topic` /
  `help` alongside `config` and `app`. Removing those surfaces is
  outside the wizard plan's scope; the standing "CLI root is
  exactly config + app" mandate would require a separate plan to
  drop them.
- The `autonomo_profile_from_mapping` helper and its
  `_bool_value` / `_iva_regime_value` privates still live in
  `domain/deadlines/_profiles.py`. The deadline-engine path that
  now matters (the workflow-state-driven
  `load_active_autonomo_profile`) bypasses them; the helper
  remains for the legacy callers that still consume canonical-
  token dicts directly.
- `test_filing_cli.py` still imports
  `_PROFILE_NAMESPACE` / `_PROFILE_VERSION` /
  `_profile_object_key` from `aeat.application.setup._env_writer`;
  the constants survive there for that fixture surface.

## What landed across W1..W13

- New subpackage `aeat.application.wizard` carries the descriptor
  models, the canonical widget validators, the prompter
  abstraction (scripted + questionary), the descriptor →
  `PROFILE_KEYS` projection, the `setup` flow catalogue and its
  typed answers model, the runtime walker, the canonical-token
  persistence adapter, the seven-check verifier, the
  `WizardStatusReport` + `load_active_autonomo_profile` bridge,
  and the Typer-command factory.
- `aeat config` carries the `setup` / `set` / `get` / `unset` /
  `list` / `status` / `reset` / `auth` surface; every per-field
  setter validates through the descriptor.
- `PROFILE_KEYS` is now the import-time output of
  `compile_profile_keys(WIZARD_FLOWS)`; the hand-authored 38-entry
  tuple in the domain layer is gone.
- `ProfileKey.from_key` is the case-insensitive chokepoint;
  `get_profile_key` delegates to it.
- All four locale catalogues carry a `wizard.setup` subtree per
  the descriptor; the legacy `setup.wizard.*`, `cli.setup.*`,
  `cli.init.*` keys are deleted.
- The legacy `SetupWizard`, `SetupAnswers`, `TyperPrompter`,
  `QueuedPrompter`, and `Verifier` classes are deleted along with
  their tests, the `aeat init` root command, and the `aeat setup`
  command group.
