"""The seven full-screen surfaces, each built the way production builds it.

Every builder here composes the app from the same doors the CLI hands it —
the real registration door, the real login door, the real overview and
status projections, the real setup definition. A builder that hand-made a
view-model would produce a surface that renders, and tell you nothing
about the one the operator meets.

Surfaces that need a profile say so through ``needs_profile``; the runner
enters the harness storage root and creates it before building.

**Which surface is the setup wizard.** The interactive setup experience an
operator actually meets is ``registration`` (create credentials) followed by
``manager`` (fill and edit profile fields). The paged ``setup`` /
``setup-modify`` flow is DELIBERATELY RETIRED as an interactive surface:
``manager_is_the_right_frontend`` routes every interactive invocation on a
capable host to the manager, because two interactive answers to "manage a
profile" was the parallel-authority failure the architecture rules forbid.
``setup_flow_definition`` survives in production only for the scripted /
``--quiet`` headless path, which renders no screen at all.

The retired surfaces stay registered here on purpose — evaluating what a dead
path still paints is how you tell an orphan from a regression — but a finding
against them is a DEAD-CODE finding, never an operator-facing one. Say which
you mean.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

from textual.app import App

from cadrumo.core.flows import FlowMode


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


def _setup(mode: FlowMode) -> Callable[[], App]:
    def build() -> App:
        from cadrumo.adapters.inbound.tui import FlowTuiApp
        from cadrumo.application.wizard import ProfileFactsCheckpointStore, setup_flow_definition
        from cadrumo.core.wizard_catalogue import get_setup_flow

        from ._fixture import PROFILE_LABEL, ensure_profile

        flow = get_setup_flow()
        creating = mode is FlowMode.CREATE
        definition = setup_flow_definition(flow, attach_descendants=creating)

        # CREATE declares checkpointing AVAILABLE, so the app demands a real
        # store. Injecting the production one — bound to the harness profile
        # — is what makes save-and-exit and resume drivable here at all.
        store = (
            ProfileFactsCheckpointStore(flow, profile_id=ensure_profile(), profile_name=PROFILE_LABEL)
            if creating
            else None
        )
        return FlowTuiApp(definition, mode=mode, checkpoint_store=store, registered_values={})

    return build


def _registration() -> App:
    from cadrumo.adapters.inbound.tui import RegistrationApp
    from cadrumo.application.user_profile import assess_passphrase
    from cadrumo.entrypoints.cli._config._manager_frontend import attempt_registration

    return RegistrationApp(assess=assess_passphrase, register=attempt_registration)


def _login() -> App:
    from cadrumo.adapters.inbound.tui import LoginApp
    from cadrumo.entrypoints.cli._config._login_frontend import (
        _login_choices,
        attempt_login,
        preselected_profile_id,
    )

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
    from cadrumo.adapters.inbound.tui import ProfileManagerApp
    from cadrumo.entrypoints.cli._config._manager_actions import manager_actions
    from cadrumo.entrypoints.cli._config._manager_frontend import (
        build_active_profile_overview,
        persist_active_profile_field,
        profile_field_value_refusal,
    )

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
    from cadrumo.adapters.inbound.tui import StatusApp
    from cadrumo.entrypoints.cli._config._status_frontend import build_status_page_data

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
    from cadrumo.adapters.inbound.tui import FormApp, FormField, FormPage

    return FormApp(
        FormPage(
            title="Harness form (synthetic — no real caller uses this exact shape)",
            section="Section",
            fields=(
                FormField(key="a", label="First"),
                FormField(key="b", label="Second"),
            ),
        ),
    )


SURFACES: dict[str, Surface] = {
    s.name: s
    for s in (
        Surface(
            "setup",
            "RETIRED paged flow, CREATE — no interactive operator reaches this",
            _setup(FlowMode.CREATE),
            needs_profile=True,
        ),
        Surface(
            "setup-modify",
            "RETIRED paged flow, MODIFY — no interactive operator reaches this",
            _setup(FlowMode.MODIFY),
            needs_profile=True,
        ),
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
        Surface("status", "Read-only status page", _status, needs_profile=True),
        Surface(
            "form",
            "SYNTHETIC — no single production caller; do not read findings off its field content",
            _form,
            needs_profile=False,
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
