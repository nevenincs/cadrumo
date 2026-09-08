"""Profile journey fixtures are storage-free and cover every declared state.

Written after the module shipped without a test of its own. The sibling
``test_modelo_fixtures`` is the shape being followed; what is specific here is
that a journey scenario is a claim about the PRESENTATION projection, so the
scenarios are checked against the classifications they are named for rather
than merely counted.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from cadrumo.application.user_profile.presentation import ProfileFieldClassification

from ..profile_fixtures import PROFILE_FIXTURES, ProfileFixtureScenario, _presentation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODULE: Final[Path] = Path(__file__).resolve().parents[1] / "profile_fixtures.py"


def test_every_declared_scenario_has_exactly_one_fixture() -> None:
    """A scenario the enum names and no fixture builds would render nothing."""
    assert {spec.scenario for spec in PROFILE_FIXTURES} == set(ProfileFixtureScenario)
    assert len({spec.fixture_id for spec in PROFILE_FIXTURES}) == len(PROFILE_FIXTURES)


def test_every_fixture_declares_the_interface_it_paints() -> None:
    """The declaration is what supplies review coverage, so an empty one is a silent gap."""
    assert all(spec.interfaces for spec in PROFILE_FIXTURES)


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (ProfileFixtureScenario.READY, ProfileFieldClassification.APPLICABLE_REQUIRED_PRESENT),
        (ProfileFixtureScenario.BLOCKED, ProfileFieldClassification.APPLICABLE_REQUIRED_MISSING),
        (ProfileFixtureScenario.UNASSESSED, ProfileFieldClassification.NEEDS_APPLICABILITY),
    ],
)
def test_each_scenario_paints_the_state_it_is_named_for(
    scenario: ProfileFixtureScenario,
    expected: ProfileFieldClassification,
) -> None:
    """A fixture named ``blocked`` that renders a ready journey is worse than none."""
    presentation = _presentation(scenario)

    assert presentation.fields[0].classification is expected


def test_only_the_blocked_and_unassessed_scenarios_block_readiness() -> None:
    """``ready`` must actually be ready, or the surface misreports the product."""
    ready = _presentation(ProfileFixtureScenario.READY)
    blocked = _presentation(ProfileFixtureScenario.BLOCKED)
    unassessed = _presentation(ProfileFixtureScenario.UNASSESSED)

    assert ready.ready
    assert not blocked.ready
    assert not unassessed.ready


def test_fixture_paths_come_from_the_live_schema() -> None:
    """A path the schema dropped renders as its own raw label, which looks correct.

    The journey falls back to the bare path when a field cannot be resolved, so
    a stale fixture path produces a surface that paints something plausible and
    means nothing. Deriving them is what prevents it, and this is the assertion
    that the derivation is still happening.
    """
    from cadrumo.domain.user_profile.loader import load_user_profile_schema

    live = {f"{section.key}.{field.key}" for section in load_user_profile_schema().sections for field in section.fields}
    used = {field.path for spec in PROFILE_FIXTURES for field in _presentation(spec.scenario).fields}

    assert used and used <= live


def test_fixture_module_has_no_storage_network_random_or_test_fixture_dependency() -> None:
    """Storage-free is the property that lets a blocked state render with no profile."""
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"), filename=str(_MODULE))
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    }

    assert not any(
        token in imported
        for imported in imports
        for token in ("adapters", "repositories", "network", "random", ".tests")
    )


def test_every_fixture_builds() -> None:
    """The registry is only as good as the apps it can actually construct."""
    assert all(spec.build() is not None for spec in PROFILE_FIXTURES)
