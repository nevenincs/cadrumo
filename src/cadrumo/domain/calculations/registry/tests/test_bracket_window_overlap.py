"""Bracket resolution must not depend on declaration order.

Bracket-table validation rejected duplicate ranges only when the entries shared
a ``valid_from``. Rows declared in different windows could still cover the same
numeric interval on a date both windows contain, and ``resolve_bracket`` gathers
every date-valid row, sorts by ``lower_bound`` alone, then returns the first base
match -- so reversing two otherwise identical rows changed the fixed addition and
the tax result instead of raising.

These tests build real ``BracketEntry`` / ``ParameterDefinition`` models (no
doubles), prove the refusal, and pin the shapes that must stay legal: rows for
consecutive filing years reuse the same tranches by design and are legal because
their windows are disjoint.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.schema_formula import BracketEntry, ParameterDefinition

from ..formula_runtime_ops import resolve_bracket

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL_REF = "ley-35-2006:art-63"
_SOURCE_REF = "aeat-renta-2024-manual-parte1"


def _bracket(
    *,
    lower: str,
    upper: str | None,
    fixed: str,
    valid_from: date,
    valid_to: date | None,
) -> BracketEntry:
    return BracketEntry(
        lower_bound=Decimal(lower),
        upper_bound=None if upper is None else Decimal(upper),
        fixed_addition=Decimal(fixed),
        marginal_rate=Decimal("0"),
        valid_from=valid_from,
        valid_to=valid_to,
    )


def _parameter(brackets: tuple[BracketEntry, ...]) -> ParameterDefinition:
    return ParameterDefinition(
        id="test-bracket-window-overlap",
        data_type="bracket_table",
        unit="eur",
        brackets=brackets,
        bracket_axis="devengo_date",
        legal_refs=(_LEGAL_REF,),
        source_refs=(_SOURCE_REF,),
    )


#: The audit's probe: identical numeric bounds, windows that share 2023.
_WIDE = _bracket(lower="0", upper="100000", fixed="10", valid_from=date(2020, 1, 1), valid_to=date(2025, 12, 31))
_NARROW = _bracket(lower="0", upper="100000", fixed="20", valid_from=date(2023, 1, 1), valid_to=date(2024, 12, 31))


@pytest.mark.parametrize(
    ("brackets", "order"),
    [
        pytest.param((_WIDE, _NARROW), "wide-then-narrow", id="wide-then-narrow"),
        pytest.param((_NARROW, _WIDE), "narrow-then-wide", id="narrow-then-wide"),
    ],
)
def test_cross_window_overlap_is_refused_in_either_declaration_order(
    brackets: tuple[BracketEntry, ...],
    order: str,
) -> None:
    """Both orders must refuse; refusing only one would still be order-dependent."""
    with pytest.raises(ValidationError, match="overlapping validity windows"):
        _parameter(brackets)

    assert order  # the id documents which permutation this run covered


def test_consecutive_year_windows_reusing_the_same_tranche_stay_legal() -> None:
    """The shape the whole registry relies on: disjoint windows, same bounds."""
    parameter = _parameter(
        (
            _bracket(lower="0", upper="12450", fixed="0", valid_from=date(2024, 1, 1), valid_to=date(2024, 12, 31)),
            _bracket(lower="0", upper="12450", fixed="5", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)),
        ),
    )

    assert len(parameter.brackets) == 2


def test_windows_that_share_a_date_but_not_a_tranche_stay_legal() -> None:
    """Overlap needs both axes: adjacent tranches in one window are fine."""
    parameter = _parameter(
        (
            _bracket(lower="0", upper="12450", fixed="0", valid_from=date(2024, 1, 1), valid_to=date(2025, 12, 31)),
            _bracket(lower="12450", upper="20200", fixed="5", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)),
        ),
    )

    assert len(parameter.brackets) == 2


def test_windows_touching_at_a_single_boundary_date_are_refused() -> None:
    """A one-day window intersection is still an ambiguous resolution date."""
    with pytest.raises(ValidationError, match="overlapping validity windows"):
        _parameter(
            (
                _bracket(
                    lower="0",
                    upper="12450",
                    fixed="0",
                    valid_from=date(2024, 1, 1),
                    valid_to=date(2025, 1, 1),
                ),
                _bracket(
                    lower="0",
                    upper="12450",
                    fixed="5",
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        )


def test_open_ended_windows_that_overlap_are_refused() -> None:
    """An unbounded valid_to overlaps every later window, not none of them."""
    with pytest.raises(ValidationError, match="overlapping validity windows"):
        _parameter(
            (
                _bracket(lower="0", upper="12450", fixed="0", valid_from=date(2020, 1, 1), valid_to=None),
                _bracket(
                    lower="0",
                    upper="12450",
                    fixed="5",
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
        )


def test_a_legal_bracket_table_still_resolves_its_expected_row() -> None:
    """Positive control: the gate refuses ambiguity, not ordinary resolution.

    Without this, every refusal test above would still pass if the parameter
    model had simply stopped accepting bracket tables altogether.
    """
    parameter = _parameter(
        (
            _bracket(lower="0", upper="12450", fixed="10", valid_from=date(2025, 1, 1), valid_to=date(2025, 12, 31)),
            _bracket(
                lower="12450",
                upper="20200",
                fixed="99",
                valid_from=date(2025, 1, 1),
                valid_to=date(2025, 12, 31),
            ),
        ),
    )

    resolved = resolve_bracket(parameter, Decimal("5000"), {"devengo_date": date(2025, 6, 1)})

    assert resolved == Decimal("10")
