"""Deterministic, storage-free visual fixtures for the profile journey shell.

The journey screen takes one already-built :class:`ProfilePresentationV1` and
decides nothing itself, which is exactly what makes it fixturable: a scenario
here is a presentation projection built in memory, with no profile, no
encrypted store, and no application call behind it.

Field paths are derived from the live profile schema rather than written out,
so a renamed section or field changes what these fixtures render instead of
leaving them pointing at labels the product no longer has. A scenario asks for
the shape it needs -- a blocking field, an unassessed one, a settled one -- and
takes whatever real paths the schema currently offers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from textual.app import App

from ....application.user_profile.presentation import (
    ProfileFieldClassification,
    ProfileFieldPresentationV1,
    ProfileFieldSourceClass,
    ProfilePresentationV1,
)
from ....domain.user_profile.loader import load_user_profile_schema
from ..profile.app import ProfileJourneyScreen

if TYPE_CHECKING:
    from collections.abc import Callable

#: A canonical UUIDv4 string; ``ProfileId`` is a constrained alias, not a
#: constructor, and the model validates the shape on assignment.
_PROFILE_ID: Final = "00000000-0000-4000-8000-000000000001"

#: Classifications that are settled, in the order a scenario consumes them.
_SETTLED: Final = (
    ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT,
    ProfileFieldClassification.OPTIONAL,
    ProfileFieldClassification.NOT_APPLICABLE,
)


class ProfileFixtureScenario(StrEnum):
    """Stable visual state names for the journey shell."""

    READY = "ready"
    BLOCKED = "blocked"
    UNASSESSED = "unassessed"


@dataclass(frozen=True, slots=True)
class ProfileFixtureSpec:
    """One production surface, visual scenario, and interfaces it paints."""

    surface_id: str
    scenario: ProfileFixtureScenario
    interfaces: tuple[str, ...]
    build: Callable[[], App[Any]]

    @property
    def fixture_id(self) -> str:
        """Return the stable compound identity the surface registry consumes."""
        return f"{self.surface_id}--{self.scenario.value}"


def _schema_paths(limit: int) -> tuple[str, ...]:
    """Return real ``section.field`` paths from the live profile schema.

    Derived, never listed. A fixture naming a path the schema has dropped would
    render the raw path as its own label -- the journey's documented fallback
    for an unresolvable field -- and the surface would look correct while
    showing nothing the product actually declares.
    """
    schema = load_user_profile_schema()
    paths = [f"{section.key}.{field.key}" for section in schema.sections for field in section.fields]
    return tuple(paths[:limit])


def _field(path: str, classification: ProfileFieldClassification) -> ProfileFieldPresentationV1:
    """Build one field presentation whose flags agree with its classification.

    The model validates that ``present`` and ``source`` imply each other, that
    ``applicability_assessed`` is the exact negation of NEEDS_APPLICABILITY,
    and that ``blocks_ready`` matches the classification's declared readiness
    effect. Deriving all three here keeps a scenario from having to restate
    rules the contract already owns.
    """
    unassessed = classification is ProfileFieldClassification.NEEDS_APPLICABILITY
    missing = classification is ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING
    present = not (unassessed or missing)
    return ProfileFieldPresentationV1(
        path=path,
        classification=classification,
        present=present,
        applicability_assessed=not unassessed,
        source=ProfileFieldSourceClass.MANUAL_EDIT if present else None,
        blocks_ready=unassessed or missing,
    )


def _presentation(scenario: ProfileFixtureScenario) -> ProfilePresentationV1:
    """Build the projection one scenario paints."""
    paths = _schema_paths(6)
    settled = [_field(path, _SETTLED[index % len(_SETTLED)]) for index, path in enumerate(paths[1:])]
    head = {
        ProfileFixtureScenario.READY: ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT,
        ProfileFixtureScenario.BLOCKED: ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING,
        ProfileFixtureScenario.UNASSESSED: ProfileFieldClassification.NEEDS_APPLICABILITY,
    }[scenario]
    return ProfilePresentationV1(profile_id=_PROFILE_ID, fields=(_field(paths[0], head), *settled))


def _journey_app(scenario: ProfileFixtureScenario) -> Callable[[], App[Any]]:
    """Return a builder that mounts the journey screen for one scenario."""

    def build() -> App[Any]:
        from ..components.host import ScreenHostApp

        return ScreenHostApp(ProfileJourneyScreen(_presentation(scenario)))

    return build


PROFILE_FIXTURES: tuple[ProfileFixtureSpec, ...] = tuple(
    ProfileFixtureSpec(
        surface_id="profile-journey",
        scenario=scenario,
        interfaces=("cadrumo.entrypoints.tui.profile.app.ProfileJourneyScreen",),
        build=_journey_app(scenario),
    )
    for scenario in ProfileFixtureScenario
)


def resolve_profile_fixture(fixture_id: str) -> ProfileFixtureSpec:
    """Resolve one exact fixture identity or fail with the accepted set."""
    matches = tuple(spec for spec in PROFILE_FIXTURES if spec.fixture_id == fixture_id)
    if len(matches) != 1:
        accepted = ", ".join(spec.fixture_id for spec in PROFILE_FIXTURES)
        raise KeyError(f"unknown profile fixture {fixture_id!r}; accepted: {accepted}")
    return matches[0]


__all__ = ["PROFILE_FIXTURES", "ProfileFixtureScenario", "ProfileFixtureSpec", "resolve_profile_fixture"]
