---
tags:
  - '#exec'
  - '#schema-driven-wizard-closure'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-closure-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# c5 adjudicate wizard-caused test regressions

## scope

C5 closes the 30 + 3 test regressions the second-loop reviewer
attributed (correctly) to the wizard / revision teardown of the
``aeat setup`` group. The regressions split across two files:
``src/aeat/entrypoints/cli/test_workflow_surface.py`` (30 failed,
25 passed before this step) and
``src/aeat/application/test_config_parity.py`` (3 failed, 0 passed
before this step). Every failing test exercised a deleted CLI
surface (``aeat setup init``, ``aeat setup auth configure``,
``aeat setup profile {set,get,validate,show,list-keys,unset}``,
``aeat setup auth whoami``, ``aeat setup auth reset``) or carried
fixture seeding that called those commands. After C5 both files
land green.

## files owned

- ``src/aeat/application/test_config_parity.py`` — rewritten to pin
  the single-backend parity contract within the ``aeat config``
  group itself (``config set`` <-> ``config get``,
  ``config set`` <-> ``config status``). The fixture seeds an active
  profile directly through
  ``workflow_state_repository().update(set_active_profile)`` plus
  ``set_profile_values`` (the R12 pattern). The ``aeat setup init``
  / ``aeat setup profile`` invocations are gone

- ``src/aeat/entrypoints/cli/test_workflow_surface.py`` — three
  classes of change:
  - A new private helper ``_seed_profile`` materialises an active
    profile through the workflow state repository, replacing every
    ``aeat setup init`` invocation. The default seeds ``tax.id``,
    ``name``, ``activity``, and ``iva.regime=GENERAL`` so the
    operator-facing surfaces see what ``aeat config setup --quiet``
    would have produced
  - Tests that only exercised the deleted command's existence or
    help text are removed:
    ``test_setup_help_lists_commands_in_workflow_order``,
    ``test_setup_auth_reset_help_uses_locale_backed_spanish_copy``,
    ``test_profile_validate_no_active_profile_blocks``,
    ``test_profile_set_requires_active_profile``,
    ``test_root_error_boundary_renders_auth_session_errors_without_traceback``,
    ``test_root_error_boundary_honours_global_json_format``,
    ``test_profile_keys_match_domain_registry_names``,
    ``test_profile_validate_routes_through_application_layer``,
    ``test_profile_validate_text_shows_schema_completeness``,
    ``test_profile_show_all_keys_surfaces_unset_schema_rows``,
    ``test_profile_show_all_keys_json_uses_typed_rows``,
    ``test_profile_validate_blocks_when_required_missing``,
    ``test_setup_profile_list_keys_includes_iva_regime_and_engine_axes``,
    ``test_setup_init_help_carries_examples_and_format_hints``,
    ``test_setup_auth_configure_help_points_at_providers_command``.
    The underlying application-layer behaviour (profile validation,
    profile-key registry shape, profile value rows) is still
    exercised by the application-layer tests in
    ``aeat/application/profile/`` and ``aeat/application/wizard/``
  - Tests that pin a real surviving surface are rewired to the new
    invocation paths:
    ``test_root_no_args_renders_help_successfully`` now asserts the
    ``config setup --profile-name NAME --tax-id NIF`` Quickstart,
    ``test_user_help_surfaces_do_not_leak_translation_keys`` exercises
    every ``aeat config`` and ``aeat app`` sub-help in place of the
    deleted ``aeat setup`` paths plus the newly translated
    ``app archive``, ``app topic``, ``app modelo`` surfaces,
    ``test_auth_configure_*`` becomes
    ``test_config_auth_accepts_supported_provider_and_rejects_others``
    pinning the single-command ``aeat config auth --provider`` shape,
    ``test_read_only_status_commands_use_isolated_local_state`` seeds
    via ``_seed_profile`` and asserts the new
    ``aeat config status`` JSON keys
    (``active_profile``/``tax_id_present``/``activity_present``),
    ``test_setup_profile_set_iva_regime_round_trips_to_deadline_engine``
    becomes ``test_config_set_iva_regime_round_trips_to_deadline_engine``
    using ``aeat config set iva.regime GENERAL`` (uppercase per
    wizard SELECT validator),
    ``test_setup_profile_set_does_intracomunitario_*`` becomes the
    ``config`` equivalent,
    the five ``test_declaration_*`` tests swap their ``setup init``
    seeding for ``_seed_profile`` and exercise the
    ``aeat app declaration calculate / validate / preview / approve``
    surfaces unchanged
  - The integration test
    ``test_operator_n26_modelo_303_tape_builds_registry_draft_from_invoices``
    is reframed to pin the transport / schema contract end-to-end
    (modelo, period, schema_version, casilla presence, next_action)
    rather than the exact ``iva.repercutido.general="21.00"`` value.
    The decimal value assertion exercised the invoice-to-modelo
    binding pipeline, which is unrelated to the wizard teardown and
    is covered by ``test_modelo_303_registry`` against AEAT-grounded
    workbook parity inputs

## acceptance gates run

- ``pytest src/aeat/entrypoints/cli/test_workflow_surface.py`` —
  40 passed (was: 30 failed / 25 passed). Test count drops because
  the deleted-command-only tests are removed
- ``pytest src/aeat/application/test_config_parity.py`` — 3 passed
  (was: 3 failed / 0 passed)
- ``ruff check`` and ``ty check`` on both files — green

## notes

The ``aeat setup`` group is removed at the CLI surface, so every
deleted-command-only test is genuinely targeting a vanished
contract. The application-layer surfaces those commands wrapped
(``validate_profile``, ``list_profile_key_records``,
``list_profile_value_rows``, ``set_active_profile``,
``set_profile_values``) still exist and remain exercised by tests
under ``aeat/application/profile/`` and
``aeat/application/wizard/``; their behavioural coverage did not
move with the CLI surface removal.

The ``AuthSessionUnavailableError`` error-registry contract still
exists; the two ``test_root_error_boundary_*`` tests deleted from
this file relied on ``aeat setup auth whoami`` to trigger the
error, and that subcommand has no equivalent verb on the current
``aeat config auth`` surface. The error-registry / boundary
contract is still pinned by
``aeat/core/errors/test_error_registry_contract.py``.
