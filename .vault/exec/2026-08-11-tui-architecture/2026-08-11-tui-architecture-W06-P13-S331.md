---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:06e7adeb337b5022650e371ca333aca266bdd3e57a97dc3f18a57d745275ac1a'
step_id: 'S331'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Convert the profile area's three entry surfaces from standalone applications into mountable screens: the journey, the manager and the status surface are each their own application, so a root shell can navigate to none of them, while the area's only existing screens are modal popups inside the journey rather than the journey itself. Re-express all three as screens following the pattern the secret-area conversion establishes, and rehost every test that drives them through the application harness in the same change. TWO TRAPS THE SECRET CONVERSION PAID FOR, both of which will otherwise cost you the same time: Textual does NOT apply a screen subclass's `CSS` attribute, only `DEFAULT_CSS` -- so a naive rename silently drops the entire stylesheet while nearly every test still passes, because only a geometry assertion notices; the conversion needs `DEFAULT_CSS` plus `SCOPED_CSS = False`, and any standalone runner needs a host application carrying the base stylesheet. And the extra screen layer widens existing races, so rehosted tests must wait on a real postcondition -- the control existing, the outcome being set -- rather than on a longer sleep. Three separate entry shells is why this is not a mechanical rename: decide deliberately whether the root navigates to three destinations or whether manager and status are sub-surfaces of one profile destination, and record which and why, because that choice is the area's navigation contract

## Scope

- `the profile area's journey`
- `manager and status entry surfaces`
- `their modal sub-screens`
- `and every test that drives them`

## Changes

- `A` `src/cadrumo/entrypoints/tui/components/host.py`
- `M` `src/cadrumo/entrypoints/tui/profile/app.py`
- `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `M` `src/cadrumo/entrypoints/tui/profile/status.py`
- `M` `src/cadrumo/entrypoints/tui/devtools/surfaces.py`
- `M` `src/cadrumo/entrypoints/tui/components/form_screen.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_acquisition_source_capability.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_profile_journey.py`
- `M` `src/cadrumo/entrypoints/tui/profile/tests/test_sync_review.py`
- `M` `src/cadrumo/entrypoints/tui/tests/manager_pilot.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_field_editors.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_row_labels.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_language_switch.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_masked_field_preservation.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_masked_required_field.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_manager_required_field_refusal.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_status_screen.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_status_notices_wiring.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_status_session_deadlines.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`
- `M` `src/cadrumo/entrypoints/tui/tests/test_theme.py`
- `M` `dev/tui/_coverage.py`
- `R` `ProfileJourneyApp -> ProfileJourneyScreen`
- `R` `ProfileManagerApp -> ProfileManagerScreen`
- `R` `StatusApp -> StatusScreen`
- `R` `ProfileManagerScreen._render -> ProfileManagerScreen._redraw`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest <the manager and status suites> -m integration -n0` -> `fail`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/tests/test_theme.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tests/test_importlinter_tui_boundaries.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync python -m dev.quality.types` -> `pass`

## Notes

NAVIGATION CONTRACT: the root navigates to THREE profile destinations, not
one with sub-surfaces. The journey, the manager and the status page take
three different application projections built by three different calls, hold
no reference to one another, and are reached at different moments -- setup,
maintenance, and checking. Folding them under one destination would need a
container owning all three projections, and the journey already carries its
own five-stage navigation, so nesting would put two competing navigation
axes inside one destination.

One standalone host serves every converted screen, rather than a second copy
beside the secret area's. The secret area's own host predates it and is now a
duplicate that should collapse into this one; that was left alone because the
secret modules were being edited concurrently and a cross-area rename would
have collided.

`ProfileManagerScreen._render` shadowed Textual's own `Widget._render`, which
returns the widget's visual. Harmless while the surface was an application,
which has no such method, and fatal as a screen: every paint received a
coroutine. Renamed to `_redraw`, which is what the method does. A comment in
the shared form-screen module had already predicted this exact collision.

Two assertions are left failing and neither is caused by this Step:
`test_status_notices_wiring` expects a notice action target that the
application layer no longer produces, and the first of the two touches no
interface at all -- it calls the status projection directly -- so it cannot
be affected by a screen conversion. Introduced by the restore commit that
reinstated the notice presentation helpers.

Files were carried to main inside `923e324342`, an unrelated commit by
another author, before this Step could commit them; content verified correct
at HEAD.
