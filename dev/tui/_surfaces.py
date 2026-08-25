"""The full-screen surfaces, each built the way production builds it.

Every builder here composes the app from the same doors the CLI hands it —
the real registration door, the real login door, and the real overview and
status projections. A builder that hand-made a
view-model would produce a surface that renders, and tell you nothing
about the one the operator meets.

Surfaces that need a profile say so through ``needs_profile``; the runner
enters the harness storage root and creates it before building.

The interactive setup experience is ``registration`` (create credentials)
followed by ``manager`` (fill and edit profile fields). The harness exposes
only operator-reachable interactive surfaces.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from textual.app import App

from cadrumo.core.flows import FlowMode

from ._modelo_work_fixture import harness_modelo_work_storage


@dataclass(frozen=True)
class Surface:
    """One drivable surface."""

    name: str
    summary: str
    build: Callable[[], App]
    needs_profile: bool = False
    needs_session: bool = False
    """Whether the surface reads through the ACTIVE-profile pointer.

    A profile that merely exists is not enough for these: they resolve the
    active bucket, so the harness must unlock one first."""
    provision: Callable[[], AbstractContextManager[str]] | None = None
    """Dedicated fixture provisioning, for a surface ``needs_profile`` alone
    can't express -- a distinct storage root, extra profile facts, or a
    persisted record beyond a bare profile. Entered instead of the shared
    ``needs_profile``/``needs_session`` path; a surface sets one or the
    other, never both."""


def _registration() -> App:
    from cadrumo.application.user_profile import assess_passphrase
    from cadrumo.entrypoints.cli._config._manager_frontend import attempt_registration
    from cadrumo.entrypoints.tui.secret.registration import RegistrationApp

    return RegistrationApp(assess=assess_passphrase, register=attempt_registration)


def _login() -> App:
    from cadrumo.entrypoints.cli._config._login_frontend import (
        _login_choices,
        attempt_login,
        preselected_profile_id,
    )
    from cadrumo.entrypoints.tui.secret.login import LoginApp

    # ``present_login`` is the real production entry point and always
    # supplies BOTH of these -- neither is a defaulted convenience the
    # screen invents for itself. ``_login_choices()`` sorts by the
    # operator's own casefolded LABEL; this used to sort by dict-item
    # tuple, which orders by the opaque bucket-id UUID first -- a reading
    # over that order describes a screen no operator meets. And
    # ``preselected_profile_id(None)`` resolves to the ACTIVE bucket,
    # never ``None`` for an unnamed invocation (``present_login``'s own
    # docstring: leaving it defaulted "silently drops the operator's named
    # target and lands on the active profile instead" -- and un-set
    # entirely drops even that, opening on the screen's arbitrary first
    # row). Building the app without either is the same shape as the
    # manager's zero-actions bug: it renders cleanly and shows less than
    # the real thing.
    return LoginApp(
        choices=_login_choices(),
        authenticate=attempt_login,
        preselected=preselected_profile_id(None),
    )


def _manager() -> App:
    from cadrumo.entrypoints.cli._config._manager_actions import manager_actions
    from cadrumo.entrypoints.cli._config._manager_frontend import (
        build_active_profile_overview,
        persist_active_profile_field,
        profile_field_value_refusal,
    )
    from cadrumo.entrypoints.tui.profile.overview import ProfileManagerApp

    # ``present_profile_manager`` is the real CLI entry point and always
    # wires ``manager_actions()`` alongside the overview and the write door.
    # Building the screen without them, as this used to, rendered a manager
    # carrying zero buttons — a surface no operator ever sees, since every
    # real launch offers the certificate, censal-pull, add-row and export
    # actions. A reading over that stand-in was a reading about the
    # stand-in, exactly what this harness exists to avoid.
    return ProfileManagerApp(
        build_active_profile_overview(),
        persist=persist_active_profile_field,
        actions=manager_actions(),
        validate=profile_field_value_refusal,
    )


def _status() -> App:
    from cadrumo.entrypoints.cli._config._status_frontend import build_status_page_data
    from cadrumo.entrypoints.tui.profile.status import StatusApp

    return StatusApp(build_status_page_data())


def _form() -> App:
    # UNLIKE every other builder here, this one is LEGITIMATELY SYNTHETIC and
    # not a stand-in for a missed real door. ``FormApp``/``FormPage`` are a
    # generic substrate a dozen unrelated callers each configure for
    # themselves -- the export destination/passphrase pair, the add-row
    # section chooser, the descendant door, the apoderado scope picker, the
    # certificate/auth form -- with no single production view-model this
    # surface could compose instead. The two fields below ("First",
    # "Second") are made up for this harness and correspond to no real
    # operator-facing copy; a finding read off THIS surface's field labels,
    # layout of two plain text fields, or wording is a finding about the
    # harness, never about the application. Drive one of the real callers
    # above instead when the thing under evaluation is an actual form.
    from cadrumo.core.i18n import tr
    from cadrumo.core.presentation import FormField, FormPage
    from cadrumo.entrypoints.tui.components.form_screen import FormApp

    return FormApp(
        FormPage(
            title="Harness form (synthetic — no real caller uses this exact shape)",
            section="Section",
            fields=(
                FormField(key="a", label="First"),
                FormField(key="b", label="Second"),
            ),
        ),
        translate=tr,
    )


def _modelo_work_wizard() -> App:
    from uuid import uuid4

    from cadrumo.core import resolve_active_bucket_id
    from cadrumo.core.flows import FrontendCapability
    from cadrumo.entrypoints.cli._modelo import _resolve_work_unit_for_cli
    from cadrumo.entrypoints.cli._modelo_work_wizard_cli import (
        _ACTIVE_RUNS,
        _definition_from_steps,
        _outstanding_wizard_steps,
    )
    from cadrumo.entrypoints.tui.flows.app import FlowTuiApp
    from cadrumo.entrypoints.tui.flows.select import select_flow_frontend

    from ._modelo_work_fixture import ensure_modelo_work_unit

    # ``harness_modelo_work_storage`` (this surface's ``provision``) already
    # holds a real ``open_test_profile_session`` open around this call.
    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        message = "modelo-work-wizard surface built outside its provisioned session"
        raise RuntimeError(message)
    work_unit_id = ensure_modelo_work_unit(bucket_id)

    # These three calls, in this order, are exactly what
    # ``run_modelo_work_wizard`` -> ``_run_wizard_steps`` makes before
    # handing the definition to ``select_flow_frontend``: resolve the same
    # work unit, discover its outstanding manual steps against the live
    # registry, and project them into a flow definition through the
    # production copy-table assembler. Reproducing the call sequence rather
    # than hand-building a ``FlowDefinition`` is what makes this surface a
    # reading of the live wizard rather than another zero-actions stand-in.
    unit = _resolve_work_unit_for_cli(work_unit_id=work_unit_id)
    steps = _outstanding_wizard_steps(unit)
    run_token = uuid4().hex
    _ACTIVE_RUNS[run_token] = {}
    definition = _definition_from_steps(steps, run_token=run_token)

    # ``select_flow_frontend`` at FULL_SCREEN capability is the identical
    # primitive ``_run_wizard_steps`` calls -- no ``checkpoint_store``, no
    # ``resume_state``, no ``registered_values`` override, because the
    # production call passes none either.
    frontend = select_flow_frontend(
        definition,
        mode=FlowMode.CREATE,
        capability=FrontendCapability.FULL_SCREEN,
    )
    if not isinstance(frontend, FlowTuiApp):
        message = f"select_flow_frontend returned {type(frontend).__name__}, not the full-screen app"
        raise RuntimeError(message)
    return frontend


SURFACES: dict[str, Surface] = {
    s.name: s
    for s in (
        Surface(
            "registration",
            "THE REAL setup wizard, step 1: credential-first profile creation",
            _registration,
            needs_profile=False,
        ),
        Surface("login", "The way back into a locked profile", _login, needs_profile=True),
        Surface(
            "manager",
            "Profile manager over the active profile",
            _manager,
            needs_profile=True,
            needs_session=True,
        ),
        Surface(
            "status",
            "Read-only status page",
            _status,
            needs_profile=True,
            # A session, not merely a profile. The notices band and the
            # session-deadline rows both read through the ACTIVE bucket, and
            # both render empty without one -- so a locked-profile reading
            # showed a status page with no advisories and no deadlines and
            # looked correct, which is the stand-in shape this harness has
            # already been caught by twice.
            needs_session=True,
        ),
        Surface(
            "form",
            "SYNTHETIC — no single production caller; do not read findings off its field content",
            _form,
            needs_profile=False,
        ),
        Surface(
            "modelo-work-wizard",
            (
                "THE LIVE modelo-work wizard — the question/review screens an operator running "
                "`aeat app modelo work wizard` actually meets, over a real M130 1T work unit, built "
                "through select_flow_frontend exactly as _modelo_work_wizard_cli.py composes it"
            ),
            _modelo_work_wizard,
            provision=harness_modelo_work_storage,
        ),
    )
}


def resolve(name: str) -> Surface:
    """Return the named surface, or refuse listing the accepted set."""
    try:
        return SURFACES[name]
    except KeyError:
        accepted = ", ".join(sorted(SURFACES))
        message = f"unknown surface {name!r}; accepted: {accepted}"
        raise KeyError(message) from None


__all__ = ["SURFACES", "Surface", "resolve"]
