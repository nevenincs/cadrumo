"""Read every official spelling of a closed numeric enumeration, and no comparison."""

from __future__ import annotations

import pytest

from ..export_field_numeric_derivation import numeric_enumeration_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # Modelo 322 2026 positions 134 and 135: a bare leading zero.
        ("0 , Si=1, No=2", ("0", "1", "2")),
        ("0 , Si=1, No=2. Nota 3", ("0", "1", "2")),
        # Modelo 322 2026 position 136: the zero carries its own label first.
        ("0=Vacío, Si=1, No=2", ("0", "1", "2")),
        # The earlier label-first spelling keeps its two members.
        ("Si=1, No=2", ("1", "2")),
        # Modelo 202 turnover tranches: comparisons inside labels add nothing.
        (
            '"0" No consta, "1" (>= 10 M y < 20 M €), "2" (>= 20  M y < 60 M €), "3" (>= 60 M €)',
            ("0", "1", "2", "3"),
        ),
    ],
)
def test_official_spelling_derives_its_closed_set(content: str, expected: tuple[str, ...]) -> None:
    assert numeric_enumeration_values(content) == expected


@pytest.mark.parametrize("content", ["[65]=[66]", "0 , [65]=[66]", "1=[65]"])
def test_formula_is_not_an_enumeration(content: str) -> None:
    assert numeric_enumeration_values(content) is None
