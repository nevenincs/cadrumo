"""Surface names read back into the element and state the harness composed them from.

The review server groups frames by parsing their surface names, because it
must not import the registries that compose them. These checks hold that
parse to the live registries -- the workbench fixtures in process, the
surfaces and sequence scenarios through the harness process the renderer
itself asks -- so a registry that composes a name any other way fails here
rather than scattering its frames across the review.
"""

from __future__ import annotations

import pytest

from cadrumo.entrypoints.tui.tests.workbench_fixtures import WORKBENCH_FIXTURES, WorkbenchFixtureScenario

from .. import _harness
from .._review_elements import (
    FIXTURE_STATE_ORDER,
    ElementFamily,
    SurfaceParts,
    element_digest,
    parse_surface,
    state_order,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def declared() -> dict[str, SurfaceParts]:
    """Every reviewable surface, to the element and state its registry built it from."""
    fixtures = {
        spec.fixture_id: SurfaceParts(family=ElementFamily.FIXTURE, name=spec.surface_id, state=spec.scenario.value)
        for spec in WORKBENCH_FIXTURES
    }
    declared = dict(fixtures)
    for surface in _harness.surfaces():
        if surface.name not in fixtures:
            declared[surface.name] = SurfaceParts(family=ElementFamily.SCREEN, name=surface.name, state=None)
    for scenario in _harness.scenarios():
        for page, surface in scenario.pages.items():
            declared[surface] = SurfaceParts(family=ElementFamily.SEQUENCE, name=page, state=scenario.name)
    return declared


def _misread(declared: dict[str, SurfaceParts]) -> dict[str, tuple[SurfaceParts, SurfaceParts]]:
    return {name: (parts, parse_surface(name)) for name, parts in declared.items() if parse_surface(name) != parts}


def test_every_live_surface_parses_to_the_element_and_state_its_registry_declares(
    declared: dict[str, SurfaceParts],
) -> None:
    assert {parts.family for parts in declared.values()} == set(ElementFamily)
    assert _misread(declared) == {}


def test_the_registry_join_catches_a_name_composed_the_other_way_round(declared: dict[str, SurfaceParts]) -> None:
    sequence_name, sequence_parts = next(
        (name, parts) for name, parts in declared.items() if parts.family is ElementFamily.SEQUENCE
    )
    reversed_name = f"{sequence_parts.name}--seq-{sequence_parts.state}"

    assert _misread({**declared, reversed_name: sequence_parts}) == {
        reversed_name: (sequence_parts, parse_surface(reversed_name)),
    }
    assert sequence_name not in _misread(declared)


def test_fixture_states_are_ordered_as_the_fixture_registry_declares_them() -> None:
    assert tuple(scenario.value for scenario in WorkbenchFixtureScenario) == FIXTURE_STATE_ORDER


@pytest.mark.parametrize(
    ("surface", "expected"),
    [
        ("ledger-overview--stale", SurfaceParts(ElementFamily.FIXTURE, "ledger-overview", "stale")),
        (
            "seq-modelo-130-first-quarter--not-editable",
            SurfaceParts(ElementFamily.SEQUENCE, "not-editable", "modelo-130-first-quarter"),
        ),
        ("login", SurfaceParts(ElementFamily.SCREEN, "login", None)),
        ("seq---workbench", SurfaceParts(ElementFamily.FIXTURE, "seq-", "workbench")),
        ("dangling--", SurfaceParts(ElementFamily.SCREEN, "dangling--", None)),
        ("--orphan", SurfaceParts(ElementFamily.SCREEN, "--orphan", None)),
    ],
)
def test_a_surface_name_splits_at_its_last_separator(surface: str, expected: SurfaceParts) -> None:
    assert parse_surface(surface) == expected


def test_element_keys_do_not_collide_across_families() -> None:
    page = parse_surface("seq-modelo-303-first-quarter--declarations")
    screen = parse_surface("declarations")

    assert page.name == screen.name
    assert page.element != screen.element


def test_known_fixture_states_sort_before_unknown_ones_and_the_rest_by_name() -> None:
    states = ["zeta", "failure", "ready", "alpha", "stale"]

    assert sorted(states, key=lambda state: state_order(ElementFamily.FIXTURE, state)) == [
        "ready",
        "stale",
        "failure",
        "alpha",
        "zeta",
    ]
    assert sorted(states, key=lambda state: state_order(ElementFamily.SEQUENCE, state)) == sorted(states)


def test_the_element_digest_moves_with_any_frame_and_ignores_listing_order() -> None:
    frames = {"a/small/dark": "1" * 64, "a/small/light": "2" * 64}
    same = element_digest(frames)

    assert element_digest(dict(reversed(frames.items()))) == same
    assert element_digest({**frames, "a/small/light": "3" * 64}) != same
    assert element_digest({**frames, "a/large/dark": "4" * 64}) != same
    assert element_digest({"a/small/dark": "1" * 64}) != same
