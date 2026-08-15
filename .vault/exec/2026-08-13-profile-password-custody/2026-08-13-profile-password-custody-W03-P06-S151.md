---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:ca6c818ff08dfab9c0516503c5d4c5fa201c6744892bbca31900bedf446c277f'
step_id: 'S151'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh render the next-action guidance on the surviving registration surfaces, since the projection mapping a non-resident IRNR taxpayer to the modelo describe route is live and reached only from the edit path while the creation path refuses before it, so a newly registered IRNR taxpayer is steered nowhere until they happen to run edit and the registration screens render no next action at all

## Scope

- `src/cadrumo/entrypoints/cli/_config/_registration_screen.py and src/cadrumo/entrypoints/cli/_config/_manager_frontend.py`

## Description

- Confirmed the row's premise by reading the routing projection whole: a private
  `_next_step_command_for_profile_values` in the wizard's command module mapped a
  profile's `taxpayer_type.fiscal_residency` fact to either a default follow-on
  command or, for `NON_RESIDENT_IRNR`, the Modelo 210 describe route. It was consumed
  only by the scripted wizard's own text-only success line, reached solely from a
  non-interactive invocation (`--quiet`/`--accept-defaults`, or a host that cannot go
  full-screen) — never from the interactive manager the surviving credential-first
  registration door hands off to. The manager's `ProfileOverview.notices` carried no
  next-step content at all.
- Restructured the projection so a modelo id (`profile_next_step_modelo`) is the
  primary classification and the CLI command string
  (`next_step_command_for_profile_values`) is derived from it, then promoted both to
  the `application.wizard` public facade — a precondition for a cross-package
  consumer, since neither was previously exported. The classification stayed a single
  rule in one place; only its export surface and internal composition changed.
- Wired the reused classification into the profile manager's overview builders
  (`build_active_profile_overview` and the `_active_profile_manager_storage._page`
  closure), both of which the manager reaches whether opened straight from
  registration or from a later `edit`. A new `Notice` renders only when the
  classification diverges from the default, so an untouched or resident profile
  renders no guidance at all.
- Discovered mid-implementation that the shared `Notice` model structurally refuses
  an embedded executable `aeat ...` command line in `message` or `context`
  (`ResolvedNoticeAction`/`ResolvedPreconditionAction` is the sole sanctioned
  executable-identity channel, and building one requires the live operator-surface
  action catalogue this change does not own). Reworded the notice to name the routed
  MODELO in prose instead of echoing the CLI invocation, which is also why the
  projection was restructured to expose the modelo id as primary data rather than a
  ready-made command string.
- Made no change to `_registration_screen.py`: registration collects only a label,
  passphrase and output language, so no fiscal-residency fact exists yet at the
  moment that screen runs — there is nothing for the projection to classify there. The
  manager session it opens straight into is where the guidance can first become live,
  as soon as the operator answers the fiscal-residency question.
- Locale key `flows.manager.next_step_modelo` (context `{modelo}`) required no
  coordination in the end: another agent's concurrent locale work populated real
  values in all four catalogues (en/es/ca/hu) matching this call site before
  verification, and the parity/honesty gates confirm the key is clean.

## Outcome

- The projection's premise held: it was genuinely live but reached only from the
  scripted/non-full-screen wizard path, never from the interactive manager.
- `src/cadrumo/application/wizard/_commands.py`: `profile_next_step_modelo` (new,
  primary) and `next_step_command_for_profile_values` (now derived) promoted to
  public names; `DEFAULT_PROFILE_NEXT_COMMAND` promoted alongside them.
- `src/cadrumo/application/wizard/__init__.py`: exported the three promoted symbols
  from the package facade in `__all__`.
- `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py`: added
  `_profile_next_action_notice` and `_overview_notices`, and wired the latter into
  both `build_active_profile_overview` and the manager-session `_page` closure,
  replacing their direct `build_active_profile_notices(record)` calls.
- Two-way bite-proof (real encrypted bucket, real registration/login/write doors, no
  mocks, run from a scratchpad script outside the repo): an IRNR profile with a
  declared EU/EEA country renders `Notice(code="config.profile.manager.next_step_modelo",
  message="Los datos declarados de este perfil lo dirigen al Modelo 210.")` in the
  manager overview; a bare-registered profile and an explicit RESIDENT_IRPF profile
  both render no such notice at all.
- Verification (attributed): `ruff check`/`ruff format --check` clean on all three
  changed files. `test_manager_frontend_routing.py` (9/9) and `application/wizard/tests`
  (274 passed) green. Ambient red observed and NOT mine: `test_import_hygiene_gate.py`
  (7 failed — `profile_custody`/`_master_key_io` delegate-wrapper and TUI-migration-hash
  drift from concurrent work, none naming my three files);
  `test_registration_screen.py::test_typing_credentials_and_pressing_create_makes_a_live_profile`
  (fails inside `adapters/persistence/storage/master_key`, a held package, before any
  of my code runs); four `RegistryValidationError` setup errors and three
  `test_wizard_validation_localization.py`/`test_scripted_parity.py` failures tied to
  the already-settled scripted-create refusal and an in-flight registry sweep;
  `test_locale_translation_honesty.py` one failure on unrelated Modelo 303 registry
  keys. None of these reference the classification, the wizard facade promotion, or
  the manager overview code this Step touched.
- Not checking the plan row per instruction; deferring that to the dispatcher.

## Notes

- Found, and left unfixed as out-of-scope (reported for separate tracking): setting
  `taxpayer_type.fiscal_residency=NON_RESIDENT_IRNR` alone, before
  `country_of_fiscal_residence`, crashes the manager overview today with an
  unguarded `pydantic.ValidationError` inside `build_active_profile_notices` ->
  `projection_for_taxpayer`. This is pre-existing (the crashing call was already
  reached on every manager field edit before this Step) and lives in
  `_status_frontend.py`/`application/user_profile`, both held by other agents — not
  introduced or fixed here, but directly blocks the exact IRNR onboarding flow this
  Step exists to unblock, so it is captured verbatim in the scratchpad probe rather
  than silently worked around.
- A second, independently-reproduced pre-existing defect: `Notice(message=...)`
  already raises today for the wizard's own `modify_descendants_via_door` notice
  (`application/wizard/_commands.py`, untouched by this Step) because that message
  also embeds a literal `aeat ...` command line. Confirmed via a standalone
  repro before touching any code; not fixed here (same "no raw command in `Notice`"
  constraint this Step designed around, but a pre-existing call site, not introduced
  by this Step).
- My own working-tree edits to the three files above were captured into `main` by a
  peer's broad "registry: continue authority-grade sweep" commits (three incremental
  snapshots) during this Step's execution, rather than by any commit I ran myself — I
  never invoked `git commit`/`git add`. Verified the final on-disk state matches HEAD
  exactly (`git diff HEAD` empty for all three files) after the last edit, so nothing
  was lost, but the commit messages do not name this Step.
