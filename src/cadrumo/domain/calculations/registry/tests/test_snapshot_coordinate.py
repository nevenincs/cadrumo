"""Contracts for the one identifier naming a validated registry snapshot.

These are deliberately registry-free: they pin the identifier's collision
behaviour without loading the bundled authority, so the contract stays
measurable independently of corpus state.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

from ..snapshot_coordinate import registry_snapshot_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Every surface that names a registry snapshot. Each must route through the
#: canonical identifier rather than rebuilding one inline -- an inline rebuild is
#: how the four divergent formats arose in the first place.
# The development-side workbook parity surface routes through the same owner
# but cannot be named here: this suite holds no path into that tree. Its
# canonical-routing check is owned by the development-side parity tests.
_EMITTING_SURFACES: Final[tuple[str, ...]] = (
    "src/cadrumo/domain/calculations/registry/tests/_scenarios.py",
    "src/cadrumo/adapters/outbound/aeat/sede/_declarations.py",
)


def test_same_revision_in_two_filing_years_gets_distinct_identifiers() -> None:
    """The reported collision: one revision serving two years must not share an id.

    Modelo 130 for 2025/1T and 2026/1T both resolve revision
    ``2019-y-siguientes``. A modelo-plus-revision identifier named them
    identically, silently merging the provenance of two separate filings.
    """
    first = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
    second = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2026, period="1T")

    assert first != second


def test_same_revision_in_two_periods_gets_distinct_identifiers() -> None:
    """Period is load-bearing too, not only the filing year."""
    first = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
    second = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="2T")

    assert first != second


@pytest.mark.parametrize(
    ("field", "changed_identifier"),
    [
        (
            "modelo",
            lambda: registry_snapshot_id(modelo="131", revision_id="2019-y-siguientes", filing_year=2025, period="1T"),
        ),
        (
            "revision_id",
            lambda: registry_snapshot_id(modelo="130", revision_id="2024-y-siguientes", filing_year=2025, period="1T"),
        ),
        (
            "filing_year",
            lambda: registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2026, period="1T"),
        ),
        (
            "period",
            lambda: registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="4T"),
        ),
    ],
)
def test_every_coordinate_changes_the_identifier(field: str, changed_identifier: Callable[[], str]) -> None:
    """No coordinate may be decorative.

    Asserting only that two known-different snapshots differ would still pass
    if one coordinate were dropped from the format, so each is varied alone.
    """
    baseline = registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")

    assert baseline != changed_identifier(), field


def test_identifier_is_the_four_coordinates_in_order() -> None:
    """Pin the exact rendering the persisted observations and reports carry."""
    assert (
        registry_snapshot_id(modelo="130", revision_id="2019-y-siguientes", filing_year=2025, period="1T")
        == "130:2019-y-siguientes:2025:1T"
    )


def _rebuilds_the_identifier_inline(tree: ast.AST) -> list[str]:
    """Return f-strings that assemble a snapshot identifier from its parts.

    Detected by shape rather than by name: an f-string whose interpolations
    include both a ``.revision`` and a ``.modelo`` reach is rebuilding this
    identifier, whatever the local variable happens to be called.
    """
    rebuilt: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        reached = {
            inner.attr
            for value in node.values
            if isinstance(value, ast.FormattedValue)
            for inner in ast.walk(value)
            if isinstance(inner, ast.Attribute)
        }
        if {"revision", "modelo"} <= reached:
            rebuilt.append(ast.unparse(node))
    return rebuilt


@pytest.mark.parametrize("relative_path", _EMITTING_SURFACES)
def test_no_surface_rebuilds_the_identifier_inline(relative_path: str) -> None:
    """All four emitting surfaces route through the one owner.

    The audit found four independently formatted strings naming the same
    snapshot, three of them lossy. Fixing only the sites a finding names leaves
    a mixed population, so every emitter is checked, not just the colliding one.
    """
    repository_root = Path(__file__).resolve().parents[6]
    source = repository_root / relative_path
    # Guard the instrument itself: a mis-resolved root would make this check
    # read nothing and report a violation-free file it never opened.
    assert source.is_file(), f"emitting surface not found at {source}"

    assert _rebuilds_the_identifier_inline(ast.parse(source.read_text(encoding="utf-8"))) == []
