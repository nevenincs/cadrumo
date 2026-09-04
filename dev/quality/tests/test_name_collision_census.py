"""Real-behaviour tests for the public-name collision census.

Two of the four classes exist in the corpus and are pinned against it. The
other two are constructed, because a class the screen has never actually
emitted is a class nobody has shown it can emit.
"""

from __future__ import annotations

import pathlib

import pytest

from ..name_collision_census import (
    PublicDefinition,
    collect_public_definitions,
    collision_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def definitions() -> tuple[PublicDefinition, ...]:
    from ..name_collision_census import _PACKAGE_ROOT

    return collect_public_definitions(_PACKAGE_ROOT)


def _named(census: tuple, name: str):
    return next(item for item in census if item.name == name)


def test_the_package_yields_public_definitions_across_every_layer(
    definitions: tuple[PublicDefinition, ...],
) -> None:
    """The collector reaches the whole package, not one corner of it."""
    layers = {item.layer for item in definitions}
    assert {"core", "domain", "application", "adapters", "entrypoints"} <= layers
    assert len(definitions) > 500


def test_module_entrypoints_are_classified_apart_from_findings(
    definitions: tuple[PublicDefinition, ...],
) -> None:
    """Every runnable module has a ``main``; that is convention, not ambiguity."""
    collision = _named(collision_census(definitions), "main")
    assert collision.kind == "entrypoint_convention"
    assert len(collision.definitions) > 1


def test_an_overload_set_is_not_reported_as_two_definitions(
    definitions: tuple[PublicDefinition, ...],
) -> None:
    """Several signatures in one module are one implementation, not a collision."""
    collision = _named(collision_census(definitions), "redact_structured")
    assert collision.kind == "typing_overload"
    assert len({item.module for item in collision.definitions}) == 1


def test_a_name_claimed_inside_one_layer_is_the_sharpest_class(
    definitions: tuple[PublicDefinition, ...],
) -> None:
    """No architectural boundary explains a name shared within a layer."""
    census = collision_census(definitions)
    same_layer = [item for item in census if item.kind == "same_layer_collision"]
    assert same_layer, "the corpus is expected to carry same-layer collisions"
    for collision in same_layer:
        assert len({item.layer for item in collision.definitions}) == 1


def test_a_name_crossing_layers_is_classified_apart_from_one_inside_a_layer() -> None:
    """The two collision classes are distinguished by layer, not by name shape.

    Constructed rather than pinned: the same name is placed once across two
    layers and once inside one, so the classification is shown to follow the
    layer and nothing else.
    """
    crossing = (
        PublicDefinition(name="shared", module="core/a.py", layer="core", argc=1),
        PublicDefinition(name="shared", module="adapters/b.py", layer="adapters", argc=1),
    )
    within = (
        PublicDefinition(name="shared", module="core/a.py", layer="core", argc=1),
        PublicDefinition(name="shared", module="core/b.py", layer="core", argc=1),
    )
    assert collision_census(crossing)[0].kind == "cross_layer_collision"
    assert collision_census(within)[0].kind == "same_layer_collision"


def test_a_name_only_one_module_claims_is_not_a_collision() -> None:
    """A unique name yields no row at all, so the census cannot inflate itself."""
    unique = (
        PublicDefinition(name="alone", module="core/a.py", layer="core", argc=0),
        PublicDefinition(name="other", module="core/b.py", layer="core", argc=0),
    )
    assert collision_census(unique) == ()


def test_arity_is_carried_so_two_claims_can_be_told_apart(
    definitions: tuple[PublicDefinition, ...],
) -> None:
    """Differing arity is the cheapest evidence two same-named functions differ."""
    collision = _named(collision_census(definitions), "review_view")
    assert len({item.argc for item in collision.definitions}) > 1
    assert "argc=" in collision.detail


def test_an_unreadable_module_is_announced_as_absent_from_the_corpus(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A collision is detected only between names both present in this corpus.

    A silently skipped module cannot collide with anything, so the census
    reported fewer collisions than exist. The skip stays - the tree is edited
    while this runs and one half-written file must not cost the census - but it
    now says which names are missing from the comparison.
    """
    (tmp_path / "sound.py").write_text("def widen():" + chr(10) + "    return 1" + chr(10), encoding="utf-8")
    (tmp_path / "broken.py").write_text("def (:" + chr(10), encoding="utf-8")

    collected = collect_public_definitions(tmp_path)

    assert [item.name for item in collected] == ["widen"]
    error = capsys.readouterr().err
    assert "cannot be reported as colliding" in error
    assert "broken.py" in error


def test_a_readable_corpus_announces_nothing(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A notice that fires on every run would tell a reader nothing."""
    (tmp_path / "sound.py").write_text("def widen():" + chr(10) + "    return 1" + chr(10), encoding="utf-8")

    assert collect_public_definitions(tmp_path)
    assert capsys.readouterr().err == ""
