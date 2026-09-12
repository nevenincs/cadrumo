"""Development full-screen surfaces, each built the way production builds it.

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

from cadrumo.entrypoints.tui.tests.fixture import registration_attempt


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
    interfaces: tuple[str, ...] = ()
    """The interface classes this surface paints at its OPENING frame.

    Declared here so the review tooling reads coverage from the surface
    registry rather than keeping a second, hand-maintained opinion of which
    classes a surface covers. Empty means the surface has not declared it and
    the reviewer's static table remains the only claim.
    """
    provision: Callable[[], AbstractContextManager[str]] | None = None
    """Dedicated fixture provisioning, for a surface ``needs_profile`` alone
    can't express -- a distinct storage root, extra profile facts, or a
    persisted record beyond a bare profile. Entered instead of the shared
    ``needs_profile``/``needs_session`` path; a surface sets one or the
    other, never both."""


def _registration() -> App[Any]:
    from cadrumo.core.credentials import assess_profile_password
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.registration import RegistrationScreen

    return ScreenHostApp(RegistrationScreen(assess=assess_profile_password, register=registration_attempt))


def _login() -> App[Any]:
    from cadrumo.application.user_profile.login_interaction import (
        attempt_profile_login,
        preselected_profile_login_id,
        profile_login_choices,
    )
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.secret.login import LoginScreen

    return ScreenHostApp(
        LoginScreen(
            choices=profile_login_choices(),
            authenticate=attempt_profile_login,
            preselected=preselected_profile_login_id(None),
        )
    )


def _manager() -> App[Any]:
    from cadrumo.application.user_profile.fact_write import apply_manager_profile_field_mutation
    from cadrumo.application.user_profile.overview import build_profile_overview
    from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
    from cadrumo.application.user_profile.profile_summary import summary_inventory
    from cadrumo.core.bucket_pointer import require_active_bucket_id
    from cadrumo.entrypoints.tui.components.host import ScreenHostApp
    from cadrumo.entrypoints.tui.profile.overview import ProfileManagerScreen

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


def _workbench_surfaces() -> tuple[Surface, ...]:
    """Expose every declared workbench fixture as a drivable review surface.

    The fixture registry is the authority on which workbench states exist and
    what each one builds; this only gives each of them the harness shape the
    renderer drives. A fixture added there appears here with no edit on this
    side, which is what keeps the review inventory from disagreeing with the
    fixtures it claims to cover.

    None of them needs a profile: a workbench fixture is an immutable,
    non-sensitive projection built in memory, which is the property that lets
    the whole matrix render without provisioning encrypted storage per state.
    """
    from cadrumo.entrypoints.tui.tests.workbench_fixtures import WORKBENCH_FIXTURES

    return tuple(
        Surface(
            spec.fixture_id,
            f"{spec.surface_id} in its {spec.scenario.value} state",
            spec.build,
            needs_profile=False,
            interfaces=spec.interfaces,
        )
        for spec in WORKBENCH_FIXTURES
    )


SURFACES: dict[str, Surface] = {
    s.name: s
    for s in (
        *_workbench_surfaces(),
        Surface(
            "registration",
            "THE REAL setup wizard, step 1: credential-first profile creation",
            _registration,
            needs_profile=False,
            interfaces=(
                "cadrumo.entrypoints.tui.secret.registration.RegistrationScreen",
                "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
            ),
        ),
        Surface(
            "login",
            "The way back into a locked profile",
            _login,
            needs_profile=True,
            interfaces=(
                "cadrumo.entrypoints.tui.secret.login.LoginScreen",
                "cadrumo.entrypoints.tui.secret.credentials.CredentialScreen",
            ),
        ),
        Surface(
            "manager",
            "Profile manager over the active profile",
            _manager,
            needs_profile=True,
            needs_session=True,
            interfaces=("cadrumo.entrypoints.tui.profile.overview.ProfileManagerScreen",),
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
