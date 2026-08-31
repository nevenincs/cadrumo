"""The canonical devtool full-screen surfaces, each built the way production builds it.

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
from typing import Any

from textual.app import App

from .fixture import registration_attempt
from .modelo_work_wizard import build_modelo_work_wizard, provision_modelo_work_wizard


@dataclass(frozen=True)
class Surface:
    """One drivable surface."""

    name: str
    summary: str
    build: Callable[[], App[Any]]
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


def _registration() -> App[Any]:
    from ....core.credentials import assess_profile_password
    from ....entrypoints.tui.components.host import ScreenHostApp
    from ....entrypoints.tui.secret.registration import RegistrationScreen

    return ScreenHostApp(RegistrationScreen(assess=assess_profile_password, register=registration_attempt))


def _login() -> App[Any]:
    from ....application.user_profile.login_interaction import (
        attempt_profile_login,
        preselected_profile_login_id,
        profile_login_choices,
    )
    from ....entrypoints.tui.components.host import ScreenHostApp
    from ....entrypoints.tui.secret.login import LoginScreen

    return ScreenHostApp(
        LoginScreen(
            choices=profile_login_choices(),
            authenticate=attempt_profile_login,
            preselected=preselected_profile_login_id(None),
        )
    )


def _manager() -> App[Any]:
    from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
    from ....application.user_profile.overview import build_profile_overview
    from ....application.user_profile.profile_record_repository import ProfileRecordRepository
    from ....application.user_profile.profile_summary import summary_inventory
    from ....core.bucket_pointer import require_active_bucket_id
    from ....entrypoints.tui.components.host import ScreenHostApp
    from ....entrypoints.tui.profile.overview import ProfileManagerScreen

    profile_id = require_active_bucket_id()
    profiles = ProfileRecordRepository.for_current_session(profile_id)
    # The label comes from the summary projection, not the authenticated
    # aggregate: `load` takes a per-profile custody lock and reads password
    # material, the transaction journal and the label head to hand back a
    # string this surface already has an unlocked session for.
    label = next(
        (item.label for item in summary_inventory().summaries if item.profile_id == profile_id),
        "",
    )

    def _overview():
        return build_profile_overview(profiles.load(profile_id), label=label)

    def _persist(path: str, value: str):
        record = apply_manager_profile_field_mutation(profile_id=profile_id, path=path, value=value)
        return build_profile_overview(record, label=label)

    return ScreenHostApp(
        ProfileManagerScreen(
            _overview(),
            persist=_persist,
        )
    )


def _status() -> App[Any]:
    from ....application.user_profile.status_projection import build_status_page_data
    from ....entrypoints.tui.components.host import ScreenHostApp
    from ....entrypoints.tui.profile.status import StatusScreen

    return ScreenHostApp(StatusScreen(build_status_page_data()))


def _modelo_work_wizard() -> App[Any]:
    """Render the canonical Modelo wizard definition over its live work unit."""
    from ....entrypoints.tui.components.host import ScreenHostApp

    return ScreenHostApp(build_modelo_work_wizard())


def _form() -> App[Any]:
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
    from ....core.i18n.render import tr
    from ....core.presentation import FormField, FormPage
    from ....entrypoints.tui.components.form_screen import FormApp

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
            "modelo-work-wizard",
            "Live Modelo 130 work wizard over the canonical application factory",
            _modelo_work_wizard,
            provision=provision_modelo_work_wizard,
        ),
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
