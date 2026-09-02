"""Gate: every same-layer name collision is adjudicated, and every adjudication is live.

The gate refuses in both directions. A collision nobody has reasoned about
fails, which is the point: a shared name inside one layer is the class no
architectural boundary explains. A row whose collision has been resolved fails
too, so an adjudication cannot linger and quietly excuse a condition that
returns.

It stores no count and no ceiling. Nine rows today is not the contract; every
same-layer collision being accounted for is.
"""

from __future__ import annotations

import pathlib
import tomllib

import pytest

from ..name_collision_census import (
    _PACKAGE_ROOT,
    PublicDefinition,
    collect_public_definitions,
    collision_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DISPOSITIONS = pathlib.Path(__file__).resolve().parent.parent / "name_collision_dispositions.toml"
_CLASSES = frozenset({"contract_conflict", "duplicate_owed_collapse", "distinct_rename_owed", "distinct_by_design"})


@pytest.fixture(scope="module")
def dispositions() -> dict[str, dict[str, object]]:
    declared = tomllib.loads(_DISPOSITIONS.read_text(encoding="utf-8"))
    return {key: value for key, value in declared.items() if key != "schema_version"}


@pytest.fixture(scope="module")
def observed() -> dict[str, tuple[str, ...]]:
    census = collision_census(collect_public_definitions(_PACKAGE_ROOT))
    return {
        item.name: tuple(definition.module for definition in item.definitions)
        for item in census
        if item.kind == "same_layer_collision"
    }


def test_the_census_and_the_dispositions_are_both_a_real_population() -> None:
    """Neither side may be empty, or the equality below holds by saying nothing.

    The equality is safe today because the file carries rows: a census that
    silently returned nothing would fail loudly against them. It stops being safe
    the moment both sides empty together, and a check that only works while
    someone remembers not to empty a file is not a check.
    """
    definitions = collect_public_definitions(_PACKAGE_ROOT)
    same_layer = [item for item in collision_census(definitions) if item.kind == "same_layer_collision"]

    assert len(definitions) > 500, f"only {len(definitions)} definitions scanned; the scan is not reaching the package"
    assert same_layer, "the census reports no same-layer collision at all, which the corpus is not expected to satisfy"


def test_every_same_layer_collision_is_adjudicated_and_every_row_is_live(
    dispositions: dict[str, dict[str, object]], observed: dict[str, tuple[str, ...]]
) -> None:
    """No shared name inside a layer sits unexplained, and no explanation outlives its cause."""
    assert dispositions, "the dispositions file carries no rows, so this equality would assert nothing"
    assert set(observed) == set(dispositions), (
        f"collisions carrying no disposition: {sorted(set(observed) - set(dispositions))}; "
        f"dispositions whose collision is gone: {sorted(set(dispositions) - set(observed))}"
    )


def test_every_row_names_the_sites_the_census_actually_found(
    dispositions: dict[str, dict[str, object]], observed: dict[str, tuple[str, ...]]
) -> None:
    """A row describing the wrong files would reason about code that is not there."""
    for name, row in dispositions.items():
        assert tuple(row["sites"]) == observed[name], f"{name}: sites drifted from the live census"


def test_every_row_carries_a_known_class_and_a_stated_reason(
    dispositions: dict[str, dict[str, object]],
) -> None:
    """An adjudication without a class or a reason has adjudicated nothing."""
    for name, row in dispositions.items():
        assert row["class"] in _CLASSES, f"{name}: unknown class {row['class']!r}"
        assert str(row["reason"]).strip(), f"{name}: states no reason"


def test_the_gate_detects_an_unadjudicated_collision() -> None:
    """A new same-layer collision fails rather than passing unnoticed.

    Constructed on definitions rather than files: the corpus is fully
    adjudicated, so the condition the gate exists for cannot be observed in it,
    and a gate that has only ever seen a clean corpus has proven nothing.
    """
    intruder = (
        PublicDefinition(name="brand_new", module="core/a.py", layer="core", argc=1),
        PublicDefinition(name="brand_new", module="core/b.py", layer="core", argc=1),
    )
    census = collision_census(intruder)
    surfaced = {item.name for item in census if item.kind == "same_layer_collision"}
    assert surfaced == {"brand_new"}

    declared = tomllib.loads(_DISPOSITIONS.read_text(encoding="utf-8"))
    assert "brand_new" not in declared, "the constructed name must not be a real row"
