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

# `schema-driven-wizard` `phase1` `step11`

Removed the dead `setup` wizard surface and routed the surviving
consumers through the new descriptor-based persistence.

## What landed

- `src/aeat/application/setup/_wizard.py`, `_prompter.py`,
  `_models.py`, `_protocols.py`, `_verifier.py`, `_errors.py`, plus
  the matching test files (`test_wizard.py`, `test_models.py`,
  `test_verifier.py`, `test_env_writer.py`) — deleted. The legacy
  `SetupWizard`, `SetupAnswers`, `TyperPrompter`, `QueuedPrompter`,
  and `Verifier` classes no longer exist.
- `src/aeat/application/setup/_env_writer.py` — slimmed to the
  three storage-namespace constants (`_PROFILE_NAMESPACE`,
  `_PROFILE_VERSION`, `_profile_object_key`) the archive registry
  and filing-runtime tests reference. `load_profile_envelope`,
  `write_profile_file`, `write_env_file`, `owned_env_keys`, and
  the password-comment helpers are gone.
- `src/aeat/application/setup/__init__.py` — replaced by a minimal
  namespace stub. No more public exports.
- `src/aeat/entrypoints/cli/_setup.py` — deleted. The
  `aeat setup` command group no longer exists.
- `src/aeat/entrypoints/cli/__init__.py` — `init_cmd` (the root
  `aeat init` command) and the `_setup` import / registration are
  deleted. The root module retains the app instance plus the
  `_config`, `_archive`, `_topic`, and `app` sub-app registrations.
- `src/aeat/application/test_init_wizard.py` — deleted (covered the
  removed root `aeat init` command).
- `src/aeat/entrypoints/cli/test_cli_surface.py` — the 18
  `test_setup_*` tests and the three `test_app_declaration_*` tests
  that bootstrapped state via `aeat setup init` are deleted; the
  remaining 16 tests cover the surviving surfaces.
- `src/aeat/application/wizard/_status.py` — new file. Declares
  `WizardStatusReport`, `build_wizard_status`, and
  `load_active_autonomo_profile` — the typed bridge the deadline
  engine and the filing runtime use to obtain an `AutonomoProfile`
  from the active workflow state.
- `src/aeat/application/filing/runtime.py` and
  `src/aeat/entrypoints/cli/deadlines/_helpers.py` rewritten to
  call `load_active_autonomo_profile(workflow_state)`. The on-disk
  profile-envelope round-trip is excised.
- `src/aeat/application/setup_status.py` — `next_action` strings
  now reference `aeat config setup`, `aeat config set`,
  `aeat config auth` (legacy `aeat setup *` strings would
  reference deleted commands).
- `src/aeat/locales/{en,es,ca,hu}.yml` — `setup.wizard.*`,
  `setup.verifier.*`, `cli.setup.*`, `cli.init.*` keys removed via
  `tools/strip_dead_locale_keys.py`.
- `src/aeat/core/errors/registry/_application.py` — the
  `SetupError`, `SetupAnswersError`, `SetupAbortedError`,
  `SetupVerifyError` registry rows are deleted along with the
  classes themselves.

## Gates cleared

- `uv run --no-sync pytest src/aeat/application/wizard/` is green
  (73 tests).
- `uv run --no-sync pytest src/aeat/application/test_setup_status.py`
  is green (6 tests).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_cli_surface.py`
  is green (16 tests) — only the surfaces that survived the
  deletion.
- `grep -r "from aeat.application.setup" src/` returns only the
  archive registry's string namespace literal; no `import`
  statements survive.
- `grep -r "SetupWizard\|SetupAnswers\|TyperPrompter\|QueuedPrompter\|Verifier"
  src/aeat/application/setup/` returns no hits.
- `grep -r "setup\.wizard\.\|cli\.setup\.\|cli\.init\." src/aeat/locales/`
  returns no hits (excluding the wizard.setup-prefixed wizard
  catalogue keys, which are unrelated).
- `aeat config --help` lists `setup`, `set`, `get`, `unset`,
  `list`, `status`, `reset`, `auth` (no `init`, no `setup` group).
- `uv run --no-sync prek run --files <touched paths>` passes.

## Not in this Step

- The `_bool_value` / `_iva_regime_value` helpers in
  `domain/deadlines/_profiles.py` and the
  `autonomo_profile_from_mapping` body were left in place; the
  function continues to project canonical-token dicts onto
  `AutonomoProfile` for downstream consumers that have not yet
  migrated to the workflow-state-driven `load_active_autonomo_profile`.
- The `setup/` directory still contains the `_env_writer.py` and
  `__init__.py` stubs the archive registry and filing tests rely
  on; full removal of the directory waits on those callers being
  rewired.
- `_normalise_key` chokepoint / case-insensitive lookup is W12.
